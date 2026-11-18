<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

/** Single atomic registry, serialized with the same lock as storage authorization. */
final class PrincipalWriter
{
    public function __construct(private string $private) {}
    public function write(Claims $claims, int $sequence, int $now, array $studentGroups = [], ?string $studentRole = null, ?string $authorizationMapping = null): string
    {
        $lock = fopen($this->private . '/authorization.lock', 'c+b');
        if (!$lock || !flock($lock, LOCK_EX)) { throw new LoginFailed(LoginFailed::ACCOUNT_LOCK); }
        try {
            $file = $this->private . '/principals.json';
            $records = Json::object((string)file_get_contents($file)) ?? throw new LoginFailed(LoginFailed::ACCOUNT_WRITE);
            $binding = hash('sha256', $claims->issuer . "\0" . $claims->externalId);
            $owner = null;
            foreach ($records as $id => $record) {
                if (($record['identityHash'] ?? null) === $binding) {
                    if ($owner !== null || !preg_match('/^[a-f0-9]{32}$/D', $id)) { throw new LoginFailed(LoginFailed::ACCOUNT); }
                    $owner = $id;
                }
            }
            $owner ??= bin2hex(random_bytes(16));
            $old = $records[$owner] ?? null;
            if ($old !== null && (($old['enabled'] ?? null) !== true || ($old['loginSequence'] ?? PHP_INT_MAX) >= $sequence)) {
                throw new LoginFailed(LoginFailed::ACCOUNT, 'stale_or_disabled');
            }
            $records[$owner] = ['identityHash' => $binding, 'enabled' => true, 'groups' => $claims->groups,
                'roles' => $claims->roles, 'groupAccounts' => $claims->groupAccounts,
                'groupLabels' => $claims->groupLabels, 'student' => $claims->student($studentGroups, $studentRole),
                'studentBasis' => ['role' => $studentRole, 'groups' => array_values(array_intersect($studentGroups, $claims->groups))],
                'authorizationMapping' => $authorizationMapping,
                'name' => $claims->name, 'classes' => $claims->classes, 'checkedAt' => $now, 'loginSequence' => $sequence];
            $tmp = tempnam($this->private, '.principals-');
            try {
                if ($tmp === false || file_put_contents($tmp, json_encode((object)$records, JSON_THROW_ON_ERROR)) === false
                    || !rename($tmp, $file)) { throw new LoginFailed(LoginFailed::ACCOUNT_WRITE); }
            } finally { if (is_string($tmp) && file_exists($tmp)) { unlink($tmp); } }
            return $owner;
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
}
