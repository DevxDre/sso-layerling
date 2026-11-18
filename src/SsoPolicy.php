<?php
declare(strict_types=1);
namespace Sso\Layerling;

/** Last successful SSO login is authoritative; session age is enforced by Gateway. */
final class SsoPolicy
{
    private readonly array $principals;
    private $lock;
    private readonly PermissionRules $permissions;
    public function __construct(private readonly string $private, private readonly array $config, private readonly bool $editPermissions = false)
    {
        $this->lock=fopen($private.'/authorization.lock', $editPermissions ? 'r+b' : 'rb');
        if (!$this->lock || !flock($this->lock, $editPermissions ? LOCK_EX : LOCK_SH)) { Gateway::fail(503,'authorization_unavailable'); }
        $path=$private.'/principals.json';
        if (is_link($path)||!is_file($path)||filesize($path)>2*1024*1024) { Gateway::fail(503,'authorization_unavailable'); }
        $raw=(string)file_get_contents($path);
        if (!str_starts_with(ltrim($raw), '{')) { Gateway::fail(503,'authorization_unavailable'); }
        $records=json_decode($raw,true,32,JSON_THROW_ON_ERROR);
        if (!is_array($records)||($records!==[]&&array_is_list($records))) { Gateway::fail(503,'authorization_unavailable'); }
        $this->principals=$records;
        $this->permissions = new PermissionRules($private . '/permissions.json');
        if (($config['authorizationModel']??null)!=='sso-last-login'||!is_array($config['groupIds']??null)) { Gateway::fail(503,'invalid_configuration'); }
        foreach(['makerspace','admins']as$key){
            $id=$config['groupIds'][$key]??null;
            if($id!==null&&!self::id($id)){Gateway::fail(503,'invalid_configuration');}
        }
        $maker=$config['groupIds']['makerspace']??null;
        if($maker!==null&&$maker===($config['groupIds']['admins']??null)){Gateway::fail(503,'invalid_configuration');}
        $studentRole=$config['studentRoleId']??null;
        if (($studentRole !== null && !StorageConfig::roleId($studentRole))
            || !self::ids($config['studentGroupIds'] ?? null)
            || (array_key_exists('templatePublisherRoleIds', $config) && !StorageConfig::roleIds($config['templatePublisherRoleIds']))){Gateway::fail(503,'invalid_configuration');}
    }
    private static function id(mixed $id): bool {return is_string($id)&&preg_match('/^[A-Za-z0-9_-]{1,128}$/D',$id)===1;}
    private static function ids(mixed $ids): bool
    {
        if(!is_array($ids)||!array_is_list($ids)||count($ids)>128){return false;}
        foreach($ids as$id){if(!self::id($id)){return false;}}
        return true;
    }
    private function record(string $id): ?array
    {
        $r=$this->principals[$id]??null;
        if(!is_array($r)||!is_bool($r['enabled']??null)||!is_bool($r['student']??null)
            ||!is_string($r['identityHash']??null)||!preg_match('/^[a-f0-9]{64}$/D',$r['identityHash'])
            ||!is_int($r['loginSequence']??null)||$r['loginSequence']<1
            ||!is_int($r['checkedAt']??null)||$r['checkedAt']<1||$r['checkedAt']>time()
            ||!self::ids($r['groups']??null)
            || !StorageConfig::roleIds($r['roles'] ?? null)
            || (isset($r['authorizationMapping']) && !StorageConfig::mappingId($r['authorizationMapping']))) { return null; }
        if ($r['student']) {
            $basis = $r['studentBasis'] ?? $this->config['legacyStudentBasis'] ?? [
                'role' => $this->config['studentRoleId'] ?? null, 'groups' => $this->config['studentGroupIds'],
            ];
            if (!is_array($basis) || !self::ids($basis['groups'] ?? null)
                || (isset($basis['role']) && !StorageConfig::roleId($basis['role']))) { return null; }
            $byRole = $r['roles'] !== [] && isset($basis['role']) && $r['roles'] === [$basis['role']];
            $byGroup = $r['roles'] === [] && array_intersect($r['groups'], $basis['groups']) !== [];
            if (!$byRole && !$byGroup) { return null; }
        }
        // Normalization changes require a new login before roles/groups can grant current privileges.
        if (($r['authorizationMapping'] ?? null) !== ($this->config['authorizationMapping'] ?? null)) {
            $r['roles'] = $r['groups'] = $r['groupAccounts'] = $r['groupLabels'] = [];
        }
        return $r;
    }
    public function requireActor(string $actor): void
    {
        if(($this->record($actor)['enabled']??null)!==true){Gateway::fail(403,'access_denied');}
    }
    public function isPermissionsAdmin(string $actor, ?string $role): bool
    {
        $record = $this->record($actor);
        return $role !== null && ($record['enabled'] ?? null) === true && in_array($role, $record['roles'], true);
    }

    public function permissionSettings(): array
    {
        $selectors = [];
        $groups = [];
        foreach (array_keys($this->principals) as $id) {
            $record = $this->record((string) $id);
            foreach ($record['roles'] ?? [] as $role) {
                $selectors['role:' . $role] = '';
            }
            foreach ($record['groups'] ?? [] as $group) {
                if ($record['loginSequence'] > ($groups[$group]['sequence'] ?? 0)) {
                    $account = $record['groupAccounts'][$group] ?? null;
                    $label = $record['groupLabels'][$group] ?? null;
                    $groups[$group] = [
                        'sequence' => $record['loginSequence'],
                        'account' => is_string($account) ? $account : '',
                        'label' => is_string($label) ? $label : '',
                    ];
                }
            }
        }

        $accountCounts = array_count_values(array_column($groups, 'account'));
        $groupNames = [];
        foreach ($groups as $id => $group) {
            $selector = 'group:' . $id;
            $account = $group['account'];
            if ($account !== '' && $accountCounts[$account] === 1) {
                $groupNames[$selector] = 'groups:' . $account;
            }
            $selectors[$groupNames[$selector] ?? $selector] = $group['label'];
        }
        ksort($selectors, SORT_NATURAL);
        ksort($groupNames, SORT_STRING);
        return [$this->permissions->rules(), $this->permissions->patterns(), $selectors, $groupNames];
    }

