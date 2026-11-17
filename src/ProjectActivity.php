<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** The modification time of a private marker is the account's last successful project save. */
final class ProjectActivity
{
    private const DIRECTORY = '/project-activity';
    private const WINDOW = 3600;

    public static function record(string $private, string $actor): void
    {
        $root = $private . self::DIRECTORY;
        if (!is_dir($root)) { @mkdir($root, 0700); }
        if (realpath($root) !== $root) { return; }
        $marker = $root . '/' . $actor;
        if (!is_link($marker)) { @touch($marker); }
    }

    public static function recent(string $private, string $actor, int $now): bool
    {
        $root = $private . self::DIRECTORY;
        $marker = $root . '/' . $actor;
        if (is_link($root) || is_link($marker) || !is_file($marker)) { return false; }
        $saved = filemtime($marker);
        return $saved !== false && $saved <= $now && $saved > $now - self::WINDOW;
    }
}
