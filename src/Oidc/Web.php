<?php
declare(strict_types=1);
namespace Sso\Layerling\Oidc;

use Sso\Layerling\Oidc\Http\Transport;
use Sso\Layerling\SsoPolicy;

/** SSO routes; files and CAD require explicit private storage/bundle configuration. */
final class Web
{
    public const CONTEXT_COOKIE = 'SSO_LAYERLING_LOGIN';
    public const SESSION_COOKIE = 'SSO_LAYERLING_SSO_TEST';
    private bool $secure;
    private readonly \Sso\Layerling\NativeSession $native;
    public function __construct(private string $private, private Config $config, private Transport $transport,
        private string $origin = 'https://cad.example.invalid', private ?\Sso\Layerling\StorageConfig $storage = null)
    {
        umask(0077);
        $this->secure = Profile::httpsOrigin($origin);
        if ($this->secure && $origin !== $config->profile->origin) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        if (!$this->secure && !(PHP_SAPI === 'cli-server'
            && in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1', '::1'], true)
            && preg_match('~^http://127\.0\.0\.1:[1-9][0-9]{0,4}$~D', $origin))) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        if (($_SERVER['HTTP_HOST'] ?? '') !== parse_url($origin, PHP_URL_HOST) . (parse_url($origin, PHP_URL_PORT) ? ':' . parse_url($origin, PHP_URL_PORT) : '')
            || ($this->secure && !in_array($_SERVER['HTTPS'] ?? '', ['on', '1'], true))) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        $docroot = realpath($_SERVER['DOCUMENT_ROOT'] ?? '');
        $resolved = realpath($private);
        if (!$docroot || !$resolved || $resolved === $docroot || str_starts_with($resolved . '/', $docroot . '/')) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        $storage?->assertRequest($private);
        if ($storage !== null && ($storage->values['origin'] !== $origin
            || ($storage->values['authorizationMapping'] ?? null) !== $config->profile->authorizationMapping())) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        foreach ($storage !== null ? ['contexts', 'sessions'] : ['contexts', 'sso-sessions'] as $dir) {
            if (is_link($private . '/' . $dir) || !is_dir($private . '/' . $dir) || !is_writable($private . '/' . $dir)) {
                throw new LoginFailed(LoginFailed::CONFIG);
            }
        }
        $this->native = $storage?->session($private) ?? new \Sso\Layerling\NativeSession($private,'sso-sessions',self::SESSION_COOKIE,$this->secure);
    }
    public static function headers(): void
    {
        header('Cache-Control: private, no-store');
        header('Pragma: no-cache');
        header('Referrer-Policy: no-referrer');
        header('X-Content-Type-Options: nosniff');
        header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
        header('Cross-Origin-Resource-Policy: same-origin');
    }
    private function cookie(string $name, string $value, int $expires = 0): void
    {
        setcookie($name, $value, ['expires' => $expires, 'path' => '/', 'secure' => $this->secure, 'httponly' => true, 'samesite' => 'Lax']);
    }
    private function context(bool $create = false): LoginContext
    {
        $id = $_COOKIE[self::CONTEXT_COOKIE] ?? '';
        if (is_string($id) && preg_match('/^[a-f0-9]{64}$/D', $id)
            && is_file($this->private . '/contexts/' . $id . '.json')) {
            try { return new LoginContext($this->private, $id); }
            catch (LoginFailed $e) { if (!$create) { throw $e; } }
        }
        if (!$create) { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $id = bin2hex(random_bytes(32));
        $context = new LoginContext($this->private, $id, true);
        $this->cookie(self::CONTEXT_COOKIE, $id);
        return $context;
    }
    private function sameOriginPost(): void
    {
        if (!$this->isSameOriginPost()) {
            throw new LoginFailed(LoginFailed::TRANSACTION);
        }
    }
    private function isSameOriginPost(): bool
    {
        return ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST'
            && ($_SERVER['HTTP_ORIGIN'] ?? '') === $this->origin
            && in_array($_SERVER['HTTP_SEC_FETCH_SITE'] ?? 'same-origin', ['same-origin', 'none'], true);
    }

    private function openSession(): ?array
    {
        $session = $this->native->open();
        if ($session !== null) { $_SESSION['lastSeen'] = time(); }
        return $session;
    }
    private function issue(string $owner, Claims $claims): void
    {
        $diagnostic = $claims->diagnostic($this->config->profile->diagnosticGroupIds);
        if ($this->storage !== null) {
            $diagnostic['preferredUsername'] = $claims->preferredUsername;
        }
        $this->native->issue($owner, $diagnostic);
    }
    private function redirect(string $target): never { header('Location: ' . $target, true, 303); exit; }
    private function route(array $paths): void
    {
        if (!in_array(parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH), $paths, true)) {
            http_response_code(404);
            exit;
        }
    }
    private function hasCad(): bool
    {
        return $this->storage !== null && is_file($this->private . '/app/cad/index.html');
    }

