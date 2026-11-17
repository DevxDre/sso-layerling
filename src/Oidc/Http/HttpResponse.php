<?php

namespace Sso\Layerling\Oidc\Http;

/** Antwort des Anbieters; Header-Namen klein geschrieben */
final class HttpResponse
{
    /** @param array<string, string> $headers */
    public function __construct(
        public readonly int $status,
        public readonly array $headers,
        public readonly string $body
    ) {
    }
}
