<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

/** A user-visible diagnostic made only from fixed failure identifiers. */
final class LoginFailurePage
{
    private const MESSAGES = [
        LoginFailed::TRANSACTION => 'Die Anmeldesitzung ist ungültig oder abgelaufen. Bitte starte die Anmeldung neu.',
        LoginFailed::CONFIG => 'Die Serverkonfiguration für die Anmeldung ist ungültig.',
        LoginFailed::PROVIDER_ERROR => 'Der Anmeldedienst hat die Anmeldung abgebrochen oder eine andere Issuer-Kennung zurückgegeben.',
        LoginFailed::CODE => 'Der Rückruf des Anmeldedienstes enthält keinen gültigen Anmeldecode.',
        LoginFailed::TOKEN_ENDPOINT => 'Der Anmeldedienst hat den Codeaustausch abgelehnt oder war nicht erreichbar.',
        LoginFailed::TOKEN_RESPONSE => 'Die Antwort des Anmeldedienstes beim Codeaustausch ist unvollständig oder ungültig.',
        LoginFailed::ID_TOKEN_FORMAT => 'Das ID-Token hat kein unterstütztes Format.',
        LoginFailed::ID_TOKEN_HEADER => 'Der Header des ID-Tokens ist ungültig oder nicht unterstützt.',
        LoginFailed::JWKS => 'Die Signaturschlüssel des Anmeldedienstes konnten nicht geladen oder gelesen werden.',
        LoginFailed::ID_TOKEN_KEY => 'Für die Token-Signatur wurde kein passender öffentlicher Schlüssel gefunden.',
        LoginFailed::ID_TOKEN_SIGNATURE => 'Die Signatur des ID-Tokens ist ungültig.',
        LoginFailed::ID_TOKEN_CLAIMS => 'Ein erforderlicher oder zeitbezogener Token-Claim ist ungültig.',
        LoginFailed::NONCE => 'Die Anmeldung konnte nicht der gestarteten Browseranfrage zugeordnet werden.',
        LoginFailed::USERINFO => 'Die Kontodaten konnten beim Anmeldedienst nicht gelesen werden.',
        LoginFailed::USERINFO_MISMATCH => 'ID-Token und Kontodaten des Anmeldedienstes passen nicht zusammen.',
        LoginFailed::CLAIMS => 'Ein benötigter Identitäts-, Rollen- oder Gruppen-Claim fehlt oder hat ein unerwartetes Format.',
        LoginFailed::ACCOUNT => 'Das Konto ist deaktiviert oder sein Anmeldestatus ist veraltet.',
        LoginFailed::ACCOUNT_WRITE => 'Der Server konnte den Kontostatus nicht speichern.',
        LoginFailed::ACCOUNT_LOCK => 'Der Server konnte die Kontosperre nicht setzen.',
        LoginFailed::SIGNED_IN => 'In diesem Browser wurde bereits eine andere Anmeldung abgeschlossen.',
        LoginFailed::RATE_LIMIT => 'Zu viele Anmeldeversuche. Bitte warte kurz und starte dann erneut.',
        LoginFailed::SESSION => 'Der Server konnte keine gültige Sitzung erstellen.',
    ];

    public static function render(\Throwable $error): never
    {
        $known = $error instanceof LoginFailed && isset(self::MESSAGES[$error->reason]);
        $reason = $known ? $error->reason : 'internal_error';
        $detail = $known ? $error->detail : null;
        $message = $known ? self::MESSAGES[$reason] : 'Ein unerwarteter Serverfehler hat die Anmeldung verhindert.';
        $code = $reason . ($detail !== null ? ':' . $detail : '');
        $escape = static fn(string $value): string => htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

        http_response_code(503);
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Anmeldung nicht abgeschlossen</title></head>'
            . '<body><main><h1>Anmeldung nicht abgeschlossen</h1><p>' . $escape($message) . '</p>'
            . '<p>Technischer Fehlercode: <code>' . $escape($code) . '</code></p>'
            . '<p>Bitte starte die Anmeldung erneut. Wenn der Fehler wieder auftritt, gib der Betreuung den Fehlercode weiter.</p>'
            . '<a href="/index.php">Zur Anmeldung</a></main></body></html>';
        exit;
    }
}
