<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
// PRIVATE/app/src/Oidc/cleanup.php. No secrets or personal records are read/output.
require dirname(__DIR__, 2) . '/vendor/autoload.php';
$private=dirname(__DIR__,3);
$removed=0;
foreach(['contexts'=>21600,'sso-sessions'=>3600,'sessions'=>\Sso\Layerling\StorageConfig::ABSOLUTE_SECONDS]as$directory=>$age){
    $root=$private.'/'.$directory;
    if ($directory==='sessions' && !file_exists($root)) { continue; }
    if (is_link($root)||!is_dir($root)) { fwrite(STDERR,"Invalid cleanup directory\n");exit(1); }
    foreach(new DirectoryIterator($root)as$file){
        if (!$file->isFile() || $file->isLink()) {continue;}
        $pattern=$directory==='contexts'?'/^[a-f0-9]{64}\.json$/D':'/^sess_[a-f0-9]{64}$/D';
        if (!preg_match($pattern,$file->getFilename()) || time()-$file->getMTime()<$age) {continue;}
        $handle=fopen($file->getPathname(),'r+b');
        if (!$handle) {continue;}
        if(flock($handle,LOCK_EX|LOCK_NB)){
            $stat=fstat($handle);
            if($stat && time()-$stat['mtime']>=$age && unlink($file->getPathname())){++$removed;}
            flock($handle,LOCK_UN);
        }
        fclose($handle);
    }
}
echo 'Expired SSO runtime files removed: '.$removed."\n";
