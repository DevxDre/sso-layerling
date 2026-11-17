<?php
declare(strict_types=1);

// Router for the loopback CAD test runtime. It is never copied into a hosted package.
if (PHP_SAPI !== 'cli-server' || ($_SERVER['REMOTE_ADDR'] ?? null) !== '127.0.0.1') {
    http_response_code(404);
    exit;
}
define('SSO_LAYERLING_MCP_TEST_ROUTER', true);
if (parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH) !== '/api/layerling-mcp') {
    return false;
}
ini_set('display_errors', '0');
$private = dirname($_SERVER['DOCUMENT_ROOT']) . '/private';
require $private . '/app/vendor/autoload.php';
set_exception_handler(static function (Throwable $error): never {
    \Sso\Layerling\Gateway::fail(503, 'mcp_test_unavailable');
});
$storage = \Sso\Layerling\StorageConfig::load($private . '/app/storage.json');
(new \Sso\Layerling\McpTest($private, $storage))->run();
