<?php
declare(strict_types=1);

namespace Sso\Layerling;

require_once __DIR__ . '/Gateway.php';
require_once __DIR__ . '/Policy.php';
require_once __DIR__ . '/SsoPolicy.php';
require_once __DIR__ . '/StorageConfig.php';
require_once __DIR__ . '/Operation.php';
require_once __DIR__ . '/Audit.php';
require_once __DIR__ . '/ExportFiles.php';
require_once __DIR__ . '/SessionRevocation.php';
require_once __DIR__ . '/NativeSession.php';

// Upstream may replace headers (notably public thumbnail caching). This callback
// runs immediately before headers are sent, including upstream's exit/streaming.
header_register_callback(static function (): void {
    header('Cache-Control: private, no-store');
    header('Pragma: no-cache');
    header_remove('Expires');
    header('X-Content-Type-Options: nosniff');
    header('Cross-Origin-Resource-Policy: same-origin');
    header('Vary: Cookie');
});

set_exception_handler(static function (\Throwable $error): void {
    // Neither configuration paths nor session contents enter the response/log.
    Gateway::fail(503, 'storage_unavailable');
});

return new Gateway(dirname(__DIR__));
