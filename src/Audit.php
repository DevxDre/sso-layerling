<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Log intent before foreign access; completion records only IDs/status. */
final class Audit
{
    public static function begin(string $private, string $actor, string $owner, string $operation): void
    {
        $path = $private . '/audit.jsonl';
        if (is_link($path)) {
            Gateway::fail(503, 'audit_unavailable');
        }
        $base = ['request' => bin2hex(random_bytes(16)), 'actor' => $actor, 'owner' => $owner, 'operation' => $operation];
        if (!self::append($path, $base + ['phase' => 'begin', 'at' => time()])) {
            Gateway::fail(503, 'audit_unavailable');
        }
        register_shutdown_function(static function () use ($path, $base): void {
            // An intent already exists even if completion logging fails.
            self::append($path, $base + ['phase' => 'end', 'at' => time(), 'status' => http_response_code() ?: 200]);
        });
    }

    private static function append(string $path, array $row): bool
    {
        $line = json_encode($row, JSON_THROW_ON_ERROR) . "\n";
        return @file_put_contents($path, $line, FILE_APPEND | LOCK_EX) === strlen($line);
    }
}
