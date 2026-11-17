#!/usr/bin/env python3
"""Real local HTTP tests, synthetic provider injected only in a temporary CLI-server bootstrap."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
from http.cookies import SimpleCookie
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--php',required=True)
OPTIONS,remaining=parser.parse_known_args()
spec=importlib.util.spec_from_file_location('sso_package',ROOT/'scripts/package-sso-test.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)

class Client:
    def __init__(self,test): self.test=test;self.cookies={}
    def request(self,path='/',method='GET',form=None,headers=None):
        h={'Cookie':'; '.join(k+'='+v for k,v in self.cookies.items())}
        if form is not None:
            h.update({'Origin':self.test.origin,'Content-Type':'application/x-www-form-urlencoded'})
        h.update(headers or {})
        c=http.client.HTTPConnection('127.0.0.1',self.test.port,timeout=6)
        try:
            c.request(method,path,body=urlencode(form) if form is not None else None,headers=h)
            response=c.getresponse();raw=response.getheaders();body=response.read()
            for k,v in raw:
                if k.lower()=='set-cookie':
                    for name,morsel in SimpleCookie(v).items(): self.cookies[name]=morsel.value
            return response.status,{k.lower():v for k,v in raw},body
        finally: c.close()

class SsoHTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='sso-sso-http-');cls.addClassCleanup(cls.tmp.cleanup)
        cls.root=Path(cls.tmp.name)
        with socket.socket() as sock: sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.origin=f'http://127.0.0.1:{cls.port}'
        cls.runtime=package.package(cls.root/'runtime',str(cls.root/'runtime/private'))
        cls.private=cls.runtime/'private'
        for name in ['contexts','sso-sessions']: (cls.private/name).mkdir(mode=0o700)
        (cls.private/'principals.json').write_text('{}')
        (cls.private/'authorization.lock').touch()
        fixture=r"""
        $k=openssl_pkey_new(['private_key_bits'=>2048]);openssl_pkey_export($k,$pem);
        file_put_contents($argv[1].'/key.pem',$pem);$d=openssl_pkey_get_details($k);
        $b=fn($v)=>rtrim(strtr(base64_encode($v),'+/','-_'),'=');
        file_put_contents($argv[1].'/jwks.json',json_encode(['keys'=>[['kty'=>'RSA','use'=>'sig','alg'=>'RS256','kid'=>'fixture-key','n'=>$b($d['rsa']['n']),'e'=>$b($d['rsa']['e'])]]]));
        """
        subprocess.run([OPTIONS.php,'-r',fixture,str(cls.root)],check=True,capture_output=True)
        def phpstr(p): return "'"+str(p).replace('\\','\\\\').replace("'","\\'")+"'"
        bootstrap="""<?php
        require %s;
        require %s;
        \\Sso\\Layerling\\Oidc\\Web::headers();
        set_exception_handler(static function(\\Throwable $e):void{http_response_code(503);echo 'Login not completed';});
        $profile = \\Sso\\Layerling\\Oidc\\Profile::load(%s);
        $config = new \\Sso\\Layerling\\Oidc\\Config('test-client',str_repeat('s',32),$profile);
        return new \\Sso\\Layerling\\Oidc\\Web(%s,$config,new \\Sso\\Layerling\\Tests\\FakeProvider(%s,$config),%s);
        """%(phpstr(cls.private/'app/vendor/autoload.php'),phpstr(ROOT/'tests/FakeProvider.php'),
              phpstr(cls.private/'app/oidc-profile.json'),phpstr(cls.private),phpstr(cls.root),phpstr(cls.origin))
        (cls.runtime/'public/_sso.php').write_text(bootstrap)
        cls.log=open(cls.root/'server.log','w+');cls.addClassCleanup(cls.log.close)
        env=dict(os.environ);env['PHP_CLI_SERVER_WORKERS']='4'
        router = [str(cls.router)] if getattr(cls, 'router', None) else []
        cls.server=subprocess.Popen([OPTIONS.php,'-d','display_errors=0','-d','log_errors=1','-S',f'127.0.0.1:{cls.port}','-t',str(cls.runtime/'public'),*router],stdout=cls.log,stderr=cls.log,env=env,start_new_session=True)
        cls.addClassCleanup(cls.stop)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1',cls.port),timeout=.1):return
            except OSError:time.sleep(.03)
        raise RuntimeError('PHP server did not start')
    @classmethod
    def stop(cls):
        os.killpg(cls.server.pid,signal.SIGTERM)
        try:cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(cls.server.pid,signal.SIGKILL);cls.server.wait()
    def setUp(self):
        self.client=Client(self)
        for name in ['exchanges','network-active']:
            (self.root/name).unlink(missing_ok=True)
        self.settings={}
    def page(self,client=None):
        c=client or self.client;r=c.request(getattr(self, 'login_page', '/'));self.assertEqual(r[0],200)
        csrf=re.search(rb'name="csrf" value="([a-f0-9]{64})"',r[2])
        self.assertIsNotNone(csrf)
        return csrf[1].decode(),r
    def begin(self,client=None,**flags):
        c=client or self.client;csrf,_=self.page(c)
        response=c.request('/auth/start.php','POST',{'csrf':csrf})
        return self.callback_for_redirect(c, response, **flags), csrf
    def callback_for_redirect(self, c, response, **flags):
        self.assertEqual(response[0],303,response[2])
        query=parse_qs(urlsplit(response[1]['location']).query)
        context=json.loads((self.private/'contexts'/(c.cookies['SSO_LAYERLING_LOGIN']+'.json')).read_text())
        self.settings={'nonce':query['nonce'][0],'verifier':context['transaction']['verifier'],**flags}
        (self.root/'fake.json').write_text(json.dumps(self.settings))
        self.assertEqual(query['code_challenge_method'],['S256'])
        expected=__import__('base64').urlsafe_b64encode(hashlib.sha256(self.settings['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'],[expected])
        return '/auth/callback.php?'+urlencode({'state':query['state'][0],'code':'fixture-code'})
    def exchanges(self):
        p=self.root/'exchanges';return len(p.read_text()) if p.exists() else 0
    def test_01_package_excludes_secrets_and_storage(self):
        manifest=json.loads((self.runtime/'manifest.json').read_text())
        self.assertFalse(any(Path(p).name=='.env' or p.startswith('tests/') for p in manifest['files']))
        self.assertFalse((self.runtime/'public/store.php').exists())
        self.assertFalse((self.runtime/'public/session.php').exists())
        self.assertTrue((self.private/'app/vendor/firebase/php-jwt/LICENSE').exists())
        self.assertEqual(self.client.request('/store.php')[0],404)
    def test_02_page_headers_and_anonymous_context(self):
        _,r=self.page()
        self.assertEqual(r[1]['cache-control'],'private, no-store')
        self.assertEqual(r[1]['referrer-policy'],'same-origin')
        self.assertIn("frame-ancestors 'none'",r[1]['content-security-policy'])
        self.assertIn('HttpOnly',r[1]['set-cookie']);self.assertIn('SameSite=Lax',r[1]['set-cookie'])
        self.assertNotIn('SSO_LAYERLING_SSO_TEST',self.client.cookies)
    def test_03_start_rejects_csrf_origin_and_get(self):
        csrf,_=self.page()
        for path,method,form,headers in [('/auth/start.php','GET',None,{}),('/auth/start.php','POST',{'csrf':'bad'},{}),('/auth/start.php','POST',{'csrf':csrf},{'Origin':'https://evil.invalid'}),('/auth/start.php','POST',{'csrf':csrf},{'Origin':'null'}),('/auth/start.php','POST',{'csrf':csrf},{'Origin':''})]:
            self.assertEqual(self.client.request(path,method,form,headers)[0],503)
        self.assertEqual(self.exchanges(),0)
    def test_04_valid_login_diagnostics_and_logout(self):
        cb,csrf=self.begin()
        old=self.client.cookies['SSO_LAYERLING_LOGIN']
        self.assertEqual(self.client.request(cb)[0],303)
        sid=self.client.cookies['SSO_LAYERLING_SSO_TEST'];self.assertNotEqual(sid,old)
        _,r=self.page();self.assertIn('Anmeldung über IServ erfolgreich'.encode(),r[2])
        self.assertIn(b'maker-fixture',r[2]);self.assertNotIn(b'Private unrelated group',r[2]);self.assertNotIn(b'unrelated-fixture',r[2])
        self.assertEqual(self.client.request('/auth/start.php','POST',{'csrf':csrf})[0],503)
        self.assertEqual(self.client.request('/auth/logout.php','POST',{'csrf':csrf})[0],303)
        self.assertEqual((self.private/'sso-sessions'/('sess_'+sid)).read_bytes(),b'')
        stale=Client(self);stale.cookies={'SSO_LAYERLING_SSO_TEST':sid}
        self.assertNotIn('Anmeldung über IServ erfolgreich'.encode(),self.page(stale)[1][2])
        self.assertEqual(self.exchanges(),1)
    def test_05_callback_replay(self):
        cb,_=self.begin();self.assertEqual(self.client.request(cb)[0],303)
        self.assertEqual(self.client.request(cb)[0],503);self.assertEqual(self.exchanges(),1)
    def test_06_forged_state_and_missing_context(self):
        cb,_=self.begin()
        self.assertEqual(Client(self).request(cb)[0],503)
        self.assertEqual(self.client.request('/auth/callback.php?state=wrong&code=fixture')[0],503)
        self.assertEqual(self.exchanges(),0)
    def test_07_duplicate_and_array_callback_parameters(self):
        cb,_=self.begin()
        for extra in ['&code=duplicate','&state=duplicate','&code%5B%5D=bad']:
            self.assertEqual(self.client.request(cb+extra)[0],503)
        self.assertEqual(self.exchanges(),0)
    def test_08_provider_error_consumes_without_exchange(self):
        cb,_=self.begin();cb=cb.replace('code=fixture-code','error=invalid_request&error_description=PRIVATE_PROVIDER_TEXT')
        r=self.client.request(cb);self.assertEqual(r[0],503);self.assertNotIn(b'PRIVATE_PROVIDER_TEXT',r[2])
        self.assertEqual(self.exchanges(),0)
        self.assertEqual(self.client.request(cb)[0],503)
    def test_09_bad_nonce_and_userinfo_cannot_issue_session(self):
        for flags in [{'badNonce':'wrong'},{'badSub':True}]:
            self.client=Client(self);cb,_=self.begin(**flags)
            self.assertEqual(self.client.request(cb)[0],503)
            self.assertNotIn('SSO_LAYERLING_SSO_TEST',self.client.cookies)
    def test_10_cancel_before_callback(self):
        cb,csrf=self.begin();self.assertEqual(self.client.request('/auth/logout.php','POST',{'csrf':csrf})[0],303)
        self.assertEqual(self.client.request(cb)[0],503);self.assertEqual(self.exchanges(),0)
    def test_11_parallel_callback_only_one_exchange(self):
        cb,_=self.begin(delayMicros=300000)
        peer=Client(self);peer.cookies=dict(self.client.cookies)
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(self.client.request,cb);b=pool.submit(peer.request,cb)
            self.assertEqual(sorted([a.result()[0],b.result()[0]]),[303,503])
        self.assertEqual(self.exchanges(),1)
    def test_12_logout_during_external_request_prevents_issue(self):
        cb,csrf=self.begin(delayMicros=600000)
        peer=Client(self);peer.cookies=dict(self.client.cookies)
        with ThreadPoolExecutor(2) as pool:
            pending=pool.submit(self.client.request,cb)
            for _ in range(150):
                if (self.root/'network-active').exists():break
                time.sleep(.01)
            self.assertTrue((self.root/'network-active').exists())
            self.assertEqual(peer.request('/auth/logout.php','POST',{'csrf':csrf})[0],303)
            self.assertEqual(pending.result()[0],503)
        self.assertNotIn('SSO_LAYERLING_SSO_TEST',self.client.cookies)
    def test_13_host_and_proxy_headers(self):
        self.assertEqual(self.client.request(headers={'Host':'evil.invalid','X-Forwarded-Host':f'127.0.0.1:{self.port}'})[0],503)
        self.assertEqual(self.client.request(headers={'X-Forwarded-Proto':'https','X-Forwarded-Host':'evil.invalid'})[0],200)
    def test_14_test_tokens_not_persisted(self):
        cb,_=self.begin();self.assertEqual(self.client.request(cb)[0],303)
        for directory in ['contexts','sso-sessions']:
            for p in (self.private/directory).iterdir():
                raw=p.read_bytes()
                for token in [b'test-access-must-not-persist',b'test-refresh-must-not-persist',b'eyJhbGci']:
                    self.assertNotIn(token,raw)
        self.assertNotIn(b'test-access-must-not-persist',(self.private/'principals.json').read_bytes())
    def test_15_rate_limit_survives_new_requests(self):
        for _ in range(5):self.begin()
        csrf,_=self.page()
        self.assertEqual(self.client.request('/auth/start.php','POST',{'csrf':csrf})[0],503)

    def test_16_incoming_session_id_not_promoted(self):
        cb,_=self.begin()
        incoming='f'*64
        self.client.cookies['SSO_LAYERLING_SSO_TEST']=incoming
        self.assertEqual(self.client.request(cb)[0],303)
        self.assertNotEqual(self.client.cookies['SSO_LAYERLING_SSO_TEST'],incoming)
        self.assertFalse((self.private/'sso-sessions'/('sess_'+incoming)).exists())
    def test_17_logout_rejects_get_and_bad_csrf(self):
        cb,csrf=self.begin();self.assertEqual(self.client.request(cb)[0],303)
        self.assertEqual(self.client.request('/auth/logout.php')[0],503)
        self.assertEqual(self.client.request('/auth/logout.php','POST',{'csrf':'bad'})[0],503)
        self.assertIn('Anmeldung über IServ erfolgreich'.encode(),self.page()[1][2])

    def test_18_form_origin_and_sensitive_response_policies(self):
        # A native browser form POST under no-referrer sends Origin:null. The
        # form document must retain same-origin provenance without permitting
        # null/missing Origin on the server or leaking callback queries.
        _,page=self.page()
        self.assertEqual(page[1]['referrer-policy'],'same-origin')
        csrf=re.search(rb'name="csrf" value="([a-f0-9]{64})"',page[2])[1].decode()
        redirect=self.client.request('/auth/start.php','POST',{'csrf':csrf})
        self.assertEqual(redirect[0],303)
        self.assertEqual(redirect[1]['referrer-policy'],'no-referrer')
        error=self.client.request('/auth/callback.php?state=wrong&code=synthetic')
        self.assertEqual(error[0],503)
        self.assertEqual(error[1]['referrer-policy'],'no-referrer')
        rejected=self.client.request('/auth/logout.php','POST',{'csrf':'wrong'})
        self.assertEqual(rejected[0],503)
        self.assertEqual(rejected[1]['referrer-policy'],'no-referrer')

if __name__=='__main__':unittest.main(argv=['sso_http_test.py']+remaining,verbosity=2)
