<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Revoke under the native session lock, including already waiting requests. */
final class SessionRevocation
{
    public static function revoke(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            return;
        }
        // Do not unlink the file with session_destroy(): a waiting request may
        // already hold the old inode and read the authenticated record from it.
        // Persist an empty record under lock. Garbage collection may remove it
        // later; no authenticated state remains even for an old file handle.
        $_SESSION = [];
        if (!session_write_close()) {
            throw new \RuntimeException('Session revocation failed');
        }
    }
}
