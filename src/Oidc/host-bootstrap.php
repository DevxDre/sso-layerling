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
$profile = \Sso\Layerling\Oidc\Profile::load(dirname(__DIR__, 2) . '/oidc-profile.json');
$config = \Sso\Layerling\Oidc\Config::fromFile(dirname($private) . '/.env', $profile);
$targetPath = dirname(__DIR__, 2) . '/deployment-target.json';
$target = !is_link($targetPath) && is_file($targetPath) && filesize($targetPath) <= 16384
    ? \Sso\Layerling\Oidc\Json::object((string) file_get_contents($targetPath))
    : null;
$expectedClient = $target['clientId'] ?? null;
if (!is_string($expectedClient) || ($expectedClient !== '' && !hash_equals($expectedClient, $config->clientId))) {
    throw new \Sso\Layerling\Oidc\LoginFailed(\Sso\Layerling\Oidc\LoginFailed::CONFIG);
}
return new \Sso\Layerling\Oidc\Web($private, $config,
    new \Sso\Layerling\Oidc\Http\CurlTransport($profile), $profile->origin, $storage);
