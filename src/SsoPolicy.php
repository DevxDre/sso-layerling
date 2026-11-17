<?php
declare(strict_types=1);
namespace Sso\Layerling;

/** Last successful SSO login is authoritative; session age is enforced by Gateway. */
final class SsoPolicy
{
    private readonly array $principals;
    private $lock;
    public function __construct(private readonly string $private, private readonly array $config)
    {
        $this->lock=fopen($private.'/authorization.lock','rb');
        if (!$this->lock || !flock($this->lock,LOCK_SH)) { Gateway::fail(503,'authorization_unavailable'); }
        $path=$private.'/principals.json';
        if (is_link($path)||!is_file($path)||filesize($path)>2*1024*1024) { Gateway::fail(503,'authorization_unavailable'); }
        $raw=(string)file_get_contents($path);
        if (!str_starts_with(ltrim($raw), '{')) { Gateway::fail(503,'authorization_unavailable'); }
        $records=json_decode($raw,true,32,JSON_THROW_ON_ERROR);
        if (!is_array($records)||($records!==[]&&array_is_list($records))) { Gateway::fail(503,'authorization_unavailable'); }
        $this->principals=$records;
        if (($config['authorizationModel']??null)!=='sso-last-login'||!is_array($config['groupIds']??null)) { Gateway::fail(503,'invalid_configuration'); }
        foreach(['makerspace','admins']as$key){
            $id=$config['groupIds'][$key]??null;
            if($id!==null&&!self::id($id)){Gateway::fail(503,'invalid_configuration');}
        }
        $maker=$config['groupIds']['makerspace']??null;
        if($maker!==null&&$maker===($config['groupIds']['admins']??null)){Gateway::fail(503,'invalid_configuration');}
        $studentRole=$config['studentRoleId']??null;
        if(($studentRole!==null&&(!is_string($studentRole)||!preg_match('/^[A-Za-z0-9_.:-]{1,100}$/D',$studentRole)))
            || !self::ids($config['studentGroupIds']??null)){Gateway::fail(503,'invalid_configuration');}
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
            ||!is_array($r['roles']??null)||!array_is_list($r['roles'])||count($r['roles'])>100){return null;}
        foreach($r['roles']as$role){
            if(!is_string($role)||!preg_match('/^[A-Za-z0-9_.:-]{1,100}$/D',$role)){return null;}
        }
        // Stored classification is the issuer's decision, never derived from a request.
        // Reject contradictory true classifications as well as malformed records.
        if($r['student']){
            $byRole=$r['roles']!==[]&&($this->config['studentRoleId']??null)!==null
                &&$r['roles']===[$this->config['studentRoleId']];
            $byGroup=$r['roles']===[]&&array_intersect($r['groups'],$this->config['studentGroupIds'])!==[];
            if(!$byRole&&!$byGroup){return null;}
        }
        return $r;
    }
    public function requireActor(string $actor): void
    {
        if(($this->record($actor)['enabled']??null)!==true){Gateway::fail(403,'access_denied');}
    }
    public function templateAccess(string $actor): array
    {
        $this->requireActor($actor);
        $record = $this->record($actor);
        return [
            'teacher' => in_array('ROLE_TEACHER', $record['roles'], true),
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
        return !$matches($rules['deny']) && $matches($rules['allow']);
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
            'isSelf' => $actor === $id, 'canWrite' => true, 'canDelete' => $this->allowed($actor, $id, 'delete')];
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
