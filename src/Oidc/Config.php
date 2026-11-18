<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

use Sso\Layerling\StorageConfig;

final class Config
{
    public const ALGORITHMS = ['RS256'];
    public const LEEWAY = 60;
    public const TRANSACTION_TTL = 300;
    public readonly string $redirectUri;
    public readonly Profile $profile;
    public function __construct(public readonly string $clientId, private readonly string $secret, ?Profile $profile = null,
        public readonly ?string $adminRole = null)
    {
        if (!preg_match('/^[a-zA-Z0-9_-]{1,128}$/D', $clientId)
            || !preg_match('/^[\x21-\x7e]{16,4096}$/D', $secret)
            || ($adminRole !== null && !StorageConfig::roleId($adminRole))) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        $this->profile = $profile ?? Profile::defaults();
        $this->redirectUri = $this->profile->origin . '/auth/callback.php';
    }
    public function clientSecret(): string { return $this->secret; }
    public function scope(): string { return implode(' ', $this->profile->provider['scopes']); }
    public function __debugInfo(): array { return ['clientId' => $this->clientId, 'secret' => '[redacted]']; }

    /** Literal dotenv subset. No shell, expansion, eval, include, or external dotenv package. */
    public static function fromFile(string $path, ?Profile $profile = null): self
    {
        if (!is_file($path) || is_link($path) || filesize($path) > 16384
            || (fileperms($path) & 0077) !== 0) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        $values = [];
        foreach (file($path, FILE_IGNORE_NEW_LINES) as $line) {
            $line = trim($line);
            if ($line === '' || str_starts_with($line, '#')) { continue; }
            if (!preg_match('/^(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=(.*)$/D', $line, $m)) {
                throw new LoginFailed(LoginFailed::CONFIG);
            }
            if (!in_array($m[1], ['SSO_LAYERLING_OIDC_CLIENT_ID', 'SSO_LAYERLING_OIDC_CLIENT_SECRET', 'SSO_LAYERLING_ADMIN_ROLE'], true)) { continue; }
            if (array_key_exists($m[1], $values)) { throw new LoginFailed(LoginFailed::CONFIG); }
            $value = trim($m[2]);
            if (str_starts_with($value, '"') || str_starts_with($value, "'")) {
                $quote = $value[0];
                if (strlen($value) < 2 || !str_ends_with($value, $quote)) { throw new LoginFailed(LoginFailed::CONFIG); }
                $value = substr($value, 1, -1);
                // Quotes contain literal values; escapes/interpolation are deliberately unsupported.
                if (str_contains($value, $quote) || str_contains($value, '\\')) { throw new LoginFailed(LoginFailed::CONFIG); }
            }
            $values[$m[1]] = $value;
        }
        $adminRole = $values['SSO_LAYERLING_ADMIN_ROLE'] ?? '';
        return new self($values['SSO_LAYERLING_OIDC_CLIENT_ID'] ?? '', $values['SSO_LAYERLING_OIDC_CLIENT_SECRET'] ?? '',
            $profile, $adminRole === '' ? null : $adminRole);
    }
}
