<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

/** Normalized token-free claims. Labels and class names are presentation data. */
final class Claims
{
    public function __construct(
        public readonly string $issuer,
        public readonly string $externalId,
        public readonly array $roles,
        public readonly array $groups,
        public readonly array $groupLabels,
        public readonly ?string $name,
        public readonly ?string $preferredUsername,
        public readonly array $classes,
    ) {}

    public static function from(Identity $identity, ?Profile $profile = null): self
    {
        $profile ??= Profile::defaults();
        $c = $identity->userinfo + $identity->idToken;
        $mapping = $profile->provider['claims'];
        $binding = $mapping['identity'];
        $externalId = $binding['claim'] === 'sub' ? $identity->subject : ($c[$binding['claim']] ?? null);
        $pattern = $binding['format'] === 'uuid'
            ? '/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/Di'
            : '/^[\x21-\x7e]{1,255}$/D';
        if (!is_string($externalId) || !preg_match($pattern, $externalId)) {
            throw new LoginFailed(LoginFailed::CLAIMS, 'identity');
        }
        if ($binding['format'] === 'uuid') {
            $externalId = strtolower($externalId);
        }

        $roles = [];
        foreach (self::collection($c, $mapping['roles'], 100, 'roles') as $value) {
            $role = self::identifier($value, $mapping['roles']);
            if (!is_string($role) || !preg_match('/^[A-Za-z0-9_.:-]{1,100}$/D', $role)) {
                throw new LoginFailed(LoginFailed::CLAIMS, 'roles');
            }
            $roles[] = $role;
        }
        $groups = $labels = $classes = [];
        $groupMapping = $mapping['groups'];
        foreach (self::collection($c, $groupMapping, 128, 'groups') as $key => $value) {
            $id = self::identifier($value, $groupMapping);
            if (!is_string($id) || !preg_match('/^[A-Za-z0-9_-]{1,128}$/D', $id)
                || ($groupMapping['format'] === 'map' && $key !== $id)
                || in_array($id, $groups, true)) {
                throw new LoginFailed(LoginFailed::CLAIMS, 'groups');
            }
            $groups[] = $id;
            $fields = (array) $value;
            $labels[$id] = self::text($fields[$groupMapping['label'] ?? ''] ?? null);
            $account = self::text($fields[$groupMapping['account'] ?? ''] ?? null);
            foreach ($profile->provider['classPrefixes'] as $prefix) {
                if ($account !== null && str_starts_with($account, $prefix)) {
                    $class = trim(substr($account, strlen($prefix)));
                    if ($class !== '') { $classes[] = $class; }
                    break;
                }
            }
        }
        $classes = array_values(array_unique($classes));
        usort($classes, 'strnatcasecmp');
        return new self($identity->issuer, $externalId, array_values(array_unique($roles)), $groups, $labels,
            self::text($c[$mapping['name']] ?? null), self::text($c[$mapping['username']] ?? null), $classes);
    }

    private static function collection(array $claims, array $mapping, int $limit, string $kind): array
    {
        if (!array_key_exists($mapping['claim'], $claims)) {
            return [];
        }
        $value = $claims[$mapping['claim']];
        $expectsList = $mapping['format'] !== 'map';
        if (!$expectsList && $value instanceof \stdClass) {
            $value = (array) $value;
        }
        if (!is_array($value) || count($value) > $limit
            || ($value !== [] && array_is_list($value) !== $expectsList)) {
            throw new LoginFailed(LoginFailed::CLAIMS, $kind);
        }
        return $value;
    }

    private static function identifier(mixed $value, array $mapping): mixed
    {
        if ($mapping['format'] === 'strings') {
            return $value;
        }
        return (is_array($value) || $value instanceof \stdClass) ? ((array) $value)[$mapping['id']] ?? null : null;
    }

    private static function text(mixed $value): ?string
    {
        return is_string($value) && strlen($value) <= 200 && !preg_match('/[\x00-\x1f\x7f]/', $value) ? $value : null;
    }

    public function student(array $configuredGroups, ?string $role): bool
    {
        // Verified nonempty roles take precedence over group fallback.
        if ($this->roles !== []) { return $role !== null && $this->roles === [$role]; }
        return array_intersect($configuredGroups, $this->groups) !== [];
    }

    public function diagnostic(array $groupIds): array
    {
        $result = [];
        foreach ($this->groups as $id) {
            if (in_array($id, $groupIds, true)) {
                $result[] = ['id' => $id, 'name' => $this->groupLabels[$id] ?? $id];
            }
        }
        return ['roles' => $this->roles, 'relevantGroups' => $result, 'groupCount' => count($this->groups)];
    }
}