    public function index(): never
    {
        $this->route(['/', '/index.php']);
        $this->entry(false, parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) === '/');
    }

    public function account(): never
    {
        $this->route(['/konto', '/konto/', '/konto/index.php']);
        if (!$this->hasCad()) { http_response_code(404); exit; }
        $this->entry(true);
    }

    private function entry(bool $account, bool $automaticLogin = false): never
    {
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $hasCad = $this->hasCad();
        if ($automaticLogin && $hasCad
            && (str_contains($_SERVER['HTTP_SEC_PURPOSE'] ?? '', 'prefetch')
                || str_contains($_SERVER['HTTP_PURPOSE'] ?? '', 'prefetch'))) {
            http_response_code(204);
            exit;
        }
        $ctx = $this->context(true);
        $csrf = $ctx->csrf();
        $session = $this->openSession();
        $templateAccess = $profile = null;
        $canManagePermissions = false;
        if ($session !== null && $this->storage !== null) {
            $policy = new SsoPolicy($this->private, $this->storage->values);
            $templateAccess = $policy->templateAccess($session['userId']);
            $canManagePermissions = $policy->isPermissionsAdmin($session['userId'], $this->config->adminRole);
            if ($account) { $profile = $policy->owner($session['userId'], $session['userId']); }
        }
        if (session_status() === PHP_SESSION_ACTIVE) { session_write_close(); }
        if ($automaticLogin && $hasCad && $session === null) {
            $this->beginLogin($ctx);
        }
        $ctx->close();
        if (!$account && $hasCad && $session !== null) {
            $this->redirect('/cad.php');
        }
        if ($account && $session === null) {
            $this->redirect('/');
        }
        // Native form POSTs under no-referrer carry Origin:null. Preserve the
        // same-origin form provenance; callback/redirect/error defaults stay no-referrer.
        header('Referrer-Policy: same-origin');
        $issuerOrigin = $this->config->profile->issuerOrigin();
        header("Content-Security-Policy: default-src 'none'; form-action 'self' $issuerOrigin; frame-ancestors 'none'; base-uri 'none'");
        header('Content-Type: text/html; charset=utf-8');
        $e = static fn(string $s) => htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $provider = $e($this->config->profile->provider['name']);
        $title = $account ? 'SSO Layerling – Konto' : ($hasCad ? 'SSO Layerling' : 'SSO Layerling – SSO-Test');
        echo '<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>' . $title . '</title><main><h1>' . $title . '</h1>';
        if (!$account) {
            echo $this->storage !== null
                ? ($hasCad
                    ? '<p>Mit ' . $provider . ' anmelden und Layerling öffnen.</p>'
                    : '<p>Der Dateitest ist freigeschaltet. Der CAD-Editor folgt im nächsten Schritt.</p>')
                : '<p>Dieser Test prüft die Anmeldung über ' . $provider . '. Der CAD-Editor und Dateizugriffe sind noch nicht freigeschaltet.</p>';
        }
        if ($session !== null) {
            echo '<p>Anmeldung über ' . $provider . ' erfolgreich.</p><h2>Geprüfte Angaben des eigenen Kontos</h2>';
            if ($profile !== null) {
                $username = $session['diagnostic']['preferredUsername'] ?? '';
                echo '<p>Account: ' . $e(trim($username) === '' ? '–' : $username) . '</p>';
                echo '<p>Name: ' . $e($profile['name'] ?? '–') . '</p>';
                echo '<p>Klasse: ' . $e($profile['classes'] === [] ? '–' : implode(', ', $profile['classes'])) . '</p>';
            }
            echo '<p>Rollen: ' . $e(implode(', ', $session['diagnostic']['roles'])) . '</p>';
            echo '<p>Gruppenanzahl: ' . (int)$session['diagnostic']['groupCount'] . '</p><ul>';
            foreach ($session['diagnostic']['relevantGroups'] as $group) {
                if (in_array($group['id'], $this->config->profile->diagnosticGroupIds, true)) {
                    echo '<li>' . $e($group['name']) . ': <code>' . $e($group['id']) . '</code></li>';
                }
            }
            echo '</ul>';
            if ($this->storage === null) { echo '<p>Diese Angaben schalten keine Fremddateirechte frei.</p>'; }
        }
        if ($account) { echo '<p><a href="/cad.php">Zum CAD-Editor</a></p>'; }
        if ($canManagePermissions) { echo '<p><a href="/rechte.php">Rechte verwalten</a></p>'; }
        if ($templateAccess && ($templateAccess['teacher'] || $templateAccess['student'])) {
            echo '<p><a href="/vorlagen.php">CAD-Vorlagen</a></p>';
        }
        echo '<form method="post" action="' . ($session ? '/auth/logout.php' : '/auth/start.php') . '"><input type="hidden" name="csrf" value="' . $e($csrf) . '"><button>' . ($session ? 'Lokal abmelden' : 'Mit ' . $provider . ' anmelden') . '</button></form>';
        if (!$session) { echo '<form method="post" action="/auth/logout.php"><input type="hidden" name="csrf" value="' . $e($csrf) . '"><button>Laufende Anmeldung abbrechen</button></form>'; }
        echo '</main></html>';
        exit;
    }
    public function permissions(): never
    {
        $this->route(['/rechte.php']);
        if ($this->storage === null) { http_response_code(404); exit; }
        $method = $_SERVER['REQUEST_METHOD'] ?? '';
        if (!in_array($method, ['GET', 'POST'], true)) {
            header('Allow: GET, POST', true, 405);
            exit;
        }
        header('Content-Type: text/html; charset=utf-8');
        $session = $this->openSession();
        if ($session === null || $this->config->adminRole === null) {
            $this->denyPermissions($session === null ? 401 : 403);
        }
        $csrf = $session['csrf'];
        $changing = $method === 'POST';
        $submittedCsrf = $_POST['csrf'] ?? null;
        if ($changing && (!$this->isSameOriginPost() || !is_string($submittedCsrf) || !hash_equals($csrf, $submittedCsrf))) {
            $this->denyPermissions(403);
        }
        $policy = new SsoPolicy($this->private, $this->storage->values, $changing);
        if (!$policy->isPermissionsAdmin($session['userId'], $this->config->adminRole)) {
            $this->denyPermissions(403);
        }
        [$rules, $patterns, $selectors, $groupNames] = $policy->permissionSettings();
        if ($changing && $policy->changePermissions($_POST, $groupNames)) {
            $this->redirect('/rechte.php?saved=1');
        }
        $invalid = $changing;
        if ($invalid) { http_response_code(400); }
        $groupNamesVersion = SsoPolicy::groupNamesVersion($groupNames);
        unset($policy);
        session_write_close();
        header('Referrer-Policy: same-origin');
        header("Content-Security-Policy: default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
        require __DIR__ . '/permissions-page.php';
        exit;
    }

    private function denyPermissions(int $status): never
    {
        http_response_code($status);
        echo '<!doctype html><html lang="de"><meta charset="utf-8"><title>Rechte verwalten</title>'
            . '<h1>Zugriff verweigert</h1><p>Die Rechteseite erfordert ein angemeldetes Administratorkonto.</p>'
            . '<a href="/index.php">Zur Anmeldung</a></html>';
        exit;
    }

    public function files(): never
    {
        $this->route(['/files.php', '/files', '/files/', '/files/index.php']);
        if ($this->storage === null) { http_response_code(404); exit; }
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $ctx = $this->context(true);
        $logoutCsrf = $ctx->csrf();
        $session = $this->openSession();
        if ($session === null) { $ctx->close(); $this->redirect('/'); }
        (new \Sso\Layerling\SsoPolicy($this->private,$this->storage->values))->requireActor($session['userId']);
        session_write_close();
        $ctx->close();
        $hasCad = $this->hasCad();
        header('Referrer-Policy: same-origin');
        header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
        header('Content-Type: text/html; charset=utf-8');
        require __DIR__ . '/files-template.php';
        exit;
    }
    /** Explicit local CAD candidate; the normal storage package contains no editor bundle. */
    public function cad(): never
    {
        $this->route(['/cad.php']);
        $bundle = $this->private . '/app/cad';
        if ($this->storage === null || !is_file($bundle . '/index.html') || is_link($bundle)) { http_response_code(404); exit; }
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $session = $this->openSession();
        if ($session === null) { $this->redirect('/'); }
        $policy = new \Sso\Layerling\SsoPolicy($this->private, $this->storage->values);
        $actor = $session['userId'];
        $selected = $policy->owner($actor, $_GET['owner'] ?? $actor);
        $owners = $policy->owners($actor, true);
        $templateAccess = $policy->templateAccess($actor);
        $mcpRules = \Sso\Layerling\McpTest::rules($this->private, $this->storage);
        $mcpTest = $selected['isSelf'] && $mcpRules !== null && $policy->allowsMcpTest($actor, $mcpRules);
        $canManagePermissions = $policy->isPermissionsAdmin($actor, $this->config->adminRole);
        unset($policy);
        session_write_close();
        $ctx = $this->context(true);
        $logoutCsrf = $ctx->csrf();
        $ctx->close();
        $manifest = json_decode((string)file_get_contents($bundle . '/manifest.json'),true,16,JSON_THROW_ON_ERROR);
        if (($manifest['kind']??null)!=='sso-layerling-cad-owner-v2'
            || !is_string($manifest['indexSha256']??null) || is_link($bundle . '/index.html')
            || !hash_equals($manifest['indexSha256'],hash_file('sha256',$bundle . '/index.html'))) {
            throw new LoginFailed(LoginFailed::CONFIG);
        }
        $html = (string)file_get_contents($bundle . '/index.html');
        $nonce = base64_encode(random_bytes(24));
        $html = preg_replace('/<script\b/', '<script nonce="'.$nonce.'"', $html);
        $context = json_encode(['userId'=>$actor, 'csrfToken'=>$session['csrf'], 'logoutCsrf'=>$logoutCsrf,
            'selected'=>$selected, 'owners'=>$owners, 'mcpTest'=>$mcpTest,
            'mcpHosted'=>$mcpTest && $this->storage->secure,
            'canManagePermissions'=>$canManagePermissions, 'canUseTemplates'=>$templateAccess['teacher'] || $templateAccess['student']],
            JSON_THROW_ON_ERROR|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT);
        $head = '<link rel="stylesheet" href="/cad-bridge.css">'
            .'<script nonce="'.$nonce.'" id="sso-cad-context" type="application/json">'.$context.'</script>'
            .'<script nonce="'.$nonce.'" src="/cad-bridge.js'.($mcpTest && $this->storage->secure ? '?v=mcp-2' : '').'"></script>';
        if (substr_count($html,'<head>')!==1) { throw new LoginFailed(LoginFailed::CONFIG); }
        $html = str_replace('<head>','<head>'.$head,$html);
        header('Referrer-Policy: same-origin');
        header("Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-".$nonce."' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' data: blob:; worker-src 'self' blob:; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
        header('Cache-Control: private, no-store');
        header_remove('Expires');
        header('Content-Type: text/html; charset=utf-8');
        echo $html;
        exit;
    }

    public function start(): never
    {
        $this->route(['/auth/start.php']);
        $this->sameOriginPost();
        $ctx = $this->context();
        $ctx->checkCsrf($_POST['csrf'] ?? null);
        if ($this->openSession() !== null) { session_write_close(); throw new LoginFailed(LoginFailed::SIGNED_IN); }
        $this->beginLogin($ctx);
    }

    private function beginLogin(LoginContext $ctx): never
    {
        $tx = $ctx->begin($this->config, time());
        $ctx->close();
        $this->redirect((new OidcClient($this->config, $this->transport, static fn() => time()))->authorizationUrl($tx));
    }
    public function callback(): never
    {
        $this->route(['/auth/callback.php']);
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') { throw new LoginFailed(LoginFailed::TRANSACTION); }
        $seen = [];
        foreach (explode('&', $_SERVER['QUERY_STRING'] ?? '') as $part) {
            $key = urldecode(explode('=', $part, 2)[0]);
            if (isset($seen[$key]) || str_contains($key, '[')) { throw new LoginFailed(LoginFailed::TRANSACTION); }
            $seen[$key] = true;
        }
        $ctx = $this->context();
        [$tx, $sequence] = $ctx->consume($_GET['state'] ?? null, $this->config, time());
        $contextId = $ctx->id;
        $ctx->close();
        // No native session or authorization/context lock during external requests.
        if (isset($_GET['error']) || (isset($_GET['iss']) && $_GET['iss'] !== $this->config->profile->issuer)) { throw new LoginFailed(LoginFailed::PROVIDER_ERROR); }
        $code = $_GET['code'] ?? null;
        if (!is_string($code) || !preg_match('/^[\x21-\x7e]{1,4096}$/D', $code)) { throw new LoginFailed(LoginFailed::CODE); }
        $identity = (new OidcClient($this->config, $this->transport, static fn() => time()))->complete($tx, $code);
        $claims = Claims::from($identity, $this->config->profile);
        $ctx = new LoginContext($this->private, $contextId);
        $ctx->finish($sequence, function () use ($claims, $sequence): void {
            if ($this->openSession() !== null) {
                session_write_close();
                throw new LoginFailed(LoginFailed::SIGNED_IN);
            }
            $owner = (new PrincipalWriter($this->private))->write($claims, $sequence, time(),
                $this->storage?->values['studentGroupIds'] ?? $this->config->profile->studentGroupIds,
                $this->storage !== null ? $this->storage->values['studentRoleId'] : $this->config->profile->studentRoleId,
                $this->config->profile->authorizationMapping());
            $this->issue($owner, $claims);
        });
        $ctx->close();
        $this->redirect($this->hasCad() ? '/cad.php' : '/');
    }
    public function logout(): never
    {
        $this->route(['/auth/logout.php']);
        $this->sameOriginPost();
        $ctx = $this->context();
        $ctx->checkCsrf($_POST['csrf'] ?? null);
        $session = $this->openSession();
        if (array_key_exists('cadCsrf', $_POST) && ($session === null || !is_string($_POST['cadCsrf'])
            || !hash_equals($session['csrf'], $_POST['cadCsrf']))) {
            throw new LoginFailed(LoginFailed::TRANSACTION);
        }
        $ctx->cancel();
        if ($session !== null) { $this->native->revoke(); }
        $ctx->close();
        $this->redirect($this->hasCad() ? '/index.php' : '/');
    }
}
