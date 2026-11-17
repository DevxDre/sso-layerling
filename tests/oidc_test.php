<?php
declare(strict_types=1);
require dirname(__DIR__) . '/vendor/autoload.php';
use Sso\Layerling\Oidc\{Config,Profile,Json,LoginFailed,Transaction,Identity,Claims,Jwks,IdTokenVerifier,OidcClient,LoginContext,PrincipalWriter};
use Sso\Layerling\Oidc\Http\{Transport,HttpResponse,TransportException,CurlTransport};
use Firebase\JWT\JWT;

function signToken(array $claims, string $key, string $alg, string $kid, array $header = []): string {
    $input = Transaction::base64url(json_encode($header + ['alg'=>$alg, 'kid'=>$kid], JSON_THROW_ON_ERROR)) . '.' . Transaction::base64url(json_encode($claims, JSON_THROW_ON_ERROR));
    if (!openssl_sign($input, $signature, $key, OPENSSL_ALGO_SHA256)) { throw new RuntimeException('Test signer'); }
    return $input . '.' . Transaction::base64url($signature);
}
function check(bool $condition): void { if (!$condition) { throw new RuntimeException('Assertion failed'); } }
function rejects(callable $fn): void { try { $fn(); } catch (LoginFailed|TransportException $e) { return; } throw new RuntimeException('Unexpected acceptance'); }
$passed = 0;
function test(string $name, callable $fn): void {
    global $passed;
    try { $fn(); ++$passed; echo "PASS $name\n"; }
    catch (Throwable $e) { fwrite(STDERR, "FAIL $name (" . get_class($e) . ")\n"); exit(1); }
}
final class Fake implements Transport {
    public array $calls = [];
    public function __construct(public array $keys, public array $tokens = [], public array $info = [], public ?string $broken = null) {}
    public function send(string $method, string $url, array $headers = [], ?array $form = null): HttpResponse {
        $this->calls[] = [$method, $url, $form];
        if ($this->broken === 'transport') { throw new TransportException('fixture'); }
        $body = match($url) { Profile::defaults()->endpoint('jwks') => ['keys' => $this->keys], Profile::defaults()->endpoint('token') => $this->tokens, Profile::defaults()->endpoint('userinfo') => $this->info };
        return new HttpResponse($this->broken === 'status' ? 500 : 200, [], $this->broken === 'json' ? '[]' : json_encode($body, JSON_THROW_ON_ERROR));
    }
}
$key = openssl_pkey_new(['private_key_bits' => 2048, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
openssl_pkey_export($key, $privateKey);
$details = openssl_pkey_get_details($key);
$jwk = ['kty'=>'RSA','use'=>'sig','alg'=>'RS256','kid'=>'fixture-key','n'=>Transaction::base64url($details['rsa']['n']),'e'=>Transaction::base64url($details['rsa']['e'])];
$config = new Config('test-client', str_repeat('s', 32));
$now = time();
$base = ['iss'=>Profile::defaults()->issuer,'aud'=>'test-client','sub'=>'pairwise-test-sub','nonce'=>'nonce', 'iat'=>$now,'exp'=>$now+3600,
 'iserv:uuid'=>'12345678-1234-1234-1234-123456789abc','iserv:roles'=>[['id'=>'ROLE_STUDENT']],
 'iserv:groups'=>['student-fixture'=>['id'=>'student-fixture','name'=>'Students']], 'name'=>'Fixture'];
$verify = static function(array $claims, array $header = [], ?string $signingKey = null, ?array $keys = null) use($config,$now,$privateKey,$jwk) {
 $token = signToken($claims, $signingKey ?? $privateKey, 'RS256', $header['kid'] ?? 'fixture-key', $header);
 return (new IdTokenVerifier($config,new Jwks(new Fake($keys ?? [$jwk]), $config->profile)))->verify($token,'nonce',$now);
};
test('valid signature and exact claims',fn()=>check($verify($base)['sub']===$base['sub']));
foreach ([['iss','https://evil.invalid'],['aud','other'],['aud',['test-client',7]],['aud',[]],['aud',['test-client','other']],['azp','other'],['exp',$now-61],['exp',(string)($now+100)],['iat',$now+61],['iat','bad'],['nbf',$now+61],['nbf','bad'],['sub',''],['nonce','wrong']] as $i=>[$claim,$value]) {
 test('claim rejection '.$i,fn()=>rejects(fn()=>$verify(array_replace($base,[$claim=>$value]))));
}
foreach (['exp','iat','sub','nonce','iss','aud'] as $claim) { test('missing '.$claim,function()use($base,$claim,$verify){$c=$base;unset($c[$claim]);rejects(fn()=>$verify($c));}); }
test('multiple audience with azp',fn()=>check($verify(array_replace($base,['aud'=>['other','test-client'],'azp'=>'test-client']))['azp']==='test-client'));
foreach (['crit'=>[], 'jku'=>'https://evil.invalid', 'x5u'=>'https://evil.invalid', 'jwk'=>$jwk] as $h=>$v) { test('header '.$h,fn()=>rejects(fn()=>$verify($base,[$h=>$v]))); }
test('unknown kid',fn()=>rejects(fn()=>$verify($base,['kid'=>'unknown'])));
test('duplicate key id',fn()=>rejects(fn()=>$verify($base,[],null,[$jwk,$jwk])));
foreach (['d'=>'private','p'=>'private','kty'=>'oct','use'=>'enc','alg'=>'HS256'] as $h=>$v) { test('JWK filter '.$h,fn()=>check(Jwks::filter(['keys'=>[array_replace($jwk,[$h=>$v])]])===[])); }
test('wrong signature',function()use($verify,$base){$k=openssl_pkey_new(['private_key_bits'=>2048]);openssl_pkey_export($k,$pem);rejects(fn()=>$verify($base,[],$pem));});
test('none algorithm and malformed token',function()use($config,$jwk,$now){foreach(['e30.e30.xxx','not-a-token',Transaction::base64url('{"alg":"none","kid":"fixture-key"}').'.e30.xxx']as$t){rejects(fn()=>(new IdTokenVerifier($config,new Jwks(new Fake([$jwk]), $config->profile)))->verify($t,'nonce',$now));}});
test('JWT globals restored after failure',function()use($verify,$base){JWT::$leeway=13;JWT::$timestamp=42;rejects(fn()=>$verify(array_replace($base,['nonce'=>'wrong'])));check(JWT::$leeway===13&&JWT::$timestamp===42);JWT::$leeway=0;JWT::$timestamp=null;});
$identity = static fn(array $c)=>new Identity(Profile::defaults()->issuer,$c['sub'],$c,$c,'site','/');
test('roles objects and groups normalized',function()use($identity,$base){$c=Claims::from($identity($base));check($c->roles===['ROLE_STUDENT']&&$c->groups===['student-fixture']&&$c->student([],'ROLE_STUDENT'));});
test('missing roles group fallback',function()use($identity,$base){$b=$base;unset($b['iserv:roles']);check(Claims::from($identity($b))->student(['student-fixture'],'ROLE_STUDENT'));});
test('empty roles group fallback',fn()=>check(Claims::from($identity(array_replace($base,['iserv:roles'=>[]])))->student(['student-fixture'],'ROLE_STUDENT')));
test('teacher and mixed roles block fallback',function()use($identity,$base){foreach([[['id'=>'ROLE_TEACHER']],[['id'=>'ROLE_STUDENT'],['id'=>'ROLE_TEACHER']]]as$roles){check(!Claims::from($identity(array_replace($base,['iserv:roles'=>$roles])))->student(['student-fixture'],'ROLE_STUDENT'));}});
foreach ([['iserv:roles',null],['iserv:roles',['ROLE_STUDENT']],['iserv:groups',null],['iserv:groups',['bad']],['iserv:groups',['a'=>['id'=>'b']]],['iserv:uuid','bad']] as$i=>[$h,$v]) {test('malformed normalized claim '.$i,fn()=>rejects(fn()=>Claims::from($identity(array_replace($base,[$h=>$v])))));}
test('empty groups accepted',fn()=>check(Claims::from($identity(array_replace($base,['iserv:groups'=>[]])))->groups===[]));
$tx=Transaction::create($config,$now,'site','/');
$claims=array_replace($base,['nonce'=>$tx->nonce]);
$token=signToken($claims,$privateKey,'RS256','fixture-key');
$tokens=['token_type'=>'Bearer','access_token'=>'opaque-fixture-access','refresh_token'=>'must-never-persist','id_token'=>$token];
test('complete PKCE flow with opaque access token',function()use($config,$jwk,$tokens,$claims,$tx,$now){$f=new Fake([$jwk],$tokens,$claims);$c=new OidcClient($config,$f,fn()=>$now);$id=$c->complete($tx,'fixture-code');check($id->subject===$claims['sub']&&count($f->calls)===3);check($f->calls[0][2]['code_verifier']===$tx->verifier&&$f->calls[0][2]['grant_type']==='authorization_code');check(str_contains($c->authorizationUrl($tx),'code_challenge_method=S256'));});
foreach(['sub'=>'other','iserv:uuid'=>'22345678-1234-1234-1234-123456789abc','iserv:roles'=>[],'aud'=>'other']as$h=>$v){test('UserInfo binding '.$h,fn()=>rejects(fn()=>(new OidcClient($config,new Fake([$jwk],$tokens,array_replace($claims,[$h=>$v])),fn()=>$now))->complete($tx,'code')));}
test('at_hash correct and incorrect',function()use($config,$jwk,$tokens,$claims,$tx,$now,$privateKey){foreach([true,false]as$good){$c=$claims;$c['at_hash']=$good?Transaction::base64url(substr(hash('sha256',$tokens['access_token'],true),0,16)):'wrong';$t=$tokens;$t['id_token']=signToken($c,$privateKey,'RS256','fixture-key');$fn=fn()=>(new OidcClient($config,new Fake([$jwk],$t,$claims),fn()=>$now))->complete($tx,'code');if($good){check($fn()instanceof Identity);}else{rejects($fn);}}});
foreach(['transport','status','json']as$broken){test('provider failure '.$broken,fn()=>rejects(fn()=>(new OidcClient($config,new Fake([$jwk],$tokens,$claims,$broken),fn()=>$now))->complete($tx,'code')));}
test('transport refuses arbitrary endpoint',fn()=>rejects(fn()=>(new CurlTransport(Profile::defaults()))->send('GET','http://127.0.0.1')));
$tmp=sys_get_temp_dir().'/sso-oidc-'.bin2hex(random_bytes(8));mkdir($tmp,0700);mkdir($tmp.'/contexts',0700);
try {
 file_put_contents($tmp.'/principals.json','{}');touch($tmp.'/authorization.lock');
 test('dotenv literal and permissions',function()use($tmp){$p=$tmp.'/.env';file_put_contents($p,"SSO_LAYERLING_OIDC_CLIENT_ID=test-client\nSSO_LAYERLING_OIDC_CLIENT_SECRET='literal-secret-value$"."x'\n");chmod($p,0600);check(Config::fromFile($p)->clientSecret()==='literal-secret-value$x');chmod($p,0644);rejects(fn()=>Config::fromFile($p));chmod($p,0600);file_put_contents($p,"SSO_LAYERLING_OIDC_CLIENT_ID=a\nSSO_LAYERLING_OIDC_CLIENT_ID=b\n");rejects(fn()=>Config::fromFile($p));});
 test('one use transaction and cancellation',function()use($tmp,$config,$now){$id=bin2hex(random_bytes(32));$c=new LoginContext($tmp,$id,true);$t=$c->begin($config,$now);rejects(fn()=>$c->consume('wrong',$config,$now));[$got,$seq]=$c->consume($t->state,$config,$now);check($got->verifier===$t->verifier);rejects(fn()=>$c->consume($t->state,$config,$now));$c->close();$c=new LoginContext($tmp,$id);$c->cancel();rejects(fn()=>$c->finish($seq,fn()=>true));$c->close();});
 test('expired transaction and persistent rate limit',function()use($tmp,$config,$now){$id=bin2hex(random_bytes(32));$c=new LoginContext($tmp,$id,true);$t=$c->begin($config,$now-300);rejects(fn()=>$c->consume($t->state,$config,$now));for($i=0;$i<5;$i++){$c->begin($config,$now);}$c->close();$c=new LoginContext($tmp,$id);rejects(fn()=>$c->begin($config,$now));$c->close();});
 test('stable owner, fresh classification and stale writer',function()use($tmp,$base,$identity,$now){$w=new PrincipalWriter($tmp);$c=Claims::from($identity($base));$owner=$w->write($c,10,$now,[],'ROLE_STUDENT');check(strlen($owner)===32);$b=$base;$b['iserv:roles']=[['id'=>'ROLE_TEACHER']];$b['iserv:groups']=[];$next=Claims::from($identity($b));check($w->write($next,11,$now) === $owner);$stored=json_decode(file_get_contents($tmp.'/principals.json'),true);check($stored[$owner]['student']===false&&$stored[$owner]['groups']===[]);rejects(fn()=>$w->write($c,10,$now));$stored[$owner]['enabled']=false;file_put_contents($tmp.'/principals.json',json_encode($stored));rejects(fn()=>$w->write($c,12,$now));});
} finally {
 foreach(new RecursiveIteratorIterator(new RecursiveDirectoryIterator($tmp,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST)as$p){$p->isDir()?rmdir($p->getPathname()):unlink($p->getPathname());}rmdir($tmp);
}
echo "$passed OIDC core groups passed. No real provider/account/configuration used.\n";