    public function changePermissions(array $form, array $groupNames): bool
    {
        if (!$this->editPermissions) {
            throw new \LogicException('Permission update requires exclusive lock');
        }
        if (($form['action'] ?? null) === 'save-rule') {
            $submittedVersion = $form['groupNamesVersion'] ?? null;
            foreach (['actor', 'owner'] as $field) {
                $value = $form[$field] ?? null;
                if (is_string($value) && str_starts_with($value, 'groups:')) {
                    $selector = array_search($value, $groupNames, true);
                    if ($selector === false || $submittedVersion !== self::groupNamesVersion($groupNames)) {
                        return false;
                    }
                    $form[$field] = $selector;
                }
            }
        }
        return $this->permissions->change($form);
    }

    public static function groupNamesVersion(array $groupNames): string
    {
        return hash('sha256', json_encode($groupNames, JSON_THROW_ON_ERROR));
    }

    public function templateAccess(string $actor): array
    {
        $this->requireActor($actor);
        $record = $this->record($actor);
        return [
            'teacher' => $this->permissions->decision('publish', $record)
                ?? (array_intersect($record['roles'], $this->config['templatePublisherRoleIds'] ?? []) !== []),
            'publishGroups' => $this->permissions->templateGroups($record),
            'labels' => $record['groupLabels'] ?? [],
            'student' => $record['student'],
            'groups' => $record['groups'],
        ];
    }

    public function allowsMcpTest(string $actor, array $rules): bool
    {
        $record = $this->record($actor);
        if (($record['enabled'] ?? null) !== true) {
            return false;
        }
        $matches = static fn(array $rule): bool => in_array($actor, $rule['accounts'], true)
            || array_intersect($record['roles'], $rule['roles']) !== []
            || array_intersect($record['groups'], $rule['groups']) !== [];
        return $this->permissions->decision('mcp', $record)
            ?? (!$matches($rules['deny']) && $matches($rules['allow']));
    }
    private function group(array $record,string $kind): bool
    {
        $id=$this->config['groupIds'][$kind]??null;
        return is_string($id)&&in_array($id,$record['groups'],true);
    }
    private function allowed(string $actor, string $owner, string $operation): bool
    {
        if ($actor === $owner) { return true; }
        $subject = $this->record($owner);
        $principal = $this->record($actor);
        if ($subject === null || $principal === null || in_array($operation, ['settings-read','settings-write'], true)) { return false; }
        $decision = $this->permissions->decision($operation, $principal, $subject);
        if ($decision !== null) { return $decision; }
        if ($this->group($principal, 'admins')) { return true; }
        return $this->group($principal, 'makerspace') && $subject['enabled'] && $subject['student'] && $operation !== 'delete';
    }
    public function authorize(string $actor, string $owner, string $operation): void
    {
        $this->requireActor($actor);
        if (!$this->allowed($actor, $owner, $operation)) { Gateway::fail(403, 'access_denied'); }
    }
    private function ownerRecord(string $actor, string $id): ?array
    {
        if (!preg_match('/^[a-f0-9]{32}$/D', $id)
            || $this->record($id) === null || !$this->allowed($actor, $id, 'read')) {
            return null;
        }
        $name = $this->principals[$id]['name'] ?? null;
        if (!is_string($name) || trim($name) === '' || strlen($name) > 200 || preg_match('/[\x00-\x1f\x7f]/', $name)) {
            $name = null;
        }
        $classes = $this->principals[$id]['classes'] ?? [];
        if (!is_array($classes) || !array_is_list($classes)) { $classes = []; }
        $classes = array_values(array_filter($classes, static fn($value) =>
            is_string($value) && $value !== '' && strlen($value) <= 200 && !preg_match('/[\x00-\x1f\x7f]/', $value)));
        $label = $name ?? 'Nutzer ' . substr($id, 0, 8);
        return ['userId' => $id, 'label' => $actor === $id ? 'Mein Speicher' : $label,
            'name' => $name, 'classes' => $classes,
            'isSelf' => $actor === $id, 'canWrite' => $this->allowed($actor, $id, 'write'), 'canDelete' => $this->allowed($actor, $id, 'delete')];
    }

    public function owner(string $actor, mixed $selected): array
    {
        $this->requireActor($actor);
        if (!is_string($selected) || !preg_match('/^[a-f0-9]{32}$/D', $selected)) {
            Gateway::fail(400, 'invalid_owner');
        }
        return $this->ownerRecord($actor, $selected) ?? Gateway::fail(403, 'access_denied');
    }

    /** The same authorization snapshot governs owner discovery and file operations. */
    public function owners(string $actor, bool $withActivity = false): array
    {
        $this->requireActor($actor);
        $owners = [];
        $now = time();
        foreach (array_keys($this->principals) as $id) {
            if (!is_string($id)) {
                continue;
            }
            $owner = $this->ownerRecord($actor, $id);
            if ($owner !== null) {
                if ($withActivity && !$owner['isSelf']) {
                    $owner['recentProjectSave'] = ProjectActivity::recent($this->private, $id, $now);
                }
                $owners[] = $owner;
            }
        }
        usort($owners, static fn($a, $b) => ($b['isSelf'] <=> $a['isSelf']) ?: strnatcasecmp($a['label'], $b['label']));
        return $owners;
    }
}
