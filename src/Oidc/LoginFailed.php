<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

/** Only fixed identifiers; no provider payload or secret in exception messages. */
final class LoginFailed extends \RuntimeException
{
    public const TRANSACTION='transaction', CONFIG='config', PROVIDER_ERROR='provider_error', CODE='code',
        TOKEN_ENDPOINT='token_endpoint', TOKEN_RESPONSE='token_response', ID_TOKEN_FORMAT='id_token_format',
        ID_TOKEN_HEADER='id_token_header', JWKS='jwks', ID_TOKEN_KEY='id_token_key',
        ID_TOKEN_SIGNATURE='id_token_signature', ID_TOKEN_CLAIMS='id_token_claims', NONCE='nonce',
        USERINFO='userinfo', USERINFO_MISMATCH='userinfo_mismatch', CLAIMS='claims',
        ACCOUNT='account', ACCOUNT_WRITE='account_write', ACCOUNT_LOCK='account_lock',
        SIGNED_IN='signed_in', RATE_LIMIT='rate_limit', SESSION='session';
    public function __construct(public readonly string $reason, ?string $detail = null)
    {
        $this->detail = $detail !== null && preg_match('/^[a-z0-9_:.-]{1,64}$/iD', $detail) === 1
            ? $detail : null;
        parent::__construct('Login failed: ' . $reason . ($this->detail !== null ? ':' . $this->detail : ''));
    }

    public readonly ?string $detail;
}
