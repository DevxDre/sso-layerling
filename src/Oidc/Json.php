<?php

namespace Sso\Layerling\Oidc;

use JsonException;

final class Json
{
    /** JSON-Objekt als Array; null bei kaputtem JSON, Liste oder Skalar. */
    public static function object(string $json, bool $preserveObjects = false): array|null
    {
        // nur ein Objekt: eine Liste ([]) ergäbe nach dem Dekodieren ebenfalls ein Array
        if (str_starts_with(ltrim($json), '{') === false) {
            return null;
        }
        try {
            $data = json_decode($json, !$preserveObjects, 32, JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return null;
        }

        return is_array($data) || $data instanceof \stdClass ? (array) $data : null;
    }
}
