<?php

namespace Sso\Layerling\Oidc;

use Sso\Layerling\Oidc\Http\TransportException;
use Firebase\JWT\JWK;
use Firebase\JWT\Key;
use Throwable;

/**
 * Schlüsselsatz vom konfigurierten JWKS-Endpunkt.
 *
 * Vor JWK::parseKeySet() gefiltert: nur kty RSA, use sig, alg RS256 (IServ setzt alle drei, geprüft 29.10.2026),
 * öffentlicher Schlüssel mit n und e, eindeutige kid. Sonst nähme parseKeySet() auch symmetrische (oct) oder andere
 * Schlüssel an.
 *
 * Geladen wird einmal je Callback und nur, nachdem Code-Tausch und Header-Prüfung des ID-Tokens gelungen sind – also
 * höchstens einmal je verbrauchter Transaktion mit gültigem Code von IServ. Das ist das begrenzte Neuladen: Ein neuer
 * Schlüssel (Schlüsselwechsel) ist beim nächsten Login sofort bekannt, eine unbekannte kid führt ohne weiteren Abruf
 * zum Abbruch. Bewusst kein Zwischenspeicher über Requests: Ist der JWKS nicht abrufbar oder kaputt, schlägt die
 * Anmeldung fehl (L3), statt mit einem alten Stand weiterzulaufen.
 */
final class Jwks
{
    /** @var array<string, Key>|null */
    private array|null $keys = null;

    public function __construct(private \Sso\Layerling\Oidc\Http\Transport $transport, private Profile $profile) {}

    public function key(string $kid): Key
    {
        $this->keys ??= $this->fetch();

        return $this->keys[$kid] ?? throw new LoginFailed(LoginFailed::ID_TOKEN_KEY);
    }

    /** @return array<string, Key> */
    public function keys(): array
    {
        return $this->keys ??= $this->fetch();
    }

    /** @return array<string, Key> */
    private function fetch(): array
    {
        try {
            $response = $this->transport->send('GET', $this->profile->endpoint('jwks'), ['Accept' => 'application/json']);
        } catch (TransportException) {
            throw new LoginFailed(LoginFailed::JWKS, 'transport');
        }
        if ($response->status !== 200) {
            throw new LoginFailed(LoginFailed::JWKS, 'status');
        }
        $data = Json::object($response->body) ?? throw new LoginFailed(LoginFailed::JWKS, 'json');
        $keys = self::filter($data);
        if ($keys === []) {
            throw new LoginFailed(LoginFailed::JWKS, 'empty');
        }

        try {
            return JWK::parseKeySet(['keys' => $keys]);
        } catch (Throwable) {
            throw new LoginFailed(LoginFailed::JWKS, 'parse');
        }
    }

    /**
     * Nur RSA-Signaturschlüssel für RS256 mit eindeutiger kid; mehrdeutige kids fallen ganz heraus.
     * @return list<array<string, mixed>>
     */
    public static function filter(array $jwks): array
    {
        $accepted = [];
        $seen = [];
        foreach (is_array($jwks['keys'] ?? null) === true ? $jwks['keys'] : [] as $jwk) {
            $kid = is_array($jwk) === true ? ($jwk['kid'] ?? null) : null;
            if (is_string($kid) === false || $kid === '' || strlen($kid) > 200) {
                continue;
            }
            $seen[$kid] = ($seen[$kid] ?? 0) + 1;
            if (
                ($jwk['kty'] ?? null) === 'RSA' &&
                ($jwk['use'] ?? null) === 'sig' &&
                ($jwk['alg'] ?? null) === 'RS256' &&
                in_array($jwk['alg'], Config::ALGORITHMS, true) === true &&
                is_string($jwk['n'] ?? null) === true && $jwk['n'] !== '' &&
                is_string($jwk['e'] ?? null) === true && $jwk['e'] !== '' &&
                array_intersect(['d', 'p', 'q', 'dp', 'dq', 'qi', 'oth'], array_keys($jwk)) === []
            ) {
                $accepted[$kid] = ['kty' => 'RSA', 'use' => 'sig', 'alg' => 'RS256', 'kid' => $kid, 'n' => $jwk['n'], 'e' => $jwk['e']];
            }
        }

        return array_values(array_filter($accepted, fn(array $jwk) => $seen[$jwk['kid']] === 1));
    }
}
