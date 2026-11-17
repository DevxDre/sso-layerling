<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

/** Normalized token-free claims. Group labels are for manual diagnosis only. */
final class Claims
{
    public function __construct(public readonly string $uuid, public readonly array $roles,
        public readonly array $groups, public readonly array $groupLabels, public readonly ?string $name,
        public readonly ?string $preferredUsername, public readonly array $classes) {}
    public static function from(Identity $identity): self
    {
        $c = $identity->userinfo + $identity->idToken;
        $uuid = $c['iserv:uuid'] ?? null;
        if (!is_string($uuid) || !preg_match('/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/Di', $uuid)) {
            throw new LoginFailed(LoginFailed::CLAIMS, 'uuid');
        }
        $roles = array_key_exists('iserv:roles', $c) ? $c['iserv:roles'] : [];
        if (!is_array($roles) || !array_is_list($roles) || count($roles) > 100) { throw new LoginFailed(LoginFailed::CLAIMS, 'roles'); }
        $ids = [];
        foreach ($roles as $role) {
            $id = is_array($role) ? ($role['id'] ?? null) : null;
            if (!is_string($id) || !preg_match('/^[A-Za-z0-9_.:-]{1,100}$/D', $id)) { throw new LoginFailed(LoginFailed::CLAIMS, 'roles'); }
            $ids[] = $id;
        }
        $groups = array_key_exists('iserv:groups', $c) ? $c['iserv:groups'] : [];
        if (!is_array($groups) || ($groups !== [] && array_is_list($groups)) || count($groups) > 128) {
            throw new LoginFailed(LoginFailed::CLAIMS, 'groups');
        }
        $labels = [];
        $classes = [];
        foreach ($groups as $key => $group) {
            if (!is_string($key) || !preg_match('/^[A-Za-z0-9_-]{1,128}$/D', $key)
                || !is_array($group) || ($group['id'] ?? null) !== $key) {
                throw new LoginFailed(LoginFailed::CLAIMS, 'groups');
            }
            $labels[$key] = self::text($group['name'] ?? null);
            $account = self::text($group['act'] ?? null);
            if ($account !== null && str_starts_with($account, 'klasse.')) {
                $class = trim(substr($account, strlen('klasse.')));
                if ($class !== '') { $classes[] = $class; }
            }
        }
        $classes = array_values(array_unique($classes));
        usort($classes, 'strnatcasecmp');
        return new self(strtolower($uuid), array_values(array_unique($ids)), array_keys($labels), $labels,
            self::text($c['name'] ?? null), self::text($c['preferred_username'] ?? null), $classes);
    }
    private static function text(mixed $value): ?string
    {
        return is_string($value) && strlen($value) <= 200 && !preg_match('/[\x00-\x1f\x7f]/', $value) ? $value : null;
    }
    public function student(array $configuredGroups, ?string $role): bool
    {
        // Valid nonempty roles take precedence. No teacher/admin/multiple-role fallback.
        if ($this->roles !== []) { return $role !== null && $this->roles === [$role]; }
        return array_intersect($configuredGroups, $this->groups) !== [];
    }
    /** Only explicitly relevant group labels, never a full profile/group dump. */
    public function diagnostic(): array
    {
        $result = [];
        foreach ($this->groupLabels as $id => $name) {
            if (is_string($name) && in_array(strtolower($name), ['admins', 'makerspace-betreuung'], true)) {
                $result[] = ['id' => $id, 'name' => $name];
            }
        }
        return ['roles' => $this->roles, 'relevantGroups' => $result, 'groupCount' => count($this->groups)];
    }
}
