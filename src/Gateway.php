<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** Local storage prototype. No login or identity issuer is exposed over HTTP. */
final class Gateway
{
    public const COOKIE = 'SSO_LAYERLING_SESSION';
    private readonly array $config;
    private readonly string $data;
    private Policy|SsoPolicy $policy;
    private readonly NativeSession $native;
    private readonly string $sources;

    public function __construct(private readonly string $private, private readonly ?StorageConfig $storage = null)
    {
        umask(0077);
        // The legacy prototype remains loopback-only. StorageConfig is a separate validated SSO deployment.
        if ($storage === null && (PHP_SAPI !== 'cli-server' || !in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1', '::1'], true))) {
            self::fail(503, 'local_prototype_only');
        }
        $storage?->assertRequest($private);
        $this->config = $storage?->values ?? json_decode((string) file_get_contents($private . '/config.json'), true, 32, JSON_THROW_ON_ERROR);
        $this->sources = $storage !== null ? $private . '/app' : $private;
        if (!in_array($this->config['authorizationModel'] ?? null, ['prototype-fresh-evidence', 'sso-last-login'], true)) {
            self::fail(503, 'invalid_configuration');
        }
        $origin = $this->config['origin'] ?? null;
        if ($storage === null && (!is_string($origin) || preg_match('~^http://127\.0\.0\.1:[1-9][0-9]{0,4}$~D', $origin) !== 1
            || ($this->config['mode'] ?? null) !== 'local-storage-prototype')) {
            self::fail(503, 'invalid_configuration');
        }
        if ($storage === null && ($_SERVER['HTTP_HOST'] ?? '') !== substr($origin, 7)) {
            self::fail(400, 'invalid_host');
        }
        foreach (['absoluteSeconds', 'idleSeconds'] as $key) {
            if (!is_int($this->config[$key] ?? null) || $this->config[$key] < 1) {
                self::fail(503, 'invalid_configuration');
            }
        }
        foreach (['projects', 'sessions'] as $directory) {
            $path = $private . '/' . $directory;
            if (is_link($path) || !is_dir($path) || !is_writable($path)) {
                self::fail(503, 'storage_unavailable');
            }
        }
        $this->data = $private . '/projects';
        $this->native = $storage?->session($private) ?? new NativeSession($private, 'sessions', self::COOKIE, false, $this->config['absoluteSeconds'], $this->config['idleSeconds']);
        $public = $storage !== null ? realpath($this->config['publicRoot']) : realpath($private . '/../public');
        $resolved = realpath($private);
        if ($resolved === false || $public === false || $resolved === $public
            || str_starts_with($resolved . '/', $public . '/')) {
            self::fail(503, 'invalid_layout');
        }
    }

    public static function fail(int $status, string $error): never
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['error' => $error], JSON_THROW_ON_ERROR), "\n";
        exit;
    }

    /** Authenticate without creating anonymous sessions or accepting URL IDs. */
    public function authenticate(): void
    {
        $origin = $_SERVER['HTTP_ORIGIN'] ?? null;
        if (($origin !== null && $origin !== $this->config['origin'])
            || !in_array($_SERVER['HTTP_SEC_FETCH_SITE'] ?? 'none', ['none', 'same-origin'], true)) {
            self::fail(403, 'foreign_request');
        }
        if ($this->native->open() === null) {
            self::fail(401, 'authentication_required');
        }
        // Keep the native session lock until upstream exits. Logout therefore
        // waits for an admitted request; requests admitted after logout fail.
    }

    private function method(array $allowed, bool $touch = true): string
    {
        $method = $_SERVER['REQUEST_METHOD'] ?? '';
        if (!in_array($method, $allowed, true)) {
            header('Allow: ' . implode(', ', $allowed));
            self::fail(405, 'method_not_allowed');
        }
        $csrf = $_SERVER['HTTP_X_SSO_CSRF'] ?? null;
        if ($method === 'GET' && $csrf !== null && (!is_string($csrf) || !hash_equals($_SESSION['csrf'], $csrf))) {
            self::fail(403, 'csrf_rejected');
        }
        if ($method !== 'GET') {
            if (($_SERVER['HTTP_ORIGIN'] ?? '') !== $this->config['origin']
                || !is_string($csrf) || !hash_equals($_SESSION['csrf'], $csrf)) {
                self::fail(403, 'csrf_rejected');
            }
        }
        if ($touch) { $_SESSION['lastSeen'] = time(); }
        return $method;
    }

    private function authorization(): Policy|SsoPolicy
    {
        return $this->config['authorizationModel'] === 'sso-last-login'
            ? new SsoPolicy($this->private, $this->config) : new Policy($this->private, $this->config);
    }

    public function session(): never
    {
        $this->authenticate();
        $method = $this->method($this->storage !== null ? ['GET'] : ['GET', 'POST']);
        if ($method === 'POST') {
            // The only POST operation here is logout. There is no login route.
            $this->destroySession();
            http_response_code(204);
            exit;
        }
        $this->policy = $this->authorization();
        $this->policy->requireActor($_SESSION['userId']);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['csrfToken' => $_SESSION['csrf']], JSON_THROW_ON_ERROR), "\n";
        exit;
    }

    /** Read-only editor probe: must not turn polling into user activity. */
    public function cadSession(): never
    {
        $this->authenticate();
        $this->method(['GET'], false);
        if ($this->storage === null) {
            self::fail(404, 'not_found');
        }
        $actor = $_SESSION['userId'];
        $policy = new SsoPolicy($this->private, $this->config);
        $owner = $policy->owner($actor, $_GET['owner'] ?? $actor);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['userId'=>$actor, 'csrfToken'=>$_SESSION['csrf'],
            'ownerId'=>$owner['userId'], 'canWrite'=>$owner['canWrite'], 'canDelete'=>$owner['canDelete'],
            'expiresAt'=>min($_SESSION['issuedAt']+$this->config['absoluteSeconds'],
                $_SESSION['lastSeen']+$this->config['idleSeconds'])], JSON_THROW_ON_ERROR), "\n";
        exit;
    }

    public function templates(): never
    {
        if ($this->storage === null) {
            self::fail(404, 'not_found');
        }
        $this->authenticate();
        $method = $this->method(['GET', 'POST']);
        $actor = $_SESSION['userId'];
        $policy = new SsoPolicy($this->private, $this->config);
        $access = $policy->templateAccess($actor);
        if (!$access['teacher'] && !$access['student']) {
            self::fail(403, 'access_denied');
        }
        if ($method === 'POST') {
            if (!$access['teacher']) {
                self::fail(403, 'access_denied');
            }
            $catalog = new TemplateCatalog($this->private, true);
            if ($_GET === ['action' => 'publish']) {
                $catalog->publish($actor, $access['publishGroups'], $_POST, $_FILES['project'] ?? []);
                http_response_code(201);
            } elseif ($_GET === ['action' => 'withdraw']) {
                $entry = $catalog->get($_POST['id'] ?? null);
                if ($entry['publisher'] !== $actor) {
                    self::fail(404, 'template_not_found');
                }
                $catalog->withdraw($entry);
                http_response_code(204);
            } else {
                self::fail(400, 'invalid_operation');
            }
            exit;
        }

        $catalog = new TemplateCatalog($this->private, false);
        $canCopy = static fn(array $entry): bool => $access['student'] && array_intersect($access['groups'], $entry['groups']) !== [];
        if (array_keys($_GET) === ['id']) {
            $entry = $catalog->get($_GET['id']);
            if (!$canCopy($entry)) {
                self::fail(404, 'template_not_found');
            }
            header('Content-Type: application/vnd.layerling.project+zip');
            header('Content-Length: ' . $entry['bytes']);
            header('Content-Disposition: attachment; filename="vorlage.lyl"');
            readfile($entry['archive']);
            exit;
        }
        if ($_GET !== []) {
            self::fail(400, 'invalid_operation');
        }
        $entries = array_filter($catalog->entries(), static fn(array $entry): bool =>
            $canCopy($entry) || ($access['teacher'] && $entry['publisher'] === $actor));
        $csrf = $_SESSION['csrf'];
        $labels = $access['labels'] ?: ($_SESSION['diagnostic']['templateGroupLabels'] ?? []);
        $hasCad = is_file($this->sources . '/cad/index.html');
        header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'");
        // Same-origin JS POSTs need the configured Origin, not Origin:null.
        header('Referrer-Policy: same-origin');
        header('Content-Type: text/html; charset=utf-8');
        require __DIR__ . '/templates-page.php';
        exit;
    }

    private function destroySession(): void
    {
        $this->native->revoke();
    }

    /** Preserve owner scope in JSON thumbnail links without buffering downloads. */
    private function preserveThumbnailOwner(string $owner): void
    {
        ob_start(static function (string $body) use ($owner): string {
            try {
                $payload = json_decode($body, true, 32, JSON_THROW_ON_ERROR);
                if (!is_array($payload)) {
                    return $body;
                }
                $scope = static function (array &$record) use ($owner): void {
                    $url = $record['thumbnailUrl'] ?? null;
                    if (is_string($url) && str_starts_with($url, 'store.php?')) {
                        $record['thumbnailUrl'] = $url . '&_sso_owner=' . $owner;
                    }
                };
                if (is_array($payload['project'] ?? null)) {
                    $scope($payload['project']);
                }
                if (is_array($payload['projects'] ?? null)) {
                    foreach ($payload['projects'] as &$record) {
                        if (is_array($record)) {
                            $scope($record);
                        }
                    }
                    unset($record);
                }
                return json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n";
            } catch (\JsonException) {
                return $body;
            }
        });
    }

    public function owners(): never
    {
        if ($this->storage === null) { self::fail(404, 'not_found'); }
        $this->authenticate();
        $this->method(['GET']);
        $this->policy = $this->authorization();
        header('Content-Type: application/json; charset=utf-8');
        $owners = $this->policy->owners($_SESSION['userId'], $_GET === ['cad' => '1']);
        echo json_encode(['owners'=>$owners], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE), "\n";
        exit;
    }

    public function store(): never
    {
        $this->authenticate();
        $method = $this->method(['GET', 'POST', 'DELETE']);
        $actor = $_SESSION['userId'];
        $this->policy = $this->authorization();
        $this->policy->requireActor($actor);
        $owner = $_GET['_sso_owner'] ?? $actor;
        if (!is_string($owner) || preg_match('/^[a-f0-9]{32}$/D', $owner) !== 1) {
            self::fail(400, 'invalid_owner');
        }
        unset($_GET['_sso_owner']);
        $operation = Operation::classify($method, $_GET);
        if ($owner !== $actor) {
            Audit::begin($this->private, $actor, $owner, $operation);
        }
        $this->policy->authorize($actor, $owner, $operation);
        $userRoot = $this->data . '/' . $owner;
        if (is_link($userRoot) || (!is_dir($userRoot) && !mkdir($userRoot, 0700))
            || realpath($userRoot) !== $userRoot || !is_writable($userRoot)) {
            self::fail(503, 'storage_unavailable');
        }
        $lock = json_decode((string) file_get_contents($this->sources . '/upstream.lock.json'), true, 16, JSON_THROW_ON_ERROR);
        $upstream = $this->sources . '/upstream/store.php';
        if (!is_string($lock['sha256'] ?? null) || is_link($upstream)
            || !hash_equals($lock['sha256'], hash_file('sha256', $upstream))) {
            self::fail(503, 'upstream_integrity_failed');
        }
        // Provide the resolved personal root, never a client identity header.
        // Explicitly overwrite all sources the pinned upstream script consults.
        foreach (['LAYERLING_SHARED_PROJECTS_DIR' => $userRoot, 'LAYERLING_USER_HEADER' => '', 'LAYERLING_ALLOWED_ORIGINS' => ''] as $key => $value) {
            if (!putenv($key . '=' . $value)) {
                self::fail(503, 'storage_unavailable');
            }
            $_ENV[$key] = $_SERVER[$key] = $value;
        }
        unset($_SERVER['HTTP_X_FORWARDED_HOST'], $_SERVER['HTTP_X_FORWARDED_PROTO']);
        if ($method !== 'POST' && isset($_GET['exportFile'])) {
            ExportFiles::respond($userRoot, $method, $_GET);
        }
        if ($owner !== $actor && !($method === 'GET' && ($_GET['fileName'] ?? '') !== '')) {
            $this->preserveThumbnailOwner($owner);
        }
        if ($this->storage !== null && Operation::savesProject($method, $_GET)) {
            register_shutdown_function(function () use ($actor): void {
                if (in_array(http_response_code(), [200, 201], true)) {
                    ProjectActivity::record($this->private, $actor);
                }
            });
        }
        require $upstream;
        self::fail(503, 'upstream_did_not_respond');
    }
}
