<?php
declare(strict_types=1);
namespace Sso\Layerling\Tests;
use Sso\Layerling\Oidc\{Config,LoginContext,Transaction};
use Sso\Layerling\Oidc\Http\{Transport,HttpResponse,TransportException};
use Firebase\JWT\JWT;
/** CLI-generated test bootstrap only. Never shipped in the hosted artifact. */
final class FakeProvider implements Transport
{
    public function __construct(private string $root) {}
    public function send(string $method, string $url, array $headers = [], ?array $form = null): HttpResponse
    {
        $f = json_decode(file_get_contents($this->root.'/fake.json'),true,32,JSON_THROW_ON_ERROR);
        $claims = ['iss'=>Config::ISSUER,'aud'=>'test-client','sub'=>'pairwise-fixture','nonce'=>$f['nonce'],
            'iat'=>time(),'exp'=>time()+3600,'iserv:uuid'=>'12345678-1234-1234-1234-123456789abc',
            'iserv:roles'=>[['id'=>'ROLE_STUDENT']], 'iserv:groups'=>[
                'maker-fixture'=>['id'=>'maker-fixture','name'=>'makerspace-betreuung'],
                'unrelated-fixture'=>['id'=>'unrelated-fixture','name'=>'Private unrelated group']]];
        $claims = array_replace($claims, $f['claims'] ?? []);
        if ($url === Config::TOKEN_URL) {
            file_put_contents($this->root.'/exchanges','x',FILE_APPEND|LOCK_EX);
            if (($form['code_verifier']??null)!==$f['verifier'] || ($form['redirect_uri']??null)!=='https://cad.example.invalid/auth/callback.php') { throw new TransportException('fixture PKCE'); }
            $claims['nonce']=$f['badNonce']??$claims['nonce'];
            $token=JWT::encode($claims,file_get_contents($this->root.'/key.pem'),'RS256','fixture-key');
            return new HttpResponse(200,[],json_encode(['token_type'=>'Bearer','id_token'=>$token,'access_token'=>'test-access-must-not-persist','refresh_token'=>'test-refresh-must-not-persist']));
        }
        if ($url===Config::JWKS_URL) { return new HttpResponse(200,[],file_get_contents($this->root.'/jwks.json')); }
        if ($url===Config::USERINFO_URL) {
            touch($this->root.'/network-active');
            if (isset($f['delayMicros'])) { usleep($f['delayMicros']); }
            if (!empty($f['badSub'])) { $claims['sub']='wrong'; }
            return new HttpResponse(200,[],json_encode($claims));
        }
        throw new TransportException('fixture endpoint');
    }
}
