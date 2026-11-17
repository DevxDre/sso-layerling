<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Download/delete adapter for exports the pinned upstream can already save. */
final class ExportFiles
{
    private const EXTENSIONS = ['stl', '3mf', 'obj', 'step', 'stp', 'svg', 'dxf', 'png', 'pdf'];

    public static function respond(string $root, string $method, array $query): never
    {
        $name = $query['exportFile'];
        $folder = $query['path'] ?? '';
        if ($name === '' || strlen($name) > 240 || $name[0] === '.' || basename($name) !== $name
            || preg_match('~[\\\\/\x00-\x1f\x7f]~', $name) === 1
            || !in_array(strtolower(pathinfo($name, PATHINFO_EXTENSION)), self::EXTENSIONS, true)) {
            Gateway::fail(400, 'invalid_export');
        }
        foreach (explode('/', $folder) as $part) {
            if ($folder !== '' && ($part === '' || $part[0] === '.' || str_contains($part, '\\')
                || preg_match('/[\x00-\x1f\x7f]/', $part) === 1)) {
                Gateway::fail(400, 'invalid_path');
            }
        }
        $resolved = realpath($root . '/' . $folder);
        if ($resolved === false || !is_dir($resolved)
            || ($resolved !== $root && !str_starts_with($resolved . '/', $root . '/'))) {
            Gateway::fail(400, 'invalid_path');
        }
        $path = $resolved . '/' . $name;
        if ($method === 'DELETE') {
            // Same on-disk lock convention as upstream export uploads.
            $lockPath = $path . '.lock';
            if (is_file($lockPath) && time() - (int) filemtime($lockPath) > 60) {
                @unlink($lockPath);
            }
            $lock = @fopen($lockPath, 'x');
            if ($lock === false) {
                Gateway::fail(409, 'export_busy');
            }
            fclose($lock);
            register_shutdown_function(static function () use ($lockPath): void { @unlink($lockPath); });
        }
        if (is_link($path) || !is_file($path)) {
            Gateway::fail(404, 'export_not_found');
        }
        $stream = fopen($path, 'rb');
        if ($stream === false) {
            Gateway::fail(503, 'storage_unavailable');
        }
        // Hash and stream the same open inode, even if a writer later renames.
        $hash = hash_init('sha256');
        if (hash_update_stream($hash, $stream) === false || !rewind($stream)) {
            Gateway::fail(503, 'storage_unavailable');
        }
        $etag = '"' . hash_final($hash) . '"';
        if ($method === 'DELETE') {
            fclose($stream);
            if (!isset($_SERVER['HTTP_IF_MATCH'])) {
                Gateway::fail(428, 'revision_required');
            }
            if (!hash_equals($etag, $_SERVER['HTTP_IF_MATCH'])) {
                Gateway::fail(409, 'revision_conflict');
            }
            if (!unlink($path)) {
                Gateway::fail(503, 'storage_unavailable');
            }
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode(['deleted' => true, 'fileName' => $name], JSON_THROW_ON_ERROR), "\n";
            exit;
        }
        header('Content-Type: application/octet-stream');
        header("Content-Disposition: attachment; filename*=UTF-8''" . rawurlencode($name));
        header('ETag: ' . $etag);
        $stat = fstat($stream);
        if ($stat !== false) {
            header('Content-Length: ' . $stat['size']);
        }
        fpassthru($stream);
        fclose($stream);
        exit;
    }
}
