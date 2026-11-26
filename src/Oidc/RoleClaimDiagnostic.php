<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

use Sso\Layerling\StorageConfig;
use stdClass;

final class RoleClaimDiagnostic
{
    /** Summarize a rejected comparison without logging role IDs, field names or field values. */
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

        $summary['roleIdsMatch'] = count($tokenRoles) === count($infoRoles) && array_diff_key($tokenRoles, $infoRoles) === [];
        if (!$summary['roleIdsMatch']) {
            // Only the direction is decision-relevant: which source omits roles the other one grants.
            return $summary + [
                'onlyInIdToken' => count(array_diff_key($tokenRoles, $infoRoles)),
                'onlyInUserInfo' => count(array_diff_key($infoRoles, $tokenRoles)),
            ];
        }

        $summary['roleOrderMatches'] = array_keys($tokenRoles) === array_keys($infoRoles);
        $fieldNamesMatch = $fieldOrderMatches = true;
        $valueDifferences = 0;
        $first = null;
        $position = 0;
        foreach ($tokenRoles as $id => $tokenFields) {
            $position++;
            $infoFields = $infoRoles[$id];
            $fieldNamesMatch = $fieldNamesMatch && count($tokenFields) === count($infoFields)
                && array_diff_key($tokenFields, $infoFields) === [];
            $fieldOrderMatches = $fieldOrderMatches && array_keys($tokenFields) === array_keys($infoFields);
            foreach (array_intersect_key($tokenFields, $infoFields) as $key => $value) {
                if (serialize($value) === serialize($infoFields[$key])) {
                    continue;
                }
                $valueDifferences++;
                $first ??= ['position' => $position, 'roles' => count($tokenRoles),
                    'field' => self::FIELDS[$key] ?? 'other', 'kind' => self::kind($value, $infoFields[$key])];
            }
        }

        return $summary + [
            'fieldNamesMatch' => $fieldNamesMatch,
            'fieldOrderMatches' => $fieldNamesMatch ? $fieldOrderMatches : null,
            'sharedFieldValuesMatch' => $valueDifferences === 0,
        ] + ($first === null ? [] : ['valueDifferences' => $valueDifferences, 'firstValueDifference' => $first]);
    }

    /** Known provider field names may be reported; every other field name is reported as "other". */
    private const FIELDS = ['uuid' => 'uuid', 'displayName' => 'displayname'];

    /** How two values differ, without revealing either value. */
    private static function kind(mixed $token, mixed $info): string
    {
        if (!is_string($token) || !is_string($info)) {
            return get_debug_type($token) !== get_debug_type($info) ? 'type' : 'value';
        }
        if (class_exists(\Normalizer::class)) {
            $token = \Normalizer::normalize($token, \Normalizer::FORM_C);
            $info = \Normalizer::normalize($info, \Normalizer::FORM_C);
            if (!is_string($token) || !is_string($info)) {
                return 'text';
            }
            if ($token === $info) {
                return 'unicode';
            }
        }
        $token = trim($token);
        $info = trim($info);
        if ($token === $info) {
            return 'space';
        }
        $lower = static fn(string $value): string => function_exists('mb_strtolower') ? mb_strtolower($value, 'UTF-8') : strtolower($value);

        return $lower($token) === $lower($info) ? 'case' : 'text';
    }

    /** Compact fixed-vocabulary finding for the login failure page; never contains IDs, names or values. */
    public static function hint(array $summary): string
    {
        foreach (['idTokenIssue' => 'token', 'userInfoIssue' => 'userinfo'] as $key => $side) {
            if (is_string($summary[$key] ?? null)) {
                return $side . ':' . $summary[$key];
            }
        }
        if (($summary['roleIdsMatch'] ?? null) !== true) {
            return 'ids:' . (int) ($summary['onlyInIdToken'] ?? 0) . '-' . (int) ($summary['onlyInUserInfo'] ?? 0);
        }
        $differences = [];
        foreach (['roleOrderMatches' => 'order', 'fieldNamesMatch' => 'fields',
            'fieldOrderMatches' => 'field-order', 'sharedFieldValuesMatch' => 'values'] as $key => $label) {
            if (($summary[$key] ?? null) === false) {
                $differences[] = $label;
            }
        }

        $hint = 'same-ids:' . ($differences === [] ? 'other' : implode('+', $differences));
        $first = $summary['firstValueDifference'] ?? null;
        if (is_array($first)) {
            // e.g. same-ids:values:displayname:case:2-3 = first differing value in role 2 of 3
            $hint .= ':' . $first['field'] . ':' . $first['kind'] . ':' . (int) $first['position'] . '-' . (int) $first['roles'];
        }

        return $hint;
    }

    /** Index roles temporarily by their configured technical ID. */
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
            $indexed[$id] = $fields;
        }

        return $indexed;
    }
}
