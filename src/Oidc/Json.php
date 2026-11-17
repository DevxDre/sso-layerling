<?php

namespace Sso\Layerling\Oidc;

use JsonException;

final class Json
{
    /** JSON-Objekt als Array; null bei kaputtem JSON, Liste oder Skalar. Große Zahlen bleiben Zeichenketten. */
    public static function object(string $json): array|null
    {
        // nur ein Objekt: eine Liste ([]) ergäbe nach dem Dekodieren ebenfalls ein Array
        if (str_starts_with(ltrim($json), '{') === false) {
            return null;
        }
        try {
            $data = json_decode($json, true, 32, JSON_THROW_ON_ERROR | JSON_BIGINT_AS_STRING);
        } catch (JsonException) {
            return null;
        }

        return is_array($data) === true ? $data : null;
    }
}
