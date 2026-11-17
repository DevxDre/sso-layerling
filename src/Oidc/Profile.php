<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

/** Private deployment metadata selected at package time. */
final class Profile
{
    public function __construct(
        public readonly string $issuer,
        public readonly string $origin,
        public readonly array $provider,
        public readonly array $diagnosticGroupIds,
        public readonly array $studentGroupIds = [],
        public readonly ?string $studentRoleId = null,
    ) {
        if (!self::httpsOrigin($origin) || !self::httpsOrigin(self::originOf($issuer))
            || !preg_match('~^(?:/(?!/)[A-Za-z0-9._/\~\-]{0,1023})?$~D', substr($issuer, strlen(self::originOf($issuer))))) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
    }

    public static function defaults(): self
    {
        static $default;
        return $default ??= new self('https://login.example.invalid', 'https://cad.example.invalid',
            self::read(dirname(__DIR__, 2) . '/config/oidc-iserv.json'), []);
    }

    public static function load(string $path): self
    {
        $config = self::read($path);
        return new self($config['issuer'], $config['origin'], $config['provider'],
            $config['diagnosticGroupIds'], $config['studentGroupIds'], $config['studentRoleId']);
    }

    private static function read(string $path): array
    {
        if (is_link($path) || !is_file($path) || filesize($path) > 16384) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        return Json::object((string) file_get_contents($path)) ?? throw new LoginFailed(LoginFailed::CONFIG);
    }

    public static function httpsOrigin(string $origin): bool
    {
        return preg_match('~^https://[A-Za-z0-9][A-Za-z0-9.-]*(?::([0-9]{1,5}))?$~D', $origin, $matches) === 1
            && (!isset($matches[1]) || (int)$matches[1] >= 1 && (int)$matches[1] <= 65535);
    }

    private static function originOf(string $issuer): string
    {
        $path = strpos($issuer, '/', strlen('https://'));
        return $path === false ? $issuer : substr($issuer, 0, $path);
    }

    public function issuerOrigin(): string
    {
        return self::originOf($this->issuer);
    }

    public function endpoint(string $name): string
    {
        $path = $this->provider['endpoints'][$name] ?? null;
        if (!is_string($path) || !preg_match('~^/(?!/)[A-Za-z0-9._/\~\-]{0,1023}$~D', $path)) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        return $this->issuerOrigin() . $path;
    }

    public function identityContract(): array
    {
        $mapping = $this->provider['claims']['identity'];
        return [$this->issuer, $mapping['claim'], $mapping['format']];
    }

    public function authorizationMapping(): ?string
    {
        $claims = $this->provider['claims'];
        $default = self::defaults()->provider['claims'];
        $mapping = [$claims['roles'], $claims['groups']];
        // Presentation-only group fields may change without invalidating verified IDs.
        unset($mapping[1]['label'], $mapping[1]['account']);
        unset($default['groups']['label'], $default['groups']['account']);
        if ($mapping == [$default['roles'], $default['groups']]) {
            return null;
        }
        foreach ($mapping as &$fields) { ksort($fields); }
        unset($fields);
        return hash('sha256', json_encode($mapping, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES));
    }
}
