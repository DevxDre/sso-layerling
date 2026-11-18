<?php
declare(strict_types=1);

ini_set('display_errors', '0');
require dirname(__DIR__) . '/vendor/autoload.php';
set_exception_handler(static function (Throwable $error): never {
    \Sso\Layerling\Gateway::fail(503, 'mcp_unavailable');
});
$private = dirname(__DIR__, 2);
$storage = \Sso\Layerling\StorageConfig::load($private . '/app/storage.json');
if (PHP_SAPI !== 'fpm-fcgi' || !$storage->secure) {
    \Sso\Layerling\Gateway::fail(404, 'mcp_unavailable');
}
(new \Sso\Layerling\McpTest($private, $storage))->run();
