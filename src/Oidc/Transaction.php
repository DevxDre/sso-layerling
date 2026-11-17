<?php

namespace Sso\Layerling\Oidc;

/**
 * Eine Login-Transaktion: State, Nonce und PKCE-Verifier (je 256 Bit aus random_bytes, unabhängig voneinander),
 * dazu was beim Start feststand. Liegt nur serverseitig im privaten Login-Kontext des Browsers, höchstens
 * Config::TRANSACTION_TTL Sekunden, und wird beim ersten Callback verbraucht.
 */
final class Transaction
{
    public const ENTRIES = ['site'];

    private function __construct(
        public readonly string $state,
        public readonly string $nonce,
        public readonly string $verifier,
        public readonly int $created,
        public readonly string $issuer,
        public readonly string $redirectUri,
        public readonly string $entry,
        public readonly string $target
    ) {
    }

    public static function create(Config $config, int $now, string $entry, string $target): self
    {
        return new self(
            self::random(),
            self::random(),
            self::random(),
            $now,
            $config->profile->issuer,
            $config->redirectUri,
            in_array($entry, self::ENTRIES, true) === true ? $entry : 'site',
            $target
        );
    }

    /** PKCE S256 (RFC 7636): BASE64URL(SHA-256(verifier)) – 43 Zeichen */
    public function challenge(): string
    {
        return self::base64url(hash('sha256', $this->verifier, true));
    }

    public function expired(int $now): bool
    {
        return $now - $this->created >= Config::TRANSACTION_TTL || $this->created > $now + Config::LEEWAY;
    }

    public function toArray(): array
    {
        return [
            'state' => $this->state, 'nonce' => $this->nonce, 'verifier' => $this->verifier, 'created' => $this->created,
            'issuer' => $this->issuer, 'redirectUri' => $this->redirectUri, 'entry' => $this->entry, 'target' => $this->target,
        ];
    }

    /** aus der Session; null bei jeder Abweichung von der erwarteten Form */
    public static function fromArray(mixed $data): self|null
    {
        if (is_array($data) === false) {
            return null;
        }
        foreach (['state', 'nonce', 'verifier'] as $key) {
            if (is_string($data[$key] ?? null) === false || preg_match('~^[A-Za-z0-9_-]{43}$~D', $data[$key]) !== 1) {
                return null;
            }
        }
        if (
            is_int($data['created'] ?? null) === false ||
            is_string($data['issuer'] ?? null) === false ||
            is_string($data['redirectUri'] ?? null) === false ||
            in_array($data['entry'] ?? null, self::ENTRIES, true) === false ||
            is_string($data['target'] ?? null) === false
        ) {
            return null;
        }

        return new self(
            $data['state'], $data['nonce'], $data['verifier'], $data['created'],
            $data['issuer'], $data['redirectUri'], $data['entry'], $data['target']
        );
    }

    public static function base64url(string $data): string
    {
        return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
    }

    private static function random(): string
    {
        return self::base64url(random_bytes(32));
    }
}
