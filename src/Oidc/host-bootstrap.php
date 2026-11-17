<?php
declare(strict_types=1);

// Installed at PRIVATE/app/src/Oidc/host-bootstrap.php, never beneath a DocumentRoot.
require dirname(__DIR__, 2) . '/vendor/autoload.php';
\Sso\Layerling\Oidc\Web::headers();
ini_set('display_errors', '0');
set_exception_handler(static function (\Throwable $e): void {
    // No provider error, request query, token, path or credential is echoed/logged.
    http_response_code(503);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="de"><meta charset="utf-8"><title>Anmeldung nicht abgeschlossen</title><h1>Anmeldung nicht abgeschlossen</h1><p>Bitte die Anmeldung erneut beginnen. Bei wiederholten Fehlern die Betreuung informieren.</p><a href="/index.php">Zur Anmeldung</a></html>';
});
umask(0077);
$private = dirname(__DIR__, 3);
$storagePath = dirname(__DIR__, 2) . '/storage.json';
$storage = is_file($storagePath) ? \Sso\Layerling\StorageConfig::load($storagePath) : null;
return new \Sso\Layerling\Oidc\Web($private,
    \Sso\Layerling\Oidc\Config::fromFile(dirname($private) . '/.env'),
    new \Sso\Layerling\Oidc\Http\CurlTransport(), 'https://cad.example.invalid', $storage);
