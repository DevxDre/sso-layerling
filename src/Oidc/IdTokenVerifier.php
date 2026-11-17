<?php

namespace Sso\Layerling\Oidc;

use Firebase\JWT\BeforeValidException;
use Firebase\JWT\ExpiredException;
use Firebase\JWT\JWT;
use Firebase\JWT\SignatureInvalidException;
use Throwable;

/**
 * Prüft das ID-Token (OIDC Core 3.1.3.7). Die Signatur prüft firebase/php-jwt; alles, was die Bibliothek nicht oder
 * nur bedingt prüft, steht hier (docs/plan-kirby6-login.md, Abschnitt 7):
 * - Header vorher: alg genau RS256, kid vorhanden, kein crit/jku/x5u/jwk (keine Schlüssel-URL aus dem Token),
 * - Schlüssel nur aus dem gefilterten JWKS (Jwks),
 * - exp und iat Pflicht und ganzzahlig (die Bibliothek prüft sie nur, wenn vorhanden, und iat nicht neben nbf),
 * - iss, aud, azp, sub und nonce.
 * JWT::$leeway und JWT::$timestamp (statisch) werden für den Aufruf fest gesetzt und danach zurückgesetzt.
 */
final class IdTokenVerifier
{
    /** IServ-ID-Token mit Gruppen rund 7 KB (Test-Login 29.10.2026) */
    public const MAX_LENGTH = 65536;
    public const FORBIDDEN_HEADERS = ['crit', 'jku', 'x5u', 'jwk'];

    public function __construct(private Config $config, private Jwks $jwks)
    {
    }

    /** @return array<string, mixed> geprüfte Claims */
    public function verify(string $jwt, string $nonce, int $now): array
    {
        if (strlen($jwt) > self::MAX_LENGTH || preg_match('~^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$~D', $jwt) !== 1) {
            throw new LoginFailed(LoginFailed::ID_TOKEN_FORMAT);
        }
        [$headerPart, $claimsPart] = explode('.', $jwt);
        $header = Json::object((string)base64_decode(strtr($headerPart, '-_', '+/'), true))
            ?? throw new LoginFailed(LoginFailed::ID_TOKEN_FORMAT, 'header');

        if (in_array($header['alg'] ?? null, Config::ALGORITHMS, true) === false) {
            throw new LoginFailed(LoginFailed::ID_TOKEN_HEADER, 'alg');
        }
        foreach (self::FORBIDDEN_HEADERS as $name) {
            if (array_key_exists($name, $header) === true) {
                throw new LoginFailed(LoginFailed::ID_TOKEN_HEADER, $name);
            }
        }
        $kid = $header['kid'] ?? null;
        if (is_string($kid) === false || $kid === '') {
            throw new LoginFailed(LoginFailed::ID_TOKEN_HEADER, 'kid');
        }

        $key = $this->jwks->key($kid);

        $leeway = JWT::$leeway;
        $timestamp = JWT::$timestamp;
        JWT::$leeway = Config::LEEWAY;
        JWT::$timestamp = $now;
        try {
            JWT::decode($jwt, [$kid => $key]);
        } catch (SignatureInvalidException) {
            throw new LoginFailed(LoginFailed::ID_TOKEN_SIGNATURE);
        } catch (ExpiredException) {
            // Zeitprüfungen der Bibliothek (nach gültiger Signatur); die eigenen unten wären ebenso gescheitert
            throw new LoginFailed(LoginFailed::ID_TOKEN_CLAIMS, 'exp');
        } catch (BeforeValidException) {
            throw new LoginFailed(LoginFailed::ID_TOKEN_CLAIMS, 'not_yet_valid');
        } catch (Throwable) {
            throw new LoginFailed(LoginFailed::ID_TOKEN_SIGNATURE, 'decode');
        } finally {
            JWT::$leeway = $leeway;
            JWT::$timestamp = $timestamp;
        }

        // Signatur gültig: Claims selbst lesen (Typen wie im Token, nicht die stdClass-Umwandlung der Bibliothek)
        $claims = Json::object((string)base64_decode(strtr($claimsPart, '-_', '+/'), true))
            ?? throw new LoginFailed(LoginFailed::ID_TOKEN_FORMAT, 'claims');
        $this->checkClaims($claims, $nonce, $now);

        return $claims;
    }

    private function checkClaims(array $claims, string $nonce, int $now): void
    {
        $fail = fn(string $claim) => new LoginFailed(LoginFailed::ID_TOKEN_CLAIMS, $claim);

        if (($claims['iss'] ?? null) !== Config::ISSUER) {
            throw $fail('iss');
        }

        $aud = $claims['aud'] ?? null;
        $audiences = is_string($aud) === true ? [$aud] : (is_array($aud) === true && array_is_list($aud) === true ? $aud : null);
        if ($audiences === null || $audiences === [] || count(array_filter($audiences, static fn($a) => is_string($a) && $a !== '')) !== count($audiences) || in_array($this->config->clientId, $audiences, true) === false) {
            throw $fail('aud');
        }
        // mehrere Zielgruppen: azp Pflicht; vorhandenes azp muss in jedem Fall die eigene Client-ID sein
        if ((count($audiences) > 1 || array_key_exists('azp', $claims) === true) && ($claims['azp'] ?? null) !== $this->config->clientId) {
            throw $fail('azp');
        }

        foreach (['exp', 'iat'] as $required) {
            if (is_int($claims[$required] ?? null) === false) {
                throw $fail($required);
            }
        }
        if ($now - Config::LEEWAY >= $claims['exp']) {
            throw $fail('exp');
        }
        if ($claims['exp'] <= $claims['iat'] || $claims['iat'] > $now + Config::LEEWAY) {
            throw $fail('iat');
        }
        if (array_key_exists('nbf', $claims) === true && (is_int($claims['nbf']) === false || $claims['nbf'] > $now + Config::LEEWAY)) {
            throw $fail('nbf');
        }

        $sub = $claims['sub'] ?? null;
        if (is_string($sub) === false || $sub === '' || strlen($sub) > 255) {
            throw $fail('sub');
        }

        if (is_string($claims['nonce'] ?? null) === false || hash_equals($nonce, $claims['nonce']) === false) {
            throw new LoginFailed(LoginFailed::NONCE);
        }
    }
}
