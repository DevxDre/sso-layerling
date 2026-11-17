<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Local, opt-in bridge for the pinned Layerling editor and its stdio client. */
final class McpTest
{
    private const MAX_BODY = 4 * 1024 * 1024;
    private const TOKEN_SECONDS = 1800;
    private const EDITOR_SECONDS = 15;
    private readonly NativeSession $native;

    public function __construct(private readonly string $private, private readonly StorageConfig $storage)
    {
        $this->native = $storage->session($private);
    }

    public static function rules(string $private, StorageConfig $storage): ?array
    {
        if (!defined('SSO_LAYERLING_MCP_TEST_ROUTER') || PHP_SAPI !== 'cli-server' || $storage->secure
            || ($_SERVER['REMOTE_ADDR'] ?? null) !== '127.0.0.1') {
            return null;
        }
        $path = $private . '/app/mcp-test.json';
        if (is_link($path) || !is_file($path) || filesize($path) > 16384) {
            return null;
        }
        $rules = json_decode((string)file_get_contents($path), true);
        $formats = [
            'accounts' => '/^[a-f0-9]{32}$/D',
            'roles' => '/^[A-Za-z0-9_.:-]{1,100}$/D',
            'groups' => '/^[A-Za-z0-9_-]{1,128}$/D',
        ];
        foreach (['allow', 'deny'] as $effect) {
            foreach ($formats as $key => $pattern) {
                $values = $rules[$effect][$key] ?? null;
                if (!is_array($values) || !array_is_list($values)) {
                    return null;
                }
                foreach ($values as $value) {
                    if (!is_string($value) || preg_match($pattern, $value) !== 1) {
                        return null;
                    }
                }
            }
        }
        return $rules;
    }

