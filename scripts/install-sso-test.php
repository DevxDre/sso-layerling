<?php
declare(strict_types=1);
/** Install a verified Layerling test package on the configured PHP host. */
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
ini_set('display_errors', '0');
umask(0077);
function demand(bool $ok, string $reason): void { if (!$ok) { throw new RuntimeException($reason); } }
function directory(string $path): void {
    demand(!is_link($path), 'Symlink directory refused');
    if (!is_dir($path)) { demand(mkdir($path,0700), 'Cannot create directory'); }
    demand(realpath($path)===$path && is_writable($path), 'Noncanonical/unwritable directory');
}
function copyTree(string $from, string $to): void {
    directory($to);
    foreach (new DirectoryIterator($from) as $item) {
        if ($item->isDot()) { continue; }
        demand(!$item->isLink(), 'Symlink refused');
        $target=$to.'/'.$item->getFilename();
        if ($item->isDir()) { copyTree($item->getPathname(),$target); }
        else { demand(copy($item->getPathname(),$target) && chmod($target,0600),'Copy failed'); }
    }
}
function jsonFile(string $path): array
{
    demand(is_file($path) && !is_link($path), 'Missing or linked metadata');
    $data = json_decode(file_get_contents($path), true, 32, JSON_THROW_ON_ERROR);
    demand(is_array($data), 'Invalid metadata');
    return $data;
}

function publicFiles(string $root): array
{
    $files = [];
    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::SELF_FIRST
    );
    foreach ($iterator as $file) {
        demand(!$file->isLink(), 'Public symlink refused');
        $relative = substr($file->getPathname(), strlen($root) + 1);
        if (str_starts_with($relative, '.well-known/')) {
            continue;
        }
        if (!$file->isDir()) {
            demand($file->isFile(), 'Unexpected public entry');
            $files[$relative] = hash_file('sha256', $file->getPathname());
        }
    }
    ksort($files);
    return $files;
}

function templateFiles(string $app): array
{
    return is_file($app.'/src/TemplateCatalog.php') ? ['vorlagen.php', 'vorlagen.js'] : [];
}

const CAD_ENTRY_FILES = ['konto/index.php', 'files/index.php'];

/** Accept only the fixed controllers and the static export described by the private build report. */
function cadFiles(string $app, array $files, array $baseFiles): void
{
    $bundle = jsonFile($app.'/cad/manifest.json');
    $build = jsonFile($app.'/cad/build.json');
    $pin = jsonFile($app.'/upstream.lock.json');
    demand(($bundle['kind'] ?? null) === 'sso-layerling-cad-owner-v2'
        && is_array($bundle['source'] ?? null) && $bundle['source'] === ($build['source'] ?? null)
        && ($build['source']['commit'] ?? null) === ($pin['commit'] ?? null)
        && is_string($bundle['indexSha256'] ?? null)
        && $bundle['indexSha256'] === ($build['files']['index.html'] ?? null)
        && $bundle['indexSha256'] === hash_file('sha256', $app.'/cad/index.html')
        && ($build['files']['store.php'] ?? null) === ($pin['sha256'] ?? null), 'CAD build integrity mismatch');
    $controllers = [...$baseFiles, ...templateFiles($app), 'cad.php', 'cad-session.php', 'cad-bridge.js', 'cad-bridge.css'];
    if (($bundle['entryRoutes'] ?? null) === 'cad-first-v1') {
        array_push($controllers, ...CAD_ENTRY_FILES);
    }
    $excluded = ['index.html', 'index.txt', 'store.php', 'sw.js', 'manifest.webmanifest', 'support.html',
        'view.html', '404.html', 'robots.txt', 'sitemap.xml'];
    $assets = [];
    foreach ($build['files'] as $path => $hash) {
        if (in_array($path, $excluded, true) || str_starts_with($path, '404/')) {
            continue;
        }
        demand(preg_match('~^[a-zA-Z0-9_-][a-zA-Z0-9_.-]*(?:/[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)*$~D', $path) === 1
            && !str_starts_with($path, 'auth/')
            && !in_array($path, $controllers, true)
            && !preg_match('/\.(?:php[0-9]*|phtml|phar|cgi|pl|shtml)(?:\.|$)/i', basename($path))
            && preg_match('/\.(?:css|html|ico|js|json|png|svg|txt|wasm|webp)$/D', $path) === 1
            && (!str_ends_with($path, '.html') || str_contains($path, '/')), 'Unexpected CAD asset');
        demand(($files[$path] ?? null) === $hash, 'CAD asset checksum mismatch');
        $assets[] = $path;
    }
    demand(isset($files['version.json'], $files['manifold.wasm'])
        && count(array_filter($assets, static fn($p) => str_starts_with($p, '_next/static/'))) > 0, 'Incomplete CAD export');
    $expected = [...$controllers, ...$assets];
    $actual = array_keys($files);
    sort($expected);
    sort($actual);
    demand($actual === $expected, 'Unexpected public controller or asset');
}

