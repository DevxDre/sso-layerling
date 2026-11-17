<?php

namespace Sso\Layerling\Oidc\Http;

use Sso\Layerling\Oidc\Profile;

/**
 * Produktiver Transport: nur die festen Adressen aus Config, nur HTTPS mit Zertifikats- und Hostprüfung, keine
 * Weiterleitungen, Zeit- und Größenlimit. Fehler als TransportException mit curl-Fehlernummer, ohne Antwortinhalt.
 */
final class CurlTransport implements Transport
{
    public function __construct(private readonly Profile $profile) {}
    public const CONNECT_TIMEOUT = 5;
    public const TIMEOUT = 10;
    public const MAX_BYTES = 1048576;

    public function send(string $method, string $url, array $headers = [], array|null $form = null): HttpResponse
    {
        // Header zuerst: Werte (z. B. das Access Token) dürfen keine weiteren Header einschleusen
        $lines = [];
        foreach ($headers as $name => $value) {
            if (preg_match('~^[A-Za-z0-9-]+$~D', $name) !== 1 || preg_match('~[\r\n\0]~', $value) === 1) {
                throw new TransportException('ungültiger Header');
            }
            $lines[] = $name . ': ' . $value;
        }
        $allowed = $method === 'POST' ? [$this->profile->endpoint('token')]
            : [$this->profile->endpoint('userinfo'), $this->profile->endpoint('jwks')];
        if (!in_array($url, $allowed, true) || !in_array($method, ['GET', 'POST'], true)) {
            throw new TransportException('Adresse oder Methode nicht erlaubt');
        }
        if (function_exists('curl_init') === false) {
            throw new TransportException('curl fehlt');
        }

        $body = '';
        $tooLarge = false;
        $responseHeaders = [];
        $curl = curl_init();
        curl_setopt_array($curl, [
            CURLOPT_URL => $url,
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_CONNECTTIMEOUT => self::CONNECT_TIMEOUT,
            CURLOPT_TIMEOUT => self::TIMEOUT,
            CURLOPT_HTTPHEADER => $lines,
            CURLOPT_USERAGENT => 'sso-layerling-sso-test',
            CURLOPT_MAXFILESIZE => self::MAX_BYTES,
            CURLOPT_HEADERFUNCTION => function ($curl, string $line) use (&$responseHeaders): int {
                if (str_starts_with($line, 'HTTP/') === true) {
                    $responseHeaders = [];
                } elseif (str_contains($line, ':') === true) {
                    [$name, $value] = explode(':', $line, 2);
                    $responseHeaders[strtolower(trim($name))] = trim($value);
                }
                return strlen($line);
            },
            // Größenlimit auch ohne Content-Length (chunked): Abbruch, sobald mehr kommt
            CURLOPT_WRITEFUNCTION => function ($curl, string $chunk) use (&$body, &$tooLarge): int {
                if (strlen($body) + strlen($chunk) > self::MAX_BYTES) {
                    $tooLarge = true;
                    return 0;
                }
                $body .= $chunk;
                return strlen($chunk);
            },
        ]);
        // nur HTTPS (CURLOPT_PROTOCOLS_STR erst ab libcurl 7.85)
        defined('CURLOPT_PROTOCOLS_STR') === true
            ? curl_setopt($curl, CURLOPT_PROTOCOLS_STR, 'https')
            : curl_setopt($curl, CURLOPT_PROTOCOLS, CURLPROTO_HTTPS);
        if ($method === 'POST') {
            curl_setopt($curl, CURLOPT_POST, true);
            curl_setopt($curl, CURLOPT_POSTFIELDS, http_build_query($form ?? [], '', '&'));
        }

        if (curl_exec($curl) === false) {
            throw new TransportException($tooLarge === true ? 'Antwort zu groß' : 'curl-Fehler ' . curl_errno($curl));
        }

        return new HttpResponse((int)curl_getinfo($curl, CURLINFO_RESPONSE_CODE), $responseHeaders, $body);
    }
}
