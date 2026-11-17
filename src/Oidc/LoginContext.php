<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

/** A persistent browser context with one-use, cancellable transactions; never an HTTP test-login. */
final class LoginContext
{
    private $handle;
    private array $data;
    public function __construct(private string $private, public readonly string $id, bool $create = false)
    {
        if (!preg_match('/^[a-f0-9]{64}$/D', $id)) { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $path = $private . '/contexts/' . $id . '.json';
        if (is_link($path)) { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $this->handle = fopen($path, $create ? 'x+b' : 'r+b');
        if (!$this->handle || !flock($this->handle, LOCK_EX)) { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $raw = stream_get_contents($this->handle);
        $this->data = $create ? ['created' => time(), 'csrf' => bin2hex(random_bytes(32)), 'status' => 'idle', 'attempts' => []]
            : (Json::object($raw) ?? throw new LoginFailed(LoginFailed::TRANSACTION));
        if (!is_int($this->data['created'] ?? null) || $this->data['created'] > time()
            || time() - $this->data['created'] >= 21600 || !is_string($this->data['csrf'] ?? null)) {
            throw new LoginFailed(LoginFailed::TRANSACTION);
        }
        if ($create) { $this->save(); }
    }
    public function csrf(): string { return $this->data['csrf']; }
    public function checkCsrf(mixed $csrf): void
    {
        if (!is_string($csrf) || !hash_equals($this->csrf(), $csrf)) { throw new LoginFailed(LoginFailed::TRANSACTION); }
    }
    private function save(): void
    {
        $json = json_encode($this->data, JSON_THROW_ON_ERROR);
        rewind($this->handle);
        if (!ftruncate($this->handle, 0) || fwrite($this->handle, $json) !== strlen($json) || !fflush($this->handle)) {
            throw new LoginFailed(LoginFailed::TRANSACTION);
        }
    }
    public function begin(Config $config, int $now): Transaction
    {
        if (($this->data['status'] ?? '') === 'processing') { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $attempts = array_values(array_filter($this->data['attempts'], static fn($at) => $at > $now - 300));
        if (count($attempts) >= 5) { throw new LoginFailed(LoginFailed::RATE_LIMIT); }
        $counter = fopen($this->private . '/sequence.lock', 'c+b');
        if (!$counter || !flock($counter, LOCK_EX)) { throw new LoginFailed(LoginFailed::ACCOUNT_LOCK); }
        try {
            $sequence = (int)stream_get_contents($counter) + 1;
            rewind($counter);
            if (!ftruncate($counter, 0) || fwrite($counter, (string)$sequence) === false || !fflush($counter)) { throw new LoginFailed(LoginFailed::ACCOUNT_WRITE); }
        } finally { flock($counter, LOCK_UN); fclose($counter); }
        $tx = Transaction::create($config, $now, 'site', '/');
        $this->data['attempts'] = [...$attempts, $now];
        $this->data['sequence'] = $sequence;
        $this->data['transaction'] = $tx->toArray();
        $this->data['status'] = 'pending';
        $this->save();
        return $tx;
    }
    public function consume(mixed $state, Config $config, int $now): array
    {
        $tx = Transaction::fromArray($this->data['transaction'] ?? null);
        if (($this->data['status'] ?? '') !== 'pending' || !$tx || !is_string($state)
            || !hash_equals($tx->state, $state) || $tx->expired($now)
            || $tx->issuer !== Config::ISSUER || $tx->redirectUri !== $config->redirectUri) {
            throw new LoginFailed(LoginFailed::TRANSACTION);
        }
        $this->data['status'] = 'processing';
        unset($this->data['transaction']);
        $this->save(); // durable consumption BEFORE token exchange, including subsequent errors
        return [$tx, $this->data['sequence']];
    }
    public function finish(int $sequence, callable $issue): mixed
    {
        if (($this->data['status'] ?? '') !== 'processing' || ($this->data['sequence'] ?? null) !== $sequence) {
            throw new LoginFailed(LoginFailed::TRANSACTION);
        }
        // Cancellation and issuance use this same lock. A canceled callback cannot issue a session.
        $result = $issue();
        $this->data['status'] = 'done';
        $this->save();
        return $result;
    }
    public function cancel(): void
    {
        $this->data['status'] = 'cancelled';
        unset($this->data['transaction']);
        $this->save();
    }
    public function close(): void
    {
        if (is_resource($this->handle)) { flock($this->handle, LOCK_UN); fclose($this->handle); }
    }
    public function __destruct() { $this->close(); }
}