function parentDirectories(string $root, string $relative): void
{
    $path = $root;
    $components = explode('/', $relative);
    array_pop($components);
    foreach ($components as $component) {
        $path .= '/'.$component;
        directory($path);
    }
}

function replaceFile(string $from, string $to): void
{
    $temp = $to.'.deploy-'.bin2hex(random_bytes(8));
    try {
        demand(copy($from, $temp) && chmod($temp, 0600) && rename($temp, $to), 'Cannot activate file');
    } finally {
        if (is_file($temp)) {
            unlink($temp);
        }
    }
}

try {
    demand(PHP_VERSION_ID>=80400 && PHP_VERSION_ID<80500,'Use php8.4');
    foreach (['curl','json','openssl','session'] as $extension) { demand(extension_loaded($extension),'Missing PHP extension'); }
    $options=getopt('', ['package:','base:','public:','local-test','cad-test']);
    $package=realpath($options['package']??'');
    demand(is_string($package),'Package directory required');
    $base=$options['base']??'/home/repos/sso-layerling';
    $public=$options['public']??'/home/www/layerling';
    if (isset($options['base']) || isset($options['public'])) {
        $tmp=realpath(sys_get_temp_dir());
        demand(isset($options['local-test']) && is_string($tmp)
            && str_starts_with($base,$tmp.'/') && str_starts_with($public,$tmp.'/'),'Path overrides only for isolated local installer tests');
    }
    demand(!str_starts_with($base.'/',$public.'/') && !str_starts_with($public.'/',$base.'/'),'Overlapping public/private directories');
    $manifestPath=$package.'/manifest.json';
    demand(is_file($manifestPath) && !is_link($manifestPath),'Missing manifest');
    $manifest=jsonFile($manifestPath);
    demand(in_array($manifest['kind']??null,['sso-layerling-sso-test','sso-layerling-storage-test','sso-layerling-cad-test'],true)
        && is_string($manifest['sourceCommit']??null) && preg_match('/^[a-f0-9]{40}$/D',$manifest['sourceCommit'])===1
        && ($manifest['installedPrivate']??null)===$base.'/private','Uncommitted or wrong-target package refused');
    $cadTest = $manifest['kind'] === 'sso-layerling-cad-test';
    demand($cadTest === isset($options['cad-test']), 'CAD test installation requires --cad-test');
    demand(!str_starts_with($package.'/', $public.'/') && !str_starts_with($package.'/', $base.'/private/'), 'Package overlaps active runtime');
    $actual=[];
    foreach(new RecursiveIteratorIterator(new RecursiveDirectoryIterator($package,FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::SELF_FIRST) as $file) {
        demand(!$file->isLink(),'Symlink refused');
        if ($file->isDir()) { continue; }
        demand($file->isFile(), 'Unexpected package entry');
        $relative=substr($file->getPathname(),strlen($package)+1);
        if ($relative==='manifest.json') { continue; }
        demand((str_starts_with($relative,'private/app/') || str_starts_with($relative,'public/'))
            && !str_starts_with(basename($relative),'.env'),'Unexpected package path');
        $actual[$relative]=hash_file('sha256',$file->getPathname());
    }
    $expected=$manifest['files']??[];ksort($actual);ksort($expected);
    demand($actual===$expected,'Package checksum mismatch');
    $publicFiles=['index.php','_sso.php','.sso-layerling-sso-test','auth/start.php','auth/callback.php','auth/logout.php'];
    $storageTest = $manifest['kind'] !== 'sso-layerling-sso-test';
    $managedFiles = [...$publicFiles, 'files.php', 'files.js', 'files.css', 'store.php', 'session.php', 'owners.php'];
    $templateFiles = $storageTest ? templateFiles($package.'/private/app') : [];
    $packagePublic = [];
    foreach ($actual as $path => $hash) {
        if (str_starts_with($path, 'public/')) {
            $packagePublic[substr($path, 7)] = $hash;
        }
    }
    $staticFiles = [];
    if ($cadTest) {
        cadFiles($package.'/private/app', $packagePublic, $managedFiles);
        $publicFiles = array_keys($packagePublic);
        $controllers = [...$managedFiles, ...$templateFiles, ...CAD_ENTRY_FILES, 'cad.php', 'cad-session.php', 'cad-bridge.js', 'cad-bridge.css'];
        $staticFiles = array_diff($publicFiles, $controllers);
        $publicFiles = [...array_diff($publicFiles, $staticFiles, ['cad.php', 'index.php']), 'cad.php', 'index.php'];
    } else {
        if ($storageTest) {
            $publicFiles = [...$managedFiles, ...$templateFiles];
        }
        $expectedPublic = array_keys($packagePublic);
        sort($expectedPublic);
        $allowed = $publicFiles;
        sort($allowed);
        demand($expectedPublic === $allowed, 'Unexpected public controller');
    }
    demand(is_dir(dirname($base)) && is_dir(dirname($public)), 'Create parent directories first');
    directory($base);
    directory($public);
    directory($base.'/private');
    $lock = fopen($base.'/deploy.lock', 'c+b');
    demand($lock !== false && flock($lock, LOCK_EX | LOCK_NB), 'Another installation is running');
    $app = $base.'/private/app';
    $deployment = $base.'/private/deployment.json';
    $previous = file_exists($deployment) ? jsonFile($deployment) : [];
    $existing = publicFiles($public);
    if (($previous['kind'] ?? null) === 'sso-layerling-cad-test') {
        cadFiles($app, $existing, $managedFiles);
        demand($existing === ($previous['publicFiles'] ?? null), 'Installed CAD files changed');
    } else {
        demand(array_diff(array_keys($existing), [...$managedFiles, ...templateFiles($app)]) === [], 'Existing website files refused; inspect the webroot first');
    }
    demand($existing === [] || isset($existing['.sso-layerling-sso-test']), 'Unmanaged website refused');
    require $package.'/private/app/vendor/autoload.php';
    $profile = \Sso\Layerling\Oidc\Profile::load($package.'/private/app/oidc-profile.json');
    $config = \Sso\Layerling\Oidc\Config::fromFile($base.'/.env', $profile);
    $target=jsonFile($package.'/private/app/deployment-target.json');
    $expectedClient=$target['clientId']??null;
    demand(is_string($expectedClient) && (
        ($expectedClient==='' && isset($options['local-test']))
        || ($expectedClient!=='' && $expectedClient!=='test-client' && hash_equals($expectedClient,$config->clientId))
    ),'Wrong registered client');
    $identityContract = $profile->identityContract();
    if ($identityContract[1] === 'sub') {
        // A different client registration may get a different pairwise subject.
        $identityContract[] = $config->clientId;
    }
    $previousContract = $previous['oidcIdentity'] ?? null;
    $legacyStudentBasis = $previous['legacyStudentBasis'] ?? null;
    if ($previousContract === null && is_dir($app)) {
        // Packages before profiles embedded the issuer in the private Config source.
        $legacy = $app.'/src/Oidc/Config.php';
        demand(is_file($legacy) && !is_link($legacy) && filesize($legacy) <= 16384
            && preg_match("/public const ISSUER = '([^']+)';/", (string) file_get_contents($legacy), $match) === 1,
            'Cannot verify previous identity binding');
        $legacyProfile = \Sso\Layerling\Oidc\Profile::defaults();
        $previousContract = [$match[1], ...array_slice($legacyProfile->identityContract(), 1)];
        if (is_file($app.'/storage.json')) {
            $legacyStorage = jsonFile($app.'/storage.json');
            $legacyStudentBasis = ['role' => $legacyStorage['studentRoleId'], 'groups' => $legacyStorage['studentGroupIds']];
        }
    }
    $registry = $base.'/private/principals.json';
    if ($previousContract === null && is_file($registry)) {
        demand(jsonFile($registry) === [], 'Existing principals require an explicit identity migration');
    }
    demand($previousContract === null || $previousContract === $identityContract,
        'Changing issuer or identity mapping requires an explicit migration');
    if ($storageTest) {
        foreach (['zip','mbstring','fileinfo'] as $extension) { demand(extension_loaded($extension),'Missing storage PHP extension'); }
        $storage=\Sso\Layerling\StorageConfig::load($package.'/private/app/storage.json');
        demand($storage->values['publicRoot']===$public && $storage->values['origin']===$profile->origin,'Wrong storage target');
        demand($storage->values['studentRoleId'] === $profile->studentRoleId
            && $storage->values['studentGroupIds'] === $profile->studentGroupIds
            && ($storage->values['authorizationMapping'] ?? null) === $profile->authorizationMapping()
            && ($storage->values['templatePublisherRoleIds'] ?? null) === $profile->provider['templatePublisherRoleIds'],
            'Inconsistent OIDC authorization configuration');
        $pin=json_decode(file_get_contents($package.'/private/app/upstream.lock.json'),true,16,JSON_THROW_ON_ERROR);
        demand(is_string($pin['sha256']??null) && hash_equals($pin['sha256'],hash_file('sha256',$package.'/private/app/upstream/store.php')),'Upstream integrity mismatch');
    }
    foreach($storageTest ? ['contexts','sso-sessions','sessions','projects'] : ['contexts','sso-sessions'] as $dir) { directory($base.'/private/'.$dir); }
    if ($templateFiles !== []) { directory($base.'/private/templates'); }
    foreach(['authorization.lock'=>'','principals.json'=>"{}\n"]as$file=>$initial){
        $path=$base.'/private/'.$file;
        demand(!is_link($path),'Runtime symlink refused');
        if (!file_exists($path)) { demand(file_put_contents($path,$initial)!==false,'Cannot initialize private runtime'); }
    }
    if ($storageTest && !file_exists($base.'/private/audit.jsonl')) { demand(file_put_contents($base.'/private/audit.jsonl','')!==false,'Cannot initialize audit'); }
    demand(!is_link($base.'/private/audit.jsonl'),'Audit symlink refused');
    $stage = $base.'/private/.app-'.bin2hex(random_bytes(8));
    copyTree($package.'/private/app', $stage);
    demand(!is_link($app), 'Existing app symlink refused');
    $backup = null;
    if (is_dir($app) || $existing !== []) {
        directory($base.'/backups');
        $backup = $base.'/backups/'.gmdate('Ymd-His').'-'.bin2hex(random_bytes(4));
        directory($backup);
        directory($backup.'/public');
        foreach (array_keys($existing) as $file) {
            parentDirectories($backup.'/public', $file);
            demand(copy($public.'/'.$file, $backup.'/public/'.$file), 'Cannot back up public file');
        }
        if (is_file($deployment)) {
            demand(copy($deployment, $backup.'/deployment.json'), 'Cannot back up deployment metadata');
        }
    }
    $oldMoved = false;
    $appActive = false;
    $touched = [];
    $metadata = $stage.'.deployment.json';
    ksort($packagePublic);
    try {
        demand(file_put_contents($metadata, json_encode(['sourceCommit'=>$manifest['sourceCommit'],
            'installedAt'=>gmdate(DATE_ATOM), 'kind'=>$manifest['kind'], 'publicFiles'=>$packagePublic,
            'oidcIdentity'=>$identityContract, 'legacyStudentBasis'=>$legacyStudentBasis],
            JSON_THROW_ON_ERROR)) !== false, 'Cannot prepare deployment metadata');
        foreach ($staticFiles as $file) {
            parentDirectories($public, $file);
            replaceFile($package.'/public/'.$file, $public.'/'.$file);
            $touched[] = $file;
        }
        if (!$cadTest && isset($existing['cad.php'])) {
            demand(unlink($public.'/cad.php'), 'Cannot disable previous CAD entry');
            $touched[] = 'cad.php';
        }
        if (is_dir($app)) {
            demand(rename($app, $backup.'/app'), 'Cannot back up previous app');
            $oldMoved = true;
        }
        demand(rename($stage, $app), 'Cannot activate private app');
        $appActive = true;
        foreach ($publicFiles as $file) {
            parentDirectories($public, $file);
            replaceFile($package.'/public/'.$file, $public.'/'.$file);
            $touched[] = $file;
        }
        foreach (array_diff(array_keys($existing), $publicFiles, $staticFiles, $touched) as $file) {
            demand(unlink($public.'/'.$file), 'Cannot remove previous managed file');
            $touched[] = $file;
        }
        demand(rename($metadata, $deployment), 'Cannot record deployment');
    } catch (Throwable $error) {
        $restored = true;
        foreach (array_reverse($touched) as $file) {
            $ok = isset($existing[$file])
                ? rename($backup.'/public/'.$file, $public.'/'.$file)
                : unlink($public.'/'.$file);
            $restored = $ok && $restored;
        }
        if ($appActive) {
            $restored = rename($app, $stage) && $restored;
        }
        if ($oldMoved) {
            $restored = rename($backup.'/app', $app) && $restored;
        }
        if (is_file($metadata)) {
            unlink($metadata);
        }
        demand($restored, 'Activation failed and restoration needs operator attention');
        throw $error;
    }
    if ($backup !== null) {
        echo 'Previous code backup: '.$backup."\n";
    }
    flock($lock,LOCK_UN);fclose($lock);
    echo "Test installation complete. Secret and runtime data preserved.\n";
    echo $cadTest ? "Next: sign in and open /cad.php.\n" : ($storageTest ? "Next: sign in again, open /files.php and test personal files. CAD remains disabled.\n" : "Next: test SSO login/logout. CAD/storage remain disabled.\n");
} catch(Throwable $e) {
    fwrite(STDERR,"Installation stopped: ".($e instanceof RuntimeException?$e->getMessage():'configuration/package check failed').". No credentials printed.\n");
    exit(1);
}
