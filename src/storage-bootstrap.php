<?php
declare(strict_types=1);
require dirname(__DIR__) . '/vendor/autoload.php';
\Sso\Layerling\Oidc\Web::headers();
header_register_callback(static function():void {
    header('Cache-Control: private, no-store'); header('Pragma: no-cache'); header_remove('Expires');
    header('Referrer-Policy: no-referrer'); header('X-Content-Type-Options: nosniff');
    header('Cross-Origin-Resource-Policy: same-origin'); header('Vary: Cookie');
});
ini_set('display_errors','0');
set_exception_handler(static function(\Throwable $e):void { \Sso\Layerling\Gateway::fail(503,'storage_unavailable'); });
return new \Sso\Layerling\Gateway(dirname(__DIR__,2),\Sso\Layerling\StorageConfig::load(dirname(__DIR__).'/storage.json'));
