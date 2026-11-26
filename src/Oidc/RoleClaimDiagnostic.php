<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

use Sso\Layerling\StorageConfig;
use stdClass;

final class RoleClaimDiagnostic
{
    /** Summarize a rejected role claim without logging role IDs, field names or field values. */
    public static function compare(mixed $idToken, mixed $userInfo, array $mapping): array
    {
        $tokenRoles = self::byId($idToken, $mapping);
        $infoRoles = self::byId($userInfo, $mapping);
        $summary = [
            'idTokenCount' => is_array($idToken) ? count($idToken) : null,
            'userInfoCount' => is_array($userInfo) ? count($userInfo) : null,
            'idTokenIssue' => is_string($tokenRoles) ? $tokenRoles : null,
            'userInfoIssue' => is_string($infoRoles) ? $infoRoles : null,
        ];
        if (is_string($tokenRoles) || is_string($infoRoles)) {
            return $summary;
        }

        // compare() runs only after sameRoleIds() failed (ADR 0003). Only the direction is decision-relevant:
        // which source omits roles the other one grants. Order, names and other fields no longer reject a login.
        return $summary + [
            'roleIdsMatch' => count($tokenRoles) === count($infoRoles) && array_diff_key($tokenRoles, $infoRoles) === [],
            'onlyInIdToken' => count(array_diff_key($tokenRoles, $infoRoles)),
            'onlyInUserInfo' => count(array_diff_key($infoRoles, $tokenRoles)),
        ];
    }

    /**
     * Whether both role claims grant the same set of valid role IDs. Only the IDs are authorization
     * relevant; order, display names (localized by some providers), UUIDs and extra fields are not.
     */
    public static function sameRoleIds(mixed $idToken, mixed $userInfo, array $mapping): bool
    {
        $tokenRoles = self::byId($idToken, $mapping);
        $infoRoles = self::byId($userInfo, $mapping);

        return is_array($tokenRoles) && is_array($infoRoles) && count($tokenRoles) === count($infoRoles)
            && array_diff_key($tokenRoles, $infoRoles) === [];
    }

    /** Compact fixed-vocabulary finding for the login failure page; never contains IDs, names or values. */
    public static function hint(array $summary): ?string
    {
        foreach (['idTokenIssue' => 'token', 'userInfoIssue' => 'userinfo'] as $key => $side) {
            if (is_string($summary[$key] ?? null)) {
                return $side . ':' . $summary[$key];
            }
        }
        if (($summary['roleIdsMatch'] ?? null) !== false) {
            return null;
        }

        return 'ids:' . (int) ($summary['onlyInIdToken'] ?? 0) . '-' . (int) ($summary['onlyInUserInfo'] ?? 0);
    }

    /** Set of the configured technical role IDs, or a fixed issue name. */
    private static function byId(mixed $roles, array $mapping): array|string
    {
        if (!is_array($roles) || !array_is_list($roles) || count($roles) > 100) {
            return 'invalid_role_list';
        }

        $indexed = [];
        foreach ($roles as $role) {
            $fields = $role instanceof stdClass ? (array) $role : [];
            $id = $mapping['format'] === 'strings' ? $role : ($fields[$mapping['id']] ?? null);
            if (!StorageConfig::roleId($id)) {
                return 'invalid_role_id';
            }
            if (isset($indexed[$id])) {
                return 'duplicate_role_id';
            }
            $indexed[$id] = true;
        }

        return $indexed;
    }
}
