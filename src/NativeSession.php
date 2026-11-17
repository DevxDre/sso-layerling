<?php
declare(strict_types=1);
namespace Sso\Layerling;

/** One native session contract for OIDC and file access. open() retains the native lock. */
final class NativeSession
{
    public function __construct(private string $private, private string $directory, private string $cookie,
        private bool $secure, private int $absolute = 3600, private int $idle = 900, private ?string $scope = null) {}
    private function setup(bool $cookies = true): void
    {
        ini_set('session.use_strict_mode', '1');
        ini_set('session.use_cookies', $cookies ? '1' : '0');
        ini_set('session.use_only_cookies', '1');
        ini_set('session.use_trans_sid', '0');
        ini_set('session.gc_maxlifetime', (string)$this->absolute);
        session_name($this->cookie);
        session_save_path($this->private . '/' . $this->directory);
        if ($cookies) {
            session_set_cookie_params(['path'=>'/','secure'=>$this->secure,'httponly'=>true,'samesite'=>'Lax']);
        }
    }
    private function cookie(string $value, int $expires = 0): void
    {
        setcookie($this->cookie, $value, ['expires'=>$expires,'path'=>'/','secure'=>$this->secure,'httponly'=>true,'samesite'=>'Lax']);
    }
    public function open(?string $trustedId = null): ?array
    {
        $id = $trustedId ?? ($_COOKIE[$this->cookie] ?? null);
        if (!is_string($id) || !preg_match('/^[a-f0-9]{64}$/D', $id)) { return null; }
        $file = $this->private . '/' . $this->directory . '/sess_' . $id;
        if (!is_file($file) || is_link($file)) { return null; }
        // A token lookup supplies the ID internally. Never send that session as a cookie to the client.
        $this->setup($trustedId === null);
        session_id($id);
        if (!session_start() || !hash_equals($id, session_id())) { $this->revoke($trustedId === null); return null; }
        $s = $_SESSION; $now = time();
        if (($s['authorized']??null)!==true
            || !is_string($s['userId']??null) || !preg_match('/^[a-f0-9]{32}$/D',$s['userId'])
            || !is_string($s['csrf']??null) || !preg_match('/^[a-f0-9]{64}$/D',$s['csrf'])
            || !is_int($s['issuedAt']??null) || !is_int($s['lastSeen']??null)
            || $s['issuedAt']>$now || $s['lastSeen']<$s['issuedAt'] || $s['lastSeen']>$now
            || $now-$s['issuedAt'] >= $this->absolute || $now-$s['lastSeen'] >= $this->idle
            || ($this->scope!==null && ($s['scope']??null)!==$this->scope)) {
            $this->revoke($trustedId === null); return null;
        }
        return $_SESSION;
    }
    public function issue(string $owner, array $diagnostic): void
    {
        if (session_status()===PHP_SESSION_ACTIVE || !preg_match('/^[a-f0-9]{32}$/D',$owner)) {
            throw new \RuntimeException('Invalid session issuance');
        }
        $this->setup();
        ini_set('session.use_strict_mode','0');
        do { $id=bin2hex(random_bytes(32)); } while (file_exists($this->private.'/'.$this->directory.'/sess_'.$id));
        session_id($id);
        if (!session_start()) { throw new \RuntimeException('Session issuance failed'); }
        $_SESSION=['authorized'=>true,'userId'=>$owner,'csrf'=>bin2hex(random_bytes(32)),
            'issuedAt'=>time(),'lastSeen'=>time(),'diagnostic'=>$diagnostic];
        if ($this->scope!==null) { $_SESSION['scope']=$this->scope; }
        if (!session_write_close()) { throw new \RuntimeException('Session issuance failed'); }
        $this->cookie($id);
    }
    public function revoke(bool $clearCookie = true): void
    {
        SessionRevocation::revoke();
        if ($clearCookie) { $this->cookie('',1); }
    }
}
