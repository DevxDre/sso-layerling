<?php

namespace Sso\Layerling\Oidc;

/**
 * Ergebnis einer vollständig geprüften Anmeldung: (iss, sub) und die Claims aus ID-Token und UserInfo.
 * Enthält keine Codes und Tokens (Access und Refresh Token sind zu diesem Zeitpunkt verworfen).
 * Kontobindung, Rollen und Klassen (Schritt 4) lesen nur hieraus.
 */
final class Identity
{
    public function __construct(
        public readonly string $issuer,
        public readonly string $subject,
        /** @var array<string, mixed> geprüfte Claims des ID-Tokens */
        public readonly array $idToken,
        /** @var array<string, mixed> UserInfo, sub stimmt mit dem ID-Token überein */
        public readonly array $userinfo,
        /** Einstieg und bereinigtes Ziel aus der verbrauchten Transaktion */
        public readonly string $entry,
        public readonly string $target
    ) {
    }
}