    private static function reply(array $data, int $status = 200): never
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($data, JSON_THROW_ON_ERROR), "\n";
        exit;
    }

    private static function id(mixed $value): string
    {
        if (!is_string($value) || !preg_match('/^[A-Za-z0-9-]{1,80}$/D', $value) || ctype_digit($value)) {
            Gateway::fail(400, 'invalid_editor');
        }
        return $value;
    }

    /** One short critical section across CLI workers. Never hold this lock while waiting for a session or editor. */
    private function state(callable $operation): mixed
    {
        $path = $this->private . '/mcp-test-state';
        $lock = fopen($path . '.lock', 'c');
        if (!$lock || !flock($lock, LOCK_EX)) {
            throw new \RuntimeException('MCP state lock unavailable');
        }
        try {
            $before = is_file($path) ? (string)file_get_contents($path) : '{}';
            $state = json_decode($before, true, 32, JSON_THROW_ON_ERROR);
            $now = time();
            foreach ($state as $id => &$entry) {
                $entry['editors'] = array_filter($entry['editors'], static fn($editor) => $editor['lastSeen'] > ($now - self::EDITOR_SECONDS) * 1000);
                if (($entry['command']['expiresAt'] ?? 0) <= microtime(true)) {
                    unset($entry['command']);
                }
                if (($entry['tokenExpiresAt'] ?? 0) <= $now) {
                    unset($entry['tokenHash'], $entry['tokenExpiresAt'], $entry['command']);
                    if ($entry['editors'] === []) {
                        unset($state[$id]);
                    }
                }
            }
            unset($entry);
            $result = $operation($state);
            $after = json_encode($state, JSON_THROW_ON_ERROR);
            if ($after !== $before) {
                $temp = $path . '.tmp';
                if (strlen($after) > 16 * 1024 * 1024
                    || file_put_contents($temp, $after) !== strlen($after) || !rename($temp, $path)) {
                    throw new \RuntimeException('MCP state write failed');
                }
            }
            return $result;
        } finally {
            fclose($lock);
        }
    }

    private function permits(array $session): bool
    {
        $rules = self::rules($this->private, $this->storage);
        return $rules !== null && (new SsoPolicy($this->private, $this->storage->values))->allowsMcpTest($session['userId'], $rules);
    }

    public function run(): never
    {
        umask(0077);
        session_cache_limiter('');
        header('Cache-Control: private, no-store');
        header('X-Content-Type-Options: nosniff');
        header('Cross-Origin-Resource-Policy: same-origin');
        $this->storage->assertRequest($this->private);
        if (self::rules($this->private, $this->storage) === null) {
            Gateway::fail(404, 'mcp_test_unavailable');
        }
        $method = $_SERVER['REQUEST_METHOD'] ?? '';
        if (!in_array($method, ['GET', 'POST'], true)) {
            Gateway::fail(405, 'method_not_allowed');
        }
        $origin = $_SERVER['HTTP_ORIGIN'] ?? null;
        if (($origin !== null && $origin !== $this->storage->values['origin'])
            || !in_array($_SERVER['HTTP_SEC_FETCH_SITE'] ?? 'none', ['none', 'same-origin'], true)) {
            Gateway::fail(403, 'foreign_request');
        }
        $status = $method === 'GET' && array_key_exists('status', $_GET);
        $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
        $body = [];
        if ($method === 'POST') {
            if (strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') {
                Gateway::fail(415, 'mcp_requires_json');
            }
            $raw = file_get_contents('php://input', false, null, 0, self::MAX_BODY + 1);
            if ($raw === false || strlen($raw) > self::MAX_BODY) {
                Gateway::fail(413, 'mcp_payload_too_large');
            }
            $parsed = json_decode($raw, false, 64);
            if (!$parsed instanceof \stdClass) {
                Gateway::fail(400, 'invalid_mcp_request');
            }
            $body = (array)$parsed;
        }
        if ($auth !== '' || ($method === 'GET' && !$status)) {
            $this->client($method, $auth, $body);
        }
        $session = $this->native->open();
        if ($status) {
            self::reply(['remote' => $session !== null && $this->permits($session)]);
        }
        if ($session === null || !$this->permits($session)) {
            Gateway::fail(403, 'mcp_access_denied');
        }
        $csrf = $_SERVER['HTTP_X_SSO_CSRF'] ?? '';
        if ($origin === null || !hash_equals($session['csrf'], $csrf)) {
            Gateway::fail(403, 'csrf_rejected');
        }
        $this->browser(session_id(), $body);
    }

    private function browser(string $sessionId, array $body): never
    {
        $type = $body['type'] ?? null;
        if (!in_array($type, ['pair', 'heartbeat', 'poll', 'result'], true)) {
            Gateway::fail(400, 'invalid_mcp_request');
        }
        $editor = (array)($body['editor'] ?? []);
        $editorId = $type === 'pair' ? null : self::id($type === 'heartbeat' ? ($editor['editorId'] ?? null) : ($body['editorId'] ?? null));
        $reply = $this->state(static function (array &$state) use ($sessionId, $type, $editor, $editorId, $body) {
            if (!isset($state[$sessionId]) && count($state) >= 16) {
                return null;
            }
            $entry = &$state[$sessionId];
            $entry ??= ['editors' => []];
            if ($type === 'pair') {
                $token = bin2hex(random_bytes(32));
                $entry['tokenHash'] = hash('sha256', $token);
                $entry['tokenExpiresAt'] = time() + self::TOKEN_SECONDS;
                unset($entry['command']);
                return ['token' => $token, 'expiresAt' => $entry['tokenExpiresAt']];
            }
            if ($type === 'heartbeat') {
                if (!is_int($editor['editorNumber'] ?? null) || $editor['editorNumber'] < 10000 || $editor['editorNumber'] > 99999
                    || (!isset($entry['editors'][$editorId]) && count($entry['editors']) >= 12)) {
                    return null;
                }
                $summary = ['editorId' => $editorId, 'editorNumber' => $editor['editorNumber']];
                foreach (['projectId', 'projectName', 'url', 'notice', 'lastError'] as $field) {
                    $value = $editor[$field] ?? null;
                    $summary[$field] = is_string($value) && strlen($value) <= 2048 ? $value : null;
                }
                foreach (['shapeCount', 'selectedCount'] as $field) {
                    $summary[$field] = is_int($editor[$field] ?? null) ? $editor[$field] : 0;
                }
                $summary['focused'] = ($editor['focused'] ?? null) === true;
                $summary['lastSeen'] = (int)(microtime(true) * 1000);
                $entry['editors'][$editorId] = $summary;
                return ['ok' => true];
            }
            $command = ($entry['command']['editorId'] ?? null) === $editorId && isset($entry['editors'][$editorId])
                ? $entry['command']['command'] : null;
            if ($command === null) {
                return $type === 'poll' ? ['command' => null] : ['ok' => false];
            }
            $job = &$entry['command'];
            if ($type === 'poll') {
                if ($job['delivered']) {
                    return ['command' => null];
                }
                $job['delivered'] = true;
                $command['params'] = json_decode($command['params'], false, 64, JSON_THROW_ON_ERROR);
                return ['command' => $command];
            }
            $result = (array)($body['result'] ?? []);
            if (!$job['delivered'] || isset($job['result'])
                || ($result['commandId'] ?? null) !== $command['id'] || !is_bool($result['ok'] ?? null)) {
                return ['ok' => false];
            }
            $job['result'] = json_encode($result, JSON_THROW_ON_ERROR);
            return ['ok' => true];
        });
        if ($reply === null) {
            Gateway::fail(429, 'mcp_editor_capacity_or_invalid_number');
        }
        self::reply($reply);
    }

    private function client(string $method, string $auth, array $body): never
    {
        if (!preg_match('/^Bearer ([a-f0-9]{64})$/D', $auth, $matches)) {
            Gateway::fail(401, 'mcp_token_required');
        }
        $hash = hash('sha256', $matches[1]);
        $sessionId = $this->state(static function (array &$state) use ($hash) {
            foreach ($state as $id => $entry) {
                if (hash_equals($entry['tokenHash'] ?? '', $hash)) {
                    return $id;
                }
            }
            return null;
        });
        $session = $sessionId === null ? null : $this->native->open($sessionId);
        if ($session === null || !$this->permits($session)) {
            Gateway::fail(403, 'mcp_access_denied');
        }
        if ($method === 'GET') {
            $editors = $this->state(static fn(array &$state) =>
                ($state[$sessionId]['tokenHash'] ?? null) === $hash ? array_values($state[$sessionId]['editors']) : null);
            if ($editors === null) {
                Gateway::fail(403, 'mcp_access_denied');
            }
            self::reply(['editors' => $editors]);
        }
        $this->command($sessionId, $hash, $body);
    }

    private function command(string $sessionId, string $hash, array $body): never
    {
        $action = $body['action'] ?? null;
        $editorId = isset($body['editorId']) ? self::id($body['editorId']) : null;
        $number = $body['editorNumber'] ?? null;
        $params = $body['params'] ?? new \stdClass();
        if (($body['type'] ?? null) !== 'command' || !is_string($action) || !preg_match('/^[a-z_]{1,80}$/D', $action)
            || !$params instanceof \stdClass || ($editorId === null && !is_int($number))) {
            Gateway::fail(400, 'invalid_mcp_command');
        }
        $timeout = $body['timeoutMs'] ?? 15000;
        if (!is_int($timeout) || $timeout < 1 || $timeout > 300000) {
            Gateway::fail(400, 'invalid_mcp_timeout');
        }
        $deadline = microtime(true) + $timeout / 1000;
        $command = ['id' => bin2hex(random_bytes(16)), 'action' => $action, 'params' => json_encode($params, JSON_THROW_ON_ERROR),
            'createdAt' => (int)(microtime(true) * 1000)];
        $error = $this->state(static function (array &$state) use ($sessionId, $hash, $editorId, $number, $command, $deadline) {
            if (($state[$sessionId]['tokenHash'] ?? null) !== $hash) {
                return [403, 'mcp_access_denied'];
            }
            $entry = &$state[$sessionId];
            if (isset($entry['command']) || count(array_filter($state, static fn($item) => isset($item['command']))) >= 2) {
                return [409, 'mcp_command_in_progress'];
            }
            $editors = array_filter($entry['editors'], static fn($editor) =>
                $editorId !== null ? $editor['editorId'] === $editorId : $editor['editorNumber'] === $number);
            if (count($editors) !== 1) {
                return [404, 'mcp_editor_missing_or_ambiguous'];
            }
            $entry['command'] = ['editorId' => array_key_first($editors), 'command' => $command,
                'delivered' => false, 'expiresAt' => $deadline];
            return null;
        });
        if ($error !== null) {
            Gateway::fail(...$error);
        }
        session_write_close();
        while (microtime(true) < $deadline && !connection_aborted()) {
            usleep(150000);
            $outcome = $this->state(static function (array &$state) use ($sessionId, $hash, $command) {
                if (($state[$sessionId]['tokenHash'] ?? null) !== $hash
                    || ($state[$sessionId]['command']['command']['id'] ?? null) !== $command['id']) {
                    return false;
                }
                $entry = &$state[$sessionId];
                $result = $entry['command']['result'] ?? null;
                if ($result !== null) {
                    unset($entry['command']);
                }
                return $result;
            });
            if ($outcome === false) {
                break;
            }
            if (is_string($outcome)) {
                $session = $this->native->open($sessionId);
                if ($session === null || !$this->permits($session) || !$this->state(static fn(array &$state) =>
                    ($state[$sessionId]['tokenHash'] ?? null) === $hash)) {
                    Gateway::fail(403, 'mcp_access_denied');
                }
                $result = (array)json_decode($outcome, false, 64, JSON_THROW_ON_ERROR);
                self::reply($result, $result['ok'] ? 200 : 504);
            }
        }
        Gateway::fail(504, 'mcp_command_expired');
    }
}
