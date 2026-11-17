<?php

namespace Sso\Layerling\Oidc;

use Sso\Layerling\Oidc\Http\HttpResponse;
use Sso\Layerling\Oidc\Http\TransportException;

/**
 * OIDC-Client für IServ: Autorisierungs-Adresse, Code-Tausch (client_secret_post, PKCE), ID-Token-Prüfung und
 * UserInfo – nur über die festen Adressen aus Config und den explizit injizierten Transport.
 * Access Token wird nur für den UserInfo-Abruf benutzt, Refresh Token sofort verworfen; nichts davon wird gespeichert.
 */
final class OidcClient
{
    /** Claims, die in ID-Token und UserInfo übereinstimmen müssen, wenn beide sie enthalten */
    public const CONSISTENT_CLAIMS = ['iss', 'aud', 'iserv:uuid', 'iserv:roles', 'iserv:groups'];

    public function __construct(private Config $config, private \Sso\Layerling\Oidc\Http\Transport $transport, private \Closure $clock)
    {
    }

    public function authorizationUrl(Transaction $transaction): string
    {
        return Config::AUTHORIZE_URL . '?' . http_build_query([
            'response_type' => 'code',
            'client_id' => $this->config->clientId,
            'redirect_uri' => $this->config->redirectUri,
            'scope' => $this->config->scope(),
            'state' => $transaction->state,
            'nonce' => $transaction->nonce,
            'code_challenge' => $transaction->challenge(),
            'code_challenge_method' => 'S256',
        ], '', '&', PHP_QUERY_RFC3986);
    }

    /** Code gegen Tokens tauschen und alles prüfen; wirft LoginFailed */
    public function complete(Transaction $transaction, string $code): Identity
    {
        $tokens = $this->exchange($transaction, $code);
        $now = ($this->clock)();
        $claims = (new IdTokenVerifier($this->config, new Jwks($this->transport)))->verify($tokens['id_token'], $transaction->nonce, $now);
        if (array_key_exists('at_hash', $claims)) {
            $expected = rtrim(strtr(base64_encode(substr(hash('sha256', $tokens['access_token'], true), 0, 16)), '+/', '-_'), '=');
            if (!is_string($claims['at_hash']) || !hash_equals($expected, $claims['at_hash'])) {
                throw new LoginFailed(LoginFailed::ID_TOKEN_CLAIMS, 'at_hash');
            }
        }
        $userinfo = $this->userinfo($tokens['access_token'], $claims);

        return new Identity(Config::ISSUER, $claims['sub'], $claims, $userinfo, $transaction->entry, $transaction->target);
    }

    /** @return array{id_token: string, access_token: string} */
    private function exchange(Transaction $transaction, string $code): array
    {
        try {
            $response = $this->transport->send('POST', Config::TOKEN_URL, ['Accept' => 'application/json'], [
                'grant_type' => 'authorization_code',
                'code' => $code,
                'redirect_uri' => $transaction->redirectUri,
                'client_id' => $this->config->clientId,
                'client_secret' => $this->config->clientSecret(),
                'code_verifier' => $transaction->verifier,
            ]);
        } catch (TransportException) {
            throw new LoginFailed(LoginFailed::TOKEN_ENDPOINT, 'transport');
        }
        if ($response->status !== 200) {
            throw new LoginFailed(LoginFailed::TOKEN_ENDPOINT, self::oauthError($response) ?? 'status');
        }

        $data = Json::object($response->body) ?? throw new LoginFailed(LoginFailed::TOKEN_RESPONSE, 'json');
        // Refresh Token nie weiterreichen (im IServ-Client nur „Autorisierungs-Code“ erlauben)
        unset($data['refresh_token']);

        if (is_string($data['token_type'] ?? null) === false || strcasecmp($data['token_type'], 'Bearer') !== 0) {
            throw new LoginFailed(LoginFailed::TOKEN_RESPONSE, 'token_type');
        }
        if (is_string($data['access_token'] ?? null) === false || preg_match('~^[\x21-\x7E]{1,4096}$~D', $data['access_token']) !== 1) {
            throw new LoginFailed(LoginFailed::TOKEN_RESPONSE, 'access_token');
        }
        if (is_string($data['id_token'] ?? null) === false) {
            throw new LoginFailed(LoginFailed::TOKEN_RESPONSE, 'id_token');
        }

        return ['id_token' => $data['id_token'], 'access_token' => $data['access_token']];
    }

    /** UserInfo vom festen Endpunkt; sub und die übrigen gemeinsamen Claims müssen zum ID-Token passen */
    private function userinfo(string $accessToken, array $claims): array
    {
        try {
            $response = $this->transport->send('GET', Config::USERINFO_URL, [
                'Accept' => 'application/json',
                'Authorization' => 'Bearer ' . $accessToken,
            ]);
        } catch (TransportException) {
            throw new LoginFailed(LoginFailed::USERINFO, 'transport');
        }
        if ($response->status !== 200) {
            throw new LoginFailed(LoginFailed::USERINFO, 'status');
        }
        $userinfo = Json::object($response->body) ?? throw new LoginFailed(LoginFailed::USERINFO, 'json');

        if (is_string($userinfo['sub'] ?? null) === false || hash_equals($claims['sub'], $userinfo['sub']) === false) {
            throw new LoginFailed(LoginFailed::USERINFO_MISMATCH, 'sub');
        }
        foreach (self::CONSISTENT_CLAIMS as $name) {
            if (array_key_exists($name, $claims) === true && array_key_exists($name, $userinfo) === true && $claims[$name] !== $userinfo[$name]) {
                throw new LoginFailed(LoginFailed::USERINFO_MISMATCH, $name);
            }
        }

        return $userinfo;
    }

    /** OAuth-Fehlercode der Antwort (nur der registrierte Bezeichner, keine error_description) */
    private static function oauthError(HttpResponse $response): string|null
    {
        $error = Json::object($response->body)['error'] ?? null;

        return is_string($error) === true && preg_match('~^[a-z_]{1,40}$~D', $error) === 1 ? $error : null;
    }
}
