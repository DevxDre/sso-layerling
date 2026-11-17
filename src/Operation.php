<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Explicit adapter for the pinned upstream dispatch; ambiguous input fails. */
final class Operation
{
    /** Mirrors the pinned store's POST dispatch through to handle_save. */
    public static function savesProject(string $method, array $query): bool
    {
        if ($method !== 'POST' || isset($query['moveTo'])) { return false; }
        foreach (['folder', 'renameTo', 'copyTo', 'renameFileTo', 'exportFile', 'settings'] as $selector) {
            if (($query[$selector] ?? '') !== '') { return false; }
        }
        return true;
    }

    public static function classify(string $method, array $query): string
    {
        $common = ['path', 'fileName'];
        $keys = match ($method) {
            'GET' => ['search', 'settings', 'all', 'thumbnail', 'v', 'exportFile'],
            'POST' => ['folder', 'renameTo', 'moveTo', 'copyTo', 'renameFileTo', 'exportFile', 'overwrite', 'settings'],
            'DELETE' => ['deleteFolder', 'recursive', 'exportFile'],
        };
        foreach ($query as $key => $value) {
            if (!is_string($value) || !in_array($key, [...$common, ...$keys], true)) {
                Gateway::fail(400, 'invalid_operation');
            }
        }
        if ($method === 'GET') {
            $selectors = array_intersect(['search', 'settings', 'all', 'fileName', 'exportFile'], array_keys($query));
            $selectors = array_filter($selectors, static fn(string $key): bool => $query[$key] !== '');
            if (count($selectors) > 1 || (isset($query['thumbnail']) && ($query['fileName'] ?? '') === '')) {
                Gateway::fail(400, 'ambiguous_operation');
            }
            return ($query['settings'] ?? '') !== '' ? 'settings-read' : 'read';
        }
        if ($method === 'DELETE') {
            if (count(array_intersect(['deleteFolder', 'fileName', 'exportFile'], array_keys($query))) > 1) {
                Gateway::fail(400, 'ambiguous_operation');
            }
            return 'delete';
        }
        $selectors = array_intersect(['folder', 'renameTo', 'moveTo', 'copyTo', 'renameFileTo', 'exportFile', 'settings'], array_keys($query));
        if (count($selectors) > 1) {
            Gateway::fail(400, 'ambiguous_operation');
        }
        return ($query['settings'] ?? '') !== '' ? 'settings-write' : 'write';
    }
}
