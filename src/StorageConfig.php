<?php
declare(strict_types=1);
namespace Sso\Layerling;

/** Explicit, private, packaged configuration. No request/environment overrides. */
final class StorageConfig
{
    public const SCOPE = 'sso-storage-v1';
    public const ABSOLUTE_SECONDS = 140 * 60;
    public const IDLE_SECONDS = 70 * 60;
    public readonly bool $secure;
    public function __construct(public readonly array $values)
    {
        $v=$values;
        $this->secure=is_string($v['origin'] ?? null) && Oidc\Profile::httpsOrigin($v['origin']);
        if (($v['mode']??null)!=='sso-storage-test' || ($v['enabled']??null)!==true
            || ($v['authorizationModel']??null)!=='sso-last-login'
            || (! $this->secure && (!is_string($v['origin']??null) || !preg_match('~^http://127\.0\.0\.1:[1-9][0-9]{0,4}$~D',$v['origin'])))
            || !is_string($v['publicRoot']??null) || !str_starts_with($v['publicRoot'],'/')
            || ($v['absoluteSeconds']??null)!==self::ABSOLUTE_SECONDS || ($v['idleSeconds']??null)!==self::IDLE_SECONDS
            || !is_array($v['groupIds']??null) || !is_array($v['studentGroupIds']??null)
            || !array_is_list($v['studentGroupIds']) || count($v['studentGroupIds'])>128
            || !array_key_exists('studentRoleId', $v)
            || ($v['studentRoleId'] !== null && !self::roleId($v['studentRoleId']))
            || !self::roleIds($v['templatePublisherRoleIds'] ?? null)
            || (isset($v['authorizationMapping']) && !self::mappingId($v['authorizationMapping']))) { throw new \RuntimeException('Invalid storage configuration'); }
        foreach (['makerspace','admins'] as $key) {
            if (!self::id($v['groupIds'][$key]??null)) { throw new \RuntimeException('Invalid storage groups'); }
        }
        if ($v['groupIds']['makerspace']===$v['groupIds']['admins']) { throw new \RuntimeException('Ambiguous storage groups'); }
        foreach ($v['studentGroupIds'] as $id) { if (!self::id($id)) { throw new \RuntimeException('Invalid student group'); } }
    }
    private static function id(mixed $id): bool { return is_string($id)&&preg_match('/^[A-Za-z0-9_-]{1,128}$/D',$id)===1; }
    public static function roleId(mixed $id): bool
    {
        return is_string($id) && preg_match('/^[A-Za-z0-9_.:-]{1,100}$/D', $id) === 1;
    }

    public static function roleIds(mixed $roles): bool
    {
        if (!is_array($roles) || !array_is_list($roles) || count($roles) > 100) { return false; }
        foreach ($roles as $role) {
            if (!self::roleId($role)) { return false; }
        }
        return true;
    }

    public static function mappingId(mixed $id): bool
    {
        return is_string($id) && preg_match('/^[a-f0-9]{64}$/D', $id) === 1;
    }
    public static function load(string $path): self
    {
        if (!is_file($path)||is_link($path)||filesize($path)>16384) { throw new \RuntimeException('Invalid storage configuration'); }
        $values = json_decode((string)file_get_contents($path), true, 32, JSON_THROW_ON_ERROR);
        $metadata = dirname($path, 2) . '/deployment.json';
        if (is_file($metadata) && !is_link($metadata) && filesize($metadata) <= 2 * 1024 * 1024) {
            $installed = json_decode((string)file_get_contents($metadata), true, 32, JSON_THROW_ON_ERROR);
            $values['legacyStudentBasis'] = $installed['legacyStudentBasis'] ?? null;
        }
        return new self($values);
    }
    public function assertRequest(string $private): void
    {
        $v=$this->values; $origin=$v['origin'];
        if (!$this->secure && !(PHP_SAPI==='cli-server' && in_array($_SERVER['REMOTE_ADDR']??'', ['127.0.0.1','::1'],true))) {
            throw new \RuntimeException('Local storage configuration refused');
        }
        $host=parse_url($origin,PHP_URL_HOST).(parse_url($origin,PHP_URL_PORT)?':'.parse_url($origin,PHP_URL_PORT):'');
        $root=realpath($_SERVER['DOCUMENT_ROOT']??''); $resolved=realpath($private);
        if (($_SERVER['HTTP_HOST']??'')!==$host || ($this->secure && !in_array($_SERVER['HTTPS']??'', ['on','1'],true))
            || !$root || $root!==realpath($v['publicRoot']) || !$resolved || $resolved!==$private
            || $resolved===$root || str_starts_with($resolved.'/',$root.'/')) { throw new \RuntimeException('Invalid storage deployment'); }
    }
    public function session(string $private): NativeSession
    {
        return new NativeSession($private, 'sessions', Gateway::COOKIE, $this->secure,
            self::ABSOLUTE_SECONDS, self::IDLE_SECONDS, self::SCOPE);
    }
}
