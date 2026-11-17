<?php

namespace Sso\Layerling\Oidc\Http;

/**
 * HTTP zum Anbieter: Token-Abruf, UserInfo und JWKS – nur die festen Adressen aus Config.
 * In Produktion CurlTransport, im Test (scripts/login-test.php) ein Fixture-Anbieter ohne Netz.
 */
interface Transport
{
    /**
     * @param 'GET'|'POST' $method
     * @param array<string, string> $headers z. B. Accept, Authorization
     * @param array<string, string>|null $form POST-Daten (application/x-www-form-urlencoded)
     * @throws TransportException bei Netz-, TLS-, Zeit- oder Größenfehlern – die Anmeldung schlägt dann fehl
     */
    public function send(string $method, string $url, array $headers = [], array|null $form = null): HttpResponse;
}
