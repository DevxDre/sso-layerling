#!/usr/bin/env python3
"""Synthetic OIDC -> native cookie -> real pinned PHP storage, no real accounts/credentials."""
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import hashlib
import http.client
import importlib.util
import io
import json
import re
from pathlib import Path
import shutil
import subprocess
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import zipfile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--php',required=True);parser.add_argument('--layerling',type=Path,required=True)
OPTIONS,remaining=parser.parse_known_args()
spec=importlib.util.spec_from_file_location('sso_support',ROOT/'tests/sso_http_test.py');sso=importlib.util.module_from_spec(spec);spec.loader.exec_module(sso)
MAKER='maker-fixture';ADMIN='admin-fixture'
U1='11111111-1111-1111-1111-111111111111';U2='22222222-2222-2222-2222-222222222222';UM='33333333-3333-3333-3333-333333333333';UA='44444444-4444-4444-4444-444444444444'
def project(marker):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w')as archive:archive.writestr(zipfile.ZipInfo('project.json',date_time=(2026,1,1,0,0,0)),json.dumps({'marker':marker}))
    return buffer.getvalue()

class IntegratedStorageTest(unittest.TestCase):
    stop=sso.SsoHTTPTest.__dict__['stop']
    page=sso.SsoHTTPTest.page
    begin=sso.SsoHTTPTest.begin
    callback_for_redirect=sso.SsoHTTPTest.callback_for_redirect
    exchanges=sso.SsoHTTPTest.exchanges
    @classmethod
    def setUpClass(cls):
        original=sso.package.package
        def package(output,installed_private):return original(output,installed_private,OPTIONS.layerling,str(output/'public'))
        with patch.object(sso.package,'package',package):sso.SsoHTTPTest.setUpClass.__func__(cls)
        for name in ['sessions','projects','templates']:(cls.private/name).mkdir(mode=0o700)
        (cls.private/'audit.jsonl').touch()
        config=cls.private/'app/storage.json';values=json.loads(config.read_text());values['origin']=cls.origin;config.write_text(json.dumps(values))
        bootstrap=cls.runtime/'public/_sso.php';text=bootstrap.read_text()
        text=text.replace(",'"+cls.origin+"');", ",'"+cls.origin+"',\\Sso\\Layerling\\StorageConfig::load('"+str(config)+"'));")
        bootstrap.write_text(text)
    def setUp(self):
        sso.SsoHTTPTest.setUp(self)
        (self.private/'principals.json').write_text('{}')
        (self.private/'audit.jsonl').write_text('')
        for directory in ['projects', 'templates']:
            for p in (self.private/directory).iterdir():shutil.rmtree(p) if p.is_dir()and not p.is_symlink()else p.unlink()
    def login(self,uuid=U1,roles=None,groups=None,*,display_name='',group_acts=None,preferred_username=None,**flags):
        c=sso.Client(self)
        claims={'iserv:uuid':uuid,'sub':'pairwise-'+uuid,'iserv:roles':[{'id':role}for role in (['ROLE_STUDENT']if roles is None else roles)],
                'iserv:groups':{} if groups is None else {g:{'id':g,'name':'Fixture '+g}for g in groups}}
        if display_name is not None:
            claims['name']=display_name or 'Fixture '+uuid[:8]
        if preferred_username is not None:
            claims['preferred_username'] = preferred_username
        for group, act in (group_acts or {}).items():
            claims['iserv:groups'][group]['act'] = act
        callback,logout=self.begin(c,claims=claims,**flags)
        response=c.request(callback);self.assertEqual(response[0],303,response[2])
        self.assertIn('SSO_LAYERLING_SESSION',c.cookies)
        session=self.json(self.raw(c,'GET','/session.php'))
        owners=self.json(self.raw(c,'GET','/owners.php'))['owners']
        identity=next(owner['userId']for owner in owners if owner['isSelf'])
        c.csrf=session['csrfToken'];c.owner=identity;c.logoutCsrf=logout
        return c
    def raw(self,client,method='GET',path='/store.php',body=None,headers=None,protect=True):
        actual={'Cookie':'; '.join(k+'='+v for k,v in client.cookies.items())}
        if protect and method not in ['GET','HEAD']:
            actual.update({'Origin':self.origin,'X-SSO-CSRF':getattr(client,'csrf','')})
        actual.update(headers or {})
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=6)
        try:
            connection.request(method,path,body,actual);r=connection.getresponse()
            return r.status,{k.lower():v for k,v in r.getheaders()},r.read()
        finally:connection.close()
    def json(self,result,status=200):
        self.assertEqual(result[0],status,result[2][:200]);self.assertEqual(result[1].get('cache-control'),'private, no-store')
        return json.loads(result[2])
    def upload(self,client,marker='test',owner=None,revision=None,name='same.lyl'):
        query={'fileName':name}
        if owner:query['_sso_owner']=owner
        headers={'Content-Type':'application/vnd.layerling.project+zip'}
        if revision:headers['If-Match']='"'+revision+'"'
        return self.raw(client,'POST','/store.php?'+urlencode(query),project(marker),headers)

    def publish_template(self, client, groups, content=None, **options):
        boundary = 'sso-template-test'
        body = []
        for name, value in [('title', 'CAD <Übung>'), ('instructions', 'Bau einen Quader.'), *[('groups[]', group) for group in groups]]:
            body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="project"; filename="test.lyl"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        body.extend([project('template') if content is None else content, f'\r\n--{boundary}--\r\n'.encode()])
        return self.raw(client, 'POST', '/vorlagen.php?action=publish', b''.join(body),
                        {'Content-Type': f'multipart/form-data; boundary={boundary}'}, **options)

    def test_template_permissions_follow_latest_iserv_login(self):
        path = '/vorlagen.php'
        self.json(self.raw(sso.Client(self), path=path), 401)
        teacher = self.login(UA, ['ROLE_TEACHER', 'ROLE_TEACH_AKTIV'], ['class-a', 'class-b'])
        student = self.login(U1, groups=['class-b'])
        outsider = self.login(U2, groups=['class-c'])
        admin = self.login(UM, ['ROLE_ADMIN'], [ADMIN, 'class-a'])
        teacher_page = self.raw(teacher, path=path)
        self.assertEqual(teacher_page[0], 200)
        self.assertIn(b'Fixture class-a', teacher_page[2])
        self.assertIn(b'Fixture class-b', teacher_page[2])
        self.json(self.raw(admin, path=path), 403)
        self.json(self.publish_template(student, ['class-b']), 403)
        self.json(self.publish_template(teacher, ['class-c']), 403)
        self.json(self.publish_template(teacher, ['class-a'], protect=False), 403)
        self.json(self.publish_template(teacher, []), 400)
        self.json(self.publish_template(teacher, ['class-a'], b'invalid archive'), 400)
        self.assertEqual(self.publish_template(teacher, ['class-a', 'class-b'])[0], 201)
        page = self.raw(student, path=path)
        self.assertEqual(page[0], 200)
        self.assertIn('CAD &lt;Übung&gt;'.encode(), page[2])
        self.assertNotIn(b'publish-template', page[2])
        self.assertNotIn(b'class-b', page[2])
        template_id = re.search(rb'data-copy-template="([a-f0-9]{32})"', page[2])[1].decode()
        download = path + '?id=' + template_id
        downloaded = self.raw(student, path=download)
        self.assertEqual(downloaded[0], 200)
        self.assertEqual(downloaded[2], project('template'))
        self.json(self.raw(student, 'POST', '/store.php?fileName=task.lyl', downloaded[2],
                           {'If-None-Match': '*', 'Content-Type': 'application/vnd.layerling.project+zip'}), 201)
        self.assertNotIn(b'data-copy-template', self.raw(outsider, path=path)[2])
        self.json(self.raw(outsider, path=download), 404)
        self.json(self.raw(student, path=path+'?id=../principals.json'), 404)
        other_teacher = self.login(UM, ['ROLE_TEACHER'], ['class-b'])
        withdraw = path+'?action=withdraw'
        body = urlencode({'id': template_id})
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        self.json(self.raw(other_teacher, 'POST', withdraw, body, headers), 404)
        self.login(U1, groups=['class-c'])
        self.json(self.raw(student, path=download), 404)
        self.login(UA, ['ROLE_TEACHER'], ['class-b'])
        self.json(self.publish_template(teacher, ['class-a']), 403)
        self.assertEqual(self.raw(teacher, 'POST', withdraw, body, headers)[0], 204)
        self.json(self.raw(self.login(U2, groups=['class-b']), path=download), 404)
        self.assertEqual(self.raw(student, path='/store.php?fileName=task.lyl')[2], project('template'))
    def test_01_anonymous_api_and_old_portal_cookie_denied(self):
        c=sso.Client(self)
        for path in ['/store.php','/owners.php','/session.php']:self.json(self.raw(c,path=path),401)
        self.assertEqual(c.request('/files.php')[0],303)
        self.assertEqual(c.request('/.env')[0],404)
        fake='f'*64
        fixture=r"""ini_set('session.use_strict_mode','0');session_save_path($argv[1]);session_name('SSO_LAYERLING_SSO_TEST');session_id($argv[2]);session_start();$_SESSION=['authorized'=>true,'userId'=>str_repeat('a',32),'csrf'=>str_repeat('b',64),'issuedAt'=>time(),'lastSeen'=>time()];session_write_close();"""
        subprocess.run([OPTIONS.php,'-r',fixture,str(self.private/'sso-sessions'),fake],check=True,capture_output=True)
        c.cookies['SSO_LAYERLING_SSO_TEST']=fake;self.json(self.raw(c),401)
    def test_02_two_real_oidc_flows_isolate_same_filename_and_owner_discovery(self):
        a=self.login(U1);b=self.login(U2)
        self.json(self.upload(a,'A'),201);self.json(self.upload(b,'B'),201)
        self.assertEqual(self.raw(a,path='/store.php?fileName=same.lyl')[2],project('A'))
        self.assertEqual(self.raw(b,path='/store.php?fileName=same.lyl')[2],project('B'))
        owners=self.json(self.raw(a,path='/owners.php'))['owners'];self.assertEqual([o['userId']for o in owners],[a.owner])
        self.json(self.raw(a,path='/store.php?'+urlencode({'_sso_owner':b.owner,'fileName':'same.lyl'})),403)
        self.assertTrue(json.loads((self.private/'principals.json').read_text())[a.owner]['student'])
        self.assertEqual(json.loads((self.private/'principals.json').read_text())[a.owner]['groups'],[])
    def test_03_csrf_origin_and_url_identity_do_not_bypass(self):
        a=self.login()
        for h in [{},{'Origin':self.origin},{'X-SSO-CSRF':a.csrf},{'Origin':'null','X-SSO-CSRF':a.csrf},{'Origin':'https://evil.invalid','X-SSO-CSRF':a.csrf}]:
            self.json(self.raw(a,'POST','/store.php?fileName=bad.lyl',project('blocked'),h,False),403)
        c=sso.Client(self);self.json(self.raw(c,path='/store.php?'+urlencode({'SSO_LAYERLING_SESSION':a.cookies['SSO_LAYERLING_SESSION']})),401)
        self.assertFalse((self.private/'projects'/a.owner/'bad.lyl').exists())
    def test_04_maker_sees_and_edits_students_but_not_teacher_or_deletion(self):
        a=self.login(U1);b=self.login(U2);teacher=self.login(UA,['ROLE_TEACHER'])
        record=self.json(self.upload(a,'student'),201)['project']
        maker=self.login(UM,['ROLE_TEACHER'],[MAKER])
        owners=self.json(self.raw(maker,path='/owners.php'))['owners'];ids={o['userId']for o in owners}
        self.assertEqual(ids,{a.owner,b.owner,maker.owner});self.assertNotIn(teacher.owner,ids)
        self.assertFalse(next(o['canDelete']for o in owners if o['userId']==a.owner))
        self.json(self.upload(maker,'edited',a.owner,record['revision']))
        self.assertEqual(self.raw(a,path='/store.php?fileName=same.lyl')[2],project('edited'))
        self.json(self.raw(maker,'DELETE','/store.php?'+urlencode({'_sso_owner':a.owner,'fileName':'same.lyl'})),403)
        self.json(self.raw(maker,path='/store.php?'+urlencode({'_sso_owner':teacher.owner})),403)
        self.json(self.raw(maker,path='/store.php?'+urlencode({'_sso_owner':a.owner,'settings':'default'})),403)
    def test_05_admin_precedence_all_owners_and_delete(self):
        a=self.login(U1);teacher=self.login(U2,['ROLE_TEACHER']);self.json(self.upload(teacher,'teacher'),201)
        admin=self.login(UA,['ROLE_TEACHER','ROLE_ADMIN','ROLE_TEACH_AKTIV'],[MAKER,ADMIN])
        owners=self.json(self.raw(admin,path='/owners.php'))['owners']
        self.assertEqual({o['userId']for o in owners},{a.owner,teacher.owner,admin.owner});self.assertTrue(all(o['canDelete']for o in owners))
        record=self.json(self.raw(admin,path='/store.php?'+urlencode({'_sso_owner':teacher.owner})))['projects'][0]
        self.json(self.raw(admin,'DELETE','/store.php?'+urlencode({'_sso_owner':teacher.owner,'fileName':'same.lyl'}),headers={'If-Match':'"'+record['revision']+'"'}))
        self.assertFalse((self.private/'projects'/teacher.owner/'same.lyl').exists())
    def test_06_new_owner_login_changes_student_status_without_changing_files(self):
        a=self.login(U1);self.json(self.upload(a,'keep'),201);maker=self.login(UM,['ROLE_TEACHER'],[MAKER])
        query='/store.php?'+urlencode({'_sso_owner':a.owner,'fileName':'same.lyl'});self.assertEqual(self.raw(maker,path=query)[0],200)
        changed=self.login(U1,['ROLE_TEACHER']);self.assertEqual(changed.owner,a.owner)
        self.json(self.raw(maker,path=query),403)
        self.assertNotIn(a.owner,{o['userId']for o in self.json(self.raw(maker,path='/owners.php'))['owners']})
        self.assertEqual(self.raw(a,path='/store.php?fileName=same.lyl')[2],project('keep'))
    def test_07_group_revocation_applies_to_existing_native_session(self):
        a=self.login(U1);maker=self.login(UM,['ROLE_TEACHER'],[MAKER])
        self.json(self.raw(maker,path='/store.php?'+urlencode({'_sso_owner':a.owner})))
        changed=self.login(UM,['ROLE_ADMIN'],[]);self.assertEqual(changed.owner,maker.owner)
        self.json(self.raw(maker,path='/store.php?'+urlencode({'_sso_owner':a.owner})),403)
        self.assertEqual(len(self.json(self.raw(maker,path='/owners.php'))['owners']),1)
    def test_08_web_logout_revokes_storage_and_old_cookie(self):
        a=self.login();self.json(self.upload(a),201);sid=a.cookies['SSO_LAYERLING_SESSION']
        self.assertEqual(a.request('/auth/logout.php','POST',{'csrf':a.logoutCsrf})[0],303)
        a.cookies['SSO_LAYERLING_SESSION']=sid
        for path in ['/store.php','/session.php','/owners.php']:self.json(self.raw(a,path=path),401)
        self.assertEqual((self.private/'sessions'/('sess_'+sid)).read_bytes(),b'')
        self.assertTrue((self.private/'projects'/a.owner/'same.lyl').is_file())
    def test_09_cancel_during_callback_never_issues_storage_session(self):
        c=sso.Client(self);cb,csrf=self.begin(c,delayMicros=600000)
        peer=sso.Client(self);peer.cookies=dict(c.cookies)
        with ThreadPoolExecutor(2)as pool:
            pending=pool.submit(c.request,cb)
            for _ in range(150):
                if(self.root/'network-active').exists():break
                time.sleep(.01)
            self.assertTrue((self.root/'network-active').exists());self.assertEqual(peer.request('/auth/logout.php','POST',{'csrf':csrf})[0],303)
            self.assertEqual(pending.result()[0],503)
        self.assertNotIn('SSO_LAYERLING_SESSION',c.cookies);self.json(self.raw(c),401)
    def test_10_waiting_upload_observes_native_revocation(self):
        a=self.login();ready=self.root/'locked';release=self.root/'release';ready.unlink(missing_ok=True);release.unlink(missing_ok=True)
        fixture=r"""require $argv[1];session_save_path($argv[2]);session_name('SSO_LAYERLING_SESSION');session_id($argv[3]);session_start();file_put_contents($argv[4],'ready');$until=microtime(true)+5;while(!file_exists($argv[5])&&microtime(true)<$until){usleep(10000);clearstatcache();}\Sso\Layerling\SessionRevocation::revoke();"""
        proc=subprocess.Popen([OPTIONS.php,'-r',fixture,str(ROOT/'vendor/autoload.php'),str(self.private/'sessions'),a.cookies['SSO_LAYERLING_SESSION'],str(ready),str(release)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if ready.exists():break
                time.sleep(.01)
            self.assertTrue(ready.exists())
            with ThreadPoolExecutor(1)as pool:
                pending=pool.submit(self.upload,a,'blocked')
                try:
                    with self.assertRaises(FutureTimeout):pending.result(timeout=.15)
                finally:release.write_text('release')
                self.json(pending.result(),401)
            self.assertFalse((self.private/'projects'/a.owner/'same.lyl').exists())
        finally:
            release.write_text('release')
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    def test_11_layout_config_and_upstream_integrity_fail_closed(self):
        a=self.login();cfg=self.private/'app/storage.json';original=cfg.read_text()
        try:
            for change in [{'enabled':False},{'publicRoot':'/invalid'},{'groupIds':{'makerspace':None,'admins':ADMIN}}]:
                values=json.loads(original);values.update(change);cfg.write_text(json.dumps(values));self.json(self.raw(a),503)
        finally:cfg.write_text(original)
        source=self.private/'app/upstream/store.php';saved=source.read_bytes()
        try:source.write_bytes(saved+b'\n//tamper');self.json(self.raw(a),503)
        finally:source.write_bytes(saved)
    def test_12_files_page_and_no_api_logout_shortcut(self):
        a=self.login();r=a.request('/files.php');self.assertEqual(r[0],200)
        self.assertEqual(r[1]['referrer-policy'],'same-origin');self.assertIn("script-src 'self'",r[1]['content-security-policy'])
        self.assertIn(b'/files.js',r[2]);self.assertNotIn(b'identityHash',r[2])
        self.json(self.raw(a,'POST','/session.php'),405)
        self.assertEqual(a.request('/auth/logout.php','POST',{'csrf':a.logoutCsrf})[0],303)
        self.assertEqual(a.request('/files.php')[0],303)
    def test_13_scope_marker_and_absolute_expiry_required(self):
        now = int(time.time())
        for changes, status in [
            ({'scope': 'old-prototype'}, 401),
            ({'issuedAt': now - 140*60 - 1}, 401),
            ({'issuedAt': now - 130*60}, 200),
            ({'issuedAt': now - 90*60, 'lastSeen': now - 70*60 - 1}, 401),
        ]:
            a=self.login();sid=a.cookies['SSO_LAYERLING_SESSION']
            fixture=r"""session_save_path($argv[1]);session_name('SSO_LAYERLING_SESSION');session_id($argv[2]);session_start();$_SESSION=array_replace($_SESSION,json_decode($argv[3],true));session_write_close();"""
            subprocess.run([OPTIONS.php,'-r',fixture,str(self.private/'sessions'),sid,json.dumps(changes)],check=True,capture_output=True)
            self.json(self.raw(a),status)
    def test_14_header_spoof_and_path_escape_rejected(self):
        a=self.login(U1,['ROLE_ADMIN']);b=self.login(U2);self.json(self.upload(b,'private'),201)
        self.json(self.raw(a,path='/store.php?'+urlencode({'_sso_owner':b.owner}),headers={'X-Forwarded-Groups':ADMIN,'Remote-User':b.owner}),403)
        self.json(self.raw(a,path='/store.php?'+urlencode({'_sso_owner':'../'+b.owner})),400)
        self.json(self.raw(a,path='/store.php?path=../'),400)
        self.json(self.raw(a,path='/store.php',headers={'Host':'evil.invalid'}),503)

if __name__=='__main__':unittest.main(argv=[__file__,*remaining],verbosity=2)
