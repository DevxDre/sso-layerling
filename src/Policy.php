<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Historical loopback policy using a server-owned authorization snapshot. */
final class Policy
{
    private readonly array $principals;
    /** Held until request shutdown; cooperating writers require LOCK_EX. */
    private $lock;

    public function __construct(string $private, private readonly array $config)
    {
        $this->lock = fopen($private . '/authorization.lock', 'rb');
        if ($this->lock === false || !flock($this->lock, LOCK_SH)) {
            Gateway::fail(503, 'authorization_unavailable');
        }
        $path = $private . '/principals.json';
        if (is_link($path) || !is_file($path) || filesize($path) > 2 * 1024 * 1024) {
            Gateway::fail(503, 'authorization_unavailable');
        }
        $records = json_decode((string) file_get_contents($path), true, 32, JSON_THROW_ON_ERROR);
        if (!is_array($records) || ($records !== [] && array_is_list($records))) {
            Gateway::fail(503, 'authorization_unavailable');
        }
        $this->principals = $records;
        if (!is_int($config['privilegeEvidenceSeconds'] ?? null) || $config['privilegeEvidenceSeconds'] < 1
            || !is_array($config['groupIds'] ?? null)) {
            Gateway::fail(503, 'invalid_configuration');
        }
        foreach (['makerspace', 'admins'] as $key) {
            $id = $config['groupIds'][$key] ?? null;
            if ($id !== null && (!is_string($id) || preg_match('/^[A-Za-z0-9_-]{1,128}$/D', $id) !== 1)) {
                Gateway::fail(503, 'invalid_configuration');
            }
        }
        $maker = $config['groupIds']['makerspace'] ?? null;
        if ($maker !== null && $maker === ($config['groupIds']['admins'] ?? null)) {
            Gateway::fail(503, 'invalid_configuration');
        }
    }

    public function requireActor(string $actor): void
    {
        if (($this->record($actor)['enabled'] ?? null) !== true) {
            Gateway::fail(403, 'access_denied');
        }
    }

    private function record(string $id): ?array
    {
        $record = $this->principals[$id] ?? null;
        return is_array($record) && is_bool($record['enabled'] ?? null) ? $record : null;
    }

    private function fresh(array $record): bool
    {
        $at = $record['checkedAt'] ?? null;
        $now = time();
        return is_int($at) && $at <= $now && $now - $at < $this->config['privilegeEvidenceSeconds'];
    }

    private function group(array $record, string $kind): bool
    {
        $id = $this->config['groupIds'][$kind] ?? null;
        $groups = $record['groups'] ?? null;
        if (!is_string($id) || !is_array($groups) || !array_is_list($groups) || count($groups) > 128) {
            return false;
        }
        foreach ($groups as $group) {
            if (!is_string($group) || preg_match('/^[A-Za-z0-9_-]{1,128}$/D', $group) !== 1) {
                return false;
            }
        }
        return in_array($id, $groups, true);
    }

    public function authorize(string $actor, string $owner, string $operation): void
    {
        $this->requireActor($actor);
        if ($owner === $actor) {
            return;
        }
        $subject = $this->record($owner);
        $principal = $this->record($actor);
        if ($subject === null || $principal === null || !$this->fresh($principal)
            || in_array($operation, ['settings-read', 'settings-write'], true)) {
            Gateway::fail(403, 'access_denied');
        }
        // All registered owners, including archived/disabled users, for admins.
        if ($this->group($principal, 'admins')) {
            return;
        }
        // Multiple/unknown roles do not count as confirmed student status.
        if ($this->group($principal, 'makerspace') && $this->fresh($subject)
            && $subject['enabled'] === true && ($subject['roles'] ?? null) === ['ROLE_STUDENT']
            && $operation !== 'delete') {
            return;
        }
        Gateway::fail(403, 'access_denied');
    }
}
