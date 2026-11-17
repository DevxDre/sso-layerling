<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Immutable published snapshots in a private directory, independent of personal projects. */
final class TemplateCatalog
{
    public const MAX_BYTES = 32 * 1024 * 1024;
    private const MAX_TOTAL_BYTES = 256 * 1024 * 1024;
    private const MAX_ENTRIES = 100;
    private readonly string $root;
    private $lock;

    public function __construct(string $private, bool $write)
    {
        $this->root = $private . '/templates';
        $lockPath = $this->root . '/.lock';
        if (realpath($this->root) !== $this->root || !is_dir($this->root) || is_link($lockPath)) {
            Gateway::fail(503, 'templates_unavailable');
        }
        $this->lock = fopen($lockPath, 'c+b');
        if (!$this->lock || !flock($this->lock, $write ? LOCK_EX : LOCK_SH)) {
            Gateway::fail(503, 'templates_unavailable');
        }
    }

    public function entries(): array
    {
        $entries = [];
        foreach (new \DirectoryIterator($this->root) as $entry) {
            $id = $entry->getFilename();
            if (preg_match('/^[a-f0-9]{32}$/D', $id)) {
                $entries[] = $this->get($id);
            }
        }
        usort($entries, static fn(array $a, array $b): int => $b['created'] <=> $a['created'] ?: strcmp($a['id'], $b['id']));
        return $entries;
    }

    public function get(mixed $id): array
    {
        if (!is_string($id) || !preg_match('/^[a-f0-9]{32}$/D', $id)) {
            Gateway::fail(404, 'template_not_found');
        }
        $directory = $this->root . '/' . $id;
        if (!is_dir($directory) && !is_link($directory)) {
            Gateway::fail(404, 'template_not_found');
        }
        $archive = $directory . '/project.lyl';
        $metadata = $directory . '/metadata.json';
        if (realpath($directory) !== $directory || is_link($archive) || !is_file($archive)
            || is_link($metadata) || !is_file($metadata) || filesize($metadata) > 32768) {
            Gateway::fail(503, 'templates_unavailable');
        }
        $bytes = filesize($archive);
        $entry = json_decode((string)file_get_contents($metadata), true, 16, JSON_THROW_ON_ERROR);
        if ($bytes === false || $bytes === 0 || $bytes > self::MAX_BYTES
            || !is_array($entry) || !is_string($entry['publisher'] ?? null) || !is_array($entry['groups'] ?? null)
            || !is_string($entry['title'] ?? null) || !is_string($entry['instructions'] ?? null)
            || !is_int($entry['created'] ?? null)) {
            Gateway::fail(503, 'templates_unavailable');
        }
        return ['id' => $id, 'archive' => $archive, 'bytes' => $bytes] + $entry;
    }

    public function publish(string $actor, array $allowedGroups, array $form, array $file): void
    {
        $title = self::text($form['title'] ?? null, 100);
        $instructions = self::text($form['instructions'] ?? null, 2000);
        $groups = $form['groups'] ?? null;
        if (!is_array($groups) || !array_is_list($groups) || $groups === [] || count($groups) > count($allowedGroups)) {
            Gateway::fail(400, 'invalid_template_groups');
        }
        foreach ($groups as $group) {
            if (!is_string($group) || !in_array($group, $allowedGroups, true)) {
                Gateway::fail(403, 'template_group_not_allowed');
            }
        }
        if (($file['error'] ?? null) === UPLOAD_ERR_INI_SIZE || ($file['error'] ?? null) === UPLOAD_ERR_FORM_SIZE) {
            Gateway::fail(413, 'template_too_large');
        }
        $source = $file['tmp_name'] ?? null;
        $name = $file['name'] ?? null;
        if (($file['error'] ?? null) !== UPLOAD_ERR_OK || !is_string($source) || !is_uploaded_file($source)
            || !is_string($name) || !preg_match('/\.lyl$/iD', $name)) {
            Gateway::fail(400, 'invalid_template_file');
        }
        $bytes = filesize($source);
        if ($bytes === false || $bytes === 0) {
            Gateway::fail(400, 'invalid_template_file');
        }
        if ($bytes > self::MAX_BYTES) {
            Gateway::fail(413, 'template_too_large');
        }
        $archive = new \ZipArchive();
        if ($archive->open($source, \ZipArchive::RDONLY) !== true) {
            Gateway::fail(400, 'invalid_template_file');
        }
        $hasProject = $archive->locateName('project.json') !== false;
        $archive->close();
        if (!$hasProject) {
            Gateway::fail(400, 'invalid_template_file');
        }
        $entries = $this->entries();
        if (count($entries) >= self::MAX_ENTRIES || array_sum(array_column($entries, 'bytes')) + $bytes > self::MAX_TOTAL_BYTES) {
            Gateway::fail(409, 'template_catalog_full');
        }
        $id = bin2hex(random_bytes(16));
        $staging = $this->root . '/.pending-' . $id;
        $metadata = json_encode(['publisher' => $actor, 'groups' => array_values(array_unique($groups)),
            'title' => $title, 'instructions' => $instructions, 'created' => time()], JSON_THROW_ON_ERROR);
        if (!mkdir($staging, 0700)) {
            Gateway::fail(503, 'templates_unavailable');
        }
        try {
            if (!move_uploaded_file($source, $staging . '/project.lyl')
                || !chmod($staging . '/project.lyl', 0600)
                || file_put_contents($staging . '/metadata.json', $metadata) !== strlen($metadata)
                || !rename($staging, $this->root . '/' . $id)) {
                throw new \RuntimeException('Template publication failed');
            }
        } finally {
            if (is_dir($staging)) {
                self::removeSnapshot($staging);
            }
        }
    }

    public function withdraw(array $entry): void
    {
        $directory = dirname($entry['archive']);
        $hidden = $this->root . '/.withdrawn-' . $entry['id'];
        if (!rename($directory, $hidden)) {
            Gateway::fail(503, 'templates_unavailable');
        }
        self::removeSnapshot($hidden);
    }

    private static function removeSnapshot(string $directory): void
    {
        foreach (['project.lyl', 'metadata.json'] as $name) {
            if (is_file($directory . '/' . $name)) {
                unlink($directory . '/' . $name);
            }
        }
        rmdir($directory);
    }

    private static function text(mixed $value, int $max): string
    {
        if (!is_string($value) || strlen($value) > $max * 4 || !mb_check_encoding($value, 'UTF-8')) {
            Gateway::fail(400, 'invalid_template_text');
        }
        $value = trim($value);
        if ($value === '' || mb_strlen($value) > $max || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/', $value)) {
            Gateway::fail(400, 'invalid_template_text');
        }
        return $value;
    }
}
