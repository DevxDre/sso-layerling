#!/usr/bin/env python3
"""CAD owner entry/probe against synthetic OIDC and native private sessions."""
import importlib.util
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import subprocess
import time
import unittest
import hashlib
import zipfile
import argparse

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--php',required=True);parser.add_argument('--layerling',type=Path,required=True);parser.add_argument('--candidate',type=Path)
parser.add_argument('--mcp-demo', action='store_true', help='Open a local Chromium demo with a synthetic IServ account')
parser.add_argument('--alternate-profile', action='store_true')
OPTIONS, remaining=parser.parse_known_args()
spec=importlib.util.spec_from_file_location('integrated_support',ROOT/'tests/integrated_storage_http_test.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

class CadHTTPTest(base.IntegratedStorageTest):
    login_page = '/index.php'
    router = ROOT/'scripts/mcp-test-router.php'
    mcp_path = '/api/layerling-mcp'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cad=cls.private/'app/cad';cls.cad.mkdir()
        if OPTIONS.candidate:
            shutil.copytree(OPTIONS.candidate/'private/app/cad',cls.cad,dirs_exist_ok=True)
            for p in (OPTIONS.candidate/'public').iterdir():
                if p.name in ['index.php','_sso.php','auth','store.php','session.php','owners.php','files.php','files','konto','files.js','files.css','vorlagen.php','vorlagen.js','rechte.php','.sso-layerling-sso-test','cad-session.php']:continue
                if p.is_dir():shutil.copytree(p,cls.runtime/'public'/p.name,dirs_exist_ok=True)
                else:shutil.copyfile(p,cls.runtime/'public'/p.name)
        else:
            html=b'<!doctype html><html><head><script>window.fixture=true</script></head><body>CAD fixture</body></html>'
            (cls.cad/'index.html').write_bytes(html)
            (cls.cad/'manifest.json').write_text(json.dumps({'kind':'sso-layerling-cad-owner-v2','indexSha256':hashlib.sha256(html).hexdigest()}))
        shutil.copyfile(ROOT/'public/cad.php',cls.runtime/'public/cad.php')
        for directory in ['konto', 'files']:
            shutil.copytree(ROOT/'public'/directory, cls.runtime/'public'/directory)
        (cls.runtime/'public/cad-session.php').write_text("<?php (require '"+str(cls.private)+"/app/src/storage-bootstrap.php')->cadSession();")
    def change_last_seen(self,client,value):
        code="session_name('SSO_LAYERLING_SESSION');session_save_path($argv[1]);session_id($argv[2]);session_start();$_SESSION['lastSeen']=(int)$argv[3];session_write_close();"
        subprocess.run([OPTIONS.php,'-r',code,str(self.private/'sessions'),client.cookies['SSO_LAYERLING_SESSION'],str(value)],check=True,capture_output=True)

    def enable_mcp(self):
        path = self.private/'app/mcp-test.json'
        path.write_text(json.dumps({'enabled': True}))
        self.addCleanup(path.unlink, missing_ok=True)

    def mcp_post(self, client, payload, **options):
        headers = {'Content-Type': 'application/json', **options.pop('headers', {})}
        return self.raw(client, 'POST', self.mcp_path, json.dumps(payload), headers, **options)

    def test_mcp_policy_and_session_isolation(self):
        anonymous = base.sso.Client(self)
        status_path = self.mcp_path + '?status=1'
        self.json(self.raw(anonymous, path=status_path), 404)
        by_personal_group = self.login(groups=['mcp-personal'])
        by_role = self.login(base.U2, ['ROLE_TEACHER'], [base.MAKER])
        by_group = self.login(base.UM, groups=['mcp-pilot'])
        denied = self.login(base.UA, ['ROLE_TEACHER'], ['mcp-pilot', 'mcp-blocked'])
        outsider = self.login('55555555-5555-5555-5555-555555555555')
        self.enable_mcp()
        self.assertEqual(self.json(self.raw(by_role, path=status_path)), {'remote': False})
        personal_grant = ('group:mcp-personal', '', 'mcp', 'allow')
        role_grant = ('role:' + self.provider_role('ROLE_TEACHER'), '', 'mcp', 'allow')
        group_grant = ('group:mcp-pilot', '', 'mcp', 'allow')
        blocked = ('group:mcp-blocked', '', 'mcp', 'deny')
        grants = (personal_grant, role_grant, group_grant, blocked)
        self.seed_permissions(*self.ownership_rules(base.MAKER), *grants)
        for client in [by_personal_group, by_role, by_group]:
            self.assertEqual(self.json(self.raw(client, path=status_path)), {'remote': True})
        self.assertIn(b'"mcpTest":false', self.raw(by_role, path='/cad.php?owner=' + by_personal_group.owner)[2])
        for client in [anonymous, denied, outsider]:
            self.assertEqual(self.json(self.raw(client, path=status_path)), {'remote': False})
            self.json(self.mcp_post(client, {'type': 'pair'}), 403)
        self.seed_permissions(*grants, ('group:' + self.provider_group(base.MAKER), '', 'mcp', 'deny'))
        self.assertEqual(self.json(self.raw(by_role, path=status_path)), {'remote': False})
        self.seed_permissions(personal_grant, role_grant, ('group:mcp-pilot', '', 'mcp', 'deny'))
        self.assertEqual(self.json(self.raw(by_group, path=status_path)), {'remote': False})
        self.seed_permissions(*grants)
        self.json(self.mcp_post(by_personal_group, {'type': 'pair'}, protect=False), 403)
        self.json(self.mcp_post(by_personal_group, {'type': 'pair'}, headers={'Origin': 'https://foreign.invalid'}), 403)
        self.json(self.raw(anonymous, path=self.mcp_path), 401)

        second_session = self.login(groups=['mcp-personal'])
        for client, editor_id in [(by_personal_group, 'editor-one'), (by_role, 'editor-two'), (second_session, 'editor-three')]:
            self.json(self.mcp_post(client, {'type': 'heartbeat', 'editor': {'editorId': editor_id, 'editorNumber': 12345}}))
        token = self.json(self.mcp_post(by_personal_group, {'type': 'pair'}))['token']
        auth = {'Authorization': 'Bearer ' + token}
        result = self.raw(anonymous, path=self.mcp_path, headers=auth)
        self.assertNotIn('set-cookie', result[1])
        self.assertEqual([editor['editorId'] for editor in self.json(result)['editors']], ['editor-one'])
        for editor in ['editor-two', 'editor-three']:
            self.json(self.mcp_post(anonymous, {'type': 'command', 'action': 'get_scene', 'editorId': editor}, headers=auth), 404)
        self.json(self.mcp_post(by_role, {'type': 'poll', 'editorId': 'editor-one'}))

        rotated = self.json(self.mcp_post(by_personal_group, {'type': 'pair'}))['token']
        self.json(self.raw(anonymous, path=self.mcp_path, headers=auth), 403)
        auth = {'Authorization': 'Bearer ' + rotated}
        self.assertEqual(self.raw(anonymous, path=self.mcp_path, headers=auth)[0], 200)
        self.seed_permissions(role_grant)
        self.json(self.raw(anonymous, path=self.mcp_path, headers=auth), 403)
        self.json(self.mcp_post(by_personal_group, {'type': 'poll', 'editorId': 'editor-one'}), 403)
        teacher_token = self.json(self.mcp_post(by_role, {'type': 'pair'}))['token']
        teacher_auth = {'Authorization': 'Bearer ' + teacher_token}
        self.login(base.U2, ['ROLE_STUDENT'])
        self.json(self.raw(anonymous, path=self.mcp_path, headers=teacher_auth), 403)

    @unittest.skipUnless(OPTIONS.candidate, 'Pass the verified real candidate to exercise Chromium')
    def test_mcp_browser_and_stdio(self):
        account = self.login(groups=['mcp-personal'])
        self.enable_mcp()
        self.seed_permissions(('group:mcp-personal', '', 'mcp', 'allow'))
        with TemporaryDirectory(prefix='sso-cad-mcp-browser-') as temp:
            client = subprocess.check_output(
                ['python3', str(ROOT/'scripts/prepare-mcp-client.py'),
                 '--layerling', str(OPTIONS.layerling.resolve()), '--output', str(Path(temp)/'client')],
                text=True).strip()
            payload = {'origin': self.origin, 'cookies': account.cookies, 'mcp': client}
            result = subprocess.run(['node', str(ROOT/'tests/cad_browser_test.mjs')], input=json.dumps(payload), text=True,
                                    capture_output=True, timeout=105)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertIn('CAD_MCP_BROWSER_OK', result.stdout)
    def test_15_cad_entry_requires_native_login_and_actor(self):
        self.assertEqual(self.raw(base.sso.Client(self),path='/cad.php')[0],303)
        a=self.login();response=self.raw(a,path='/cad.php')
        self.assertEqual(response[0],200)
        self.assertEqual(response[1]['cache-control'],'private, no-store')
        self.assertIn("'wasm-unsafe-eval'",response[1]['content-security-policy'])
        self.assertNotIn("'unsafe-eval'",response[1]['content-security-policy'])
        self.assertNotIn("script-src 'self' 'unsafe-inline'",response[1]['content-security-policy'])
        self.assertLess(response[2].index(b'/cad-bridge.js'),response[2].index(b'</head>'))
        self.assertIn(b'"userId":"'+a.owner.encode()+b'"',response[2])
        self.assertEqual(self.raw(a,'POST','/cad.php')[0],503)
        registry=json.loads((self.private/'principals.json').read_text());registry[a.owner]['enabled']=False
        (self.private/'principals.json').write_text(json.dumps(registry))
        self.assertEqual(self.raw(a,path='/cad.php')[0],403)

    def test_cad_first_navigation_and_manual_pages(self):
        a = base.sso.Client(self)
        self.assertEqual(self.raw(a, path='/', headers={'Sec-Purpose': 'prefetch'})[0], 204)
        anonymous = a.request('/index.php')
        self.assertEqual(anonymous[0], 200)
        self.assertIn(b'/auth/start.php', anonymous[2])
        for path in ['/konto', '/files']:
            self.assertIn(a.request(path)[0], [301, 303])
            self.assertEqual(a.request(path + '/')[1]['location'], '/')
        redirect = a.request('/')
        self.assertEqual(redirect[0], 303)
        authorize = ('https://identity.example.invalid/workshop/oauth/authorize?' if self.alternate
                     else 'https://login.example.invalid/iserv/auth/auth?')
        self.assertTrue(redirect[1]['location'].startswith(authorize))
        callback = self.callback_for_redirect(a, redirect)
        self.assertEqual(a.request(callback)[1]['location'], '/cad.php')
        for path in ['/', '/index.php']:
            self.assertEqual(a.request(path)[1]['location'], '/cad.php')
        account = a.request('/konto/')
        self.assertEqual(account[0], 200)
        self.assertIn(b'Gepr', account[2])
        files = a.request('/files/')
        self.assertEqual(files[0], 200)
        for page in [account, files]:
            self.assertIn(b'href="/cad.php"', page[2])
            self.assertNotRegex(page[2], rb'<a\b[^>]*\bhref="/(?:konto|files)(?:[./"]|$)')
        editor = a.request('/cad.php')
        context = json.loads(re.search(rb'id="sso-cad-context" type="application/json">(.*?)</script>', editor[2])[1])
        rejected = a.request('/auth/logout.php', 'POST', {'csrf': context['logoutCsrf'], 'cadCsrf': '0' * 64})
        self.assertEqual(rejected[0], 503)
        self.assertEqual(a.request('/cad.php')[0], 200)
        logout = a.request('/auth/logout.php', 'POST', {'csrf': context['logoutCsrf'], 'cadCsrf': context['csrfToken']})
        self.assertEqual(logout[1]['location'], '/index.php')
        self.assertIn(b'/auth/start.php', a.request('/index.php')[2])
        self.assertEqual(a.request('/cad.php')[1]['location'], '/')

    def test_account_profile_and_authorized_class_catalogue(self):
        prefix = self.class_prefix
        second_prefix = 'course-' if self.alternate else prefix
        groups = {'class-a': prefix+'5a', 'class-b': second_prefix+'6b', 'duplicate': prefix+'5a',
                  'empty': prefix, 'case': prefix.upper()+'8c', 'other': 'unmapped.9d', 'malformed': [prefix+'7a']}
        student = self.login(groups=list(groups), group_acts=groups,
                             preferred_username='schueler<&', display_name='Test <Schüler>')
        other = self.login(base.U2, display_name=None)
        maker = self.login(base.UM, ['ROLE_TEACHER'], [base.MAKER])
        account = student.request('/konto/')
        self.assertEqual(account[0], 200)
        for label, value in [('Account', 'schueler&lt;&amp;'), ('Name', 'Test &lt;Schüler&gt;'), ('Klasse', '5a, 6b')]:
            self.assertRegex(account[2].decode(), rf'<dt>{label}</dt>\s*<dd class="sso-wrap">{re.escape(value)}</dd>')
        self.assertRegex(other.request('/konto/')[2].decode(), r'<dt>Klasse</dt>\s*<dd class="sso-wrap">–</dd>')
        self.seed_permissions(*self.ownership_rules(base.MAKER))
        owners = self.json(self.raw(maker, path='/owners.php?cad=1'))['owners']
        entry = next(item for item in owners if item['userId'] == student.owner)
        self.assertEqual(entry['classes'], ['5a', '6b'])
        self.assertIs(entry['hasStudentRole'], True)
        self.assertIs(next(item for item in owners if item['isSelf'])['hasStudentRole'], False)
        self.assertNotIn('schueler', json.dumps(owners))
        self.assertEqual(len(self.json(self.raw(other, path='/owners.php?cad=1'))['owners']), 1)
        # Existing records and a later login without a class both render without errors.
        self.login(groups=[])
        self.assertRegex(student.request('/konto/')[2].decode(), r'<dt>Klasse</dt>\s*<dd class="sso-wrap">–</dd>')

    def test_recent_activity_counts_successful_project_saves_for_the_actor(self):
        student = self.login()
        inactive = self.login(base.U2)
        maker = self.login(base.UM, ['ROLE_TEACHER'], [base.MAKER])
        admin = self.login(base.UA, ['ROLE_TEACHER'], [base.ADMIN])
        self.seed_permissions(*self.ownership_rules(base.MAKER, base.ADMIN))

        def recent(owner):
            entries = self.json(self.raw(admin, path='/owners.php?cad=1'))['owners']
            return next(item['recentProjectSave'] for item in entries if item['userId'] == owner)

        self.assertFalse(recent(student.owner))
        saved = self.json(self.upload(student), 201)
        self.assertTrue(recent(student.owner))
        self.json(self.raw(inactive, 'POST', '/store.php?folder=Werkstatt'), 201)
        self.assertEqual(self.raw(inactive, 'POST', '/store.php?fileName=bad.lyl', b'invalid')[0], 400)
        self.assertFalse(recent(inactive.owner))
        past = time.time() - 3601
        os.utime(self.private/'project-activity'/student.owner, (past, past))
        self.assertFalse(recent(student.owner))
        self.json(self.upload(maker, 'edit', owner=student.owner, revision=saved['project']['revision']))
        self.assertTrue(recent(maker.owner))
        self.assertFalse(recent(student.owner))
    def test_16_cad_probe_has_no_idle_keepalive(self):
        a=self.login();last=int(time.time())-65*60
        # An old lastSeen must still be no earlier than issuedAt.
        code="session_name('SSO_LAYERLING_SESSION');session_save_path($argv[1]);session_id($argv[2]);session_start();$_SESSION['issuedAt']=(int)$argv[3]-10;$_SESSION['lastSeen']=(int)$argv[3];session_write_close();"
        subprocess.run([OPTIONS.php,'-r',code,str(self.private/'sessions'),a.cookies['SSO_LAYERLING_SESSION'],str(last)],check=True,capture_output=True)
        first=self.json(self.raw(a,path='/cad-session.php'));second=self.json(self.raw(a,path='/cad-session.php'))
        self.assertEqual(first['userId'],a.owner);self.assertEqual(first['csrfToken'],a.csrf)
        self.assertEqual(first['expiresAt'],last+70*60);self.assertEqual(first['expiresAt'],second['expiresAt'])
        self.json(self.raw(a,'POST','/cad-session.php'),405)
        self.json(self.raw(a,path='/cad-session.php',headers={'Origin':'https://foreign.invalid'}),403)
    def test_17_private_editor_integrity_and_missing_bundle_fail_closed(self):
        a=self.login();index=self.cad/'index.html';original=index.read_bytes()
        try:
            index.write_bytes(original+b'changed')
            self.assertEqual(self.raw(a,path='/cad.php')[0],503)
        finally:index.write_bytes(original)
        bundle=self.cad.with_name('cad-hidden');self.cad.rename(bundle)
        try:self.assertEqual(self.raw(a,path='/cad.php')[0],404)
        finally:bundle.rename(self.cad)
    def test_18_cad_owner_catalog_and_permissions(self):
        student = self.login()
        teacher = self.login(base.U2, ['ROLE_TEACHER'])
        maker = self.login(base.UM, ['ROLE_TEACHER'], [base.MAKER])
        admin = self.login(base.UA, ['ROLE_TEACHER'], [base.ADMIN])
        self.seed_permissions(*self.ownership_rules(base.MAKER, base.ADMIN))
        route = '/cad.php?owner=' + student.owner
        status, headers, html = self.raw(maker, path=route)
        self.assertEqual(status, 200)
        csp = headers['content-security-policy']
        self.assertIn("default-src 'none'", csp)
        self.assertIn("script-src 'self' 'nonce-", csp)
        # Layerling reads canvas thumbnails with fetch(data:) before uploading them.
        self.assertIn("connect-src 'self' data: blob:", csp)
        self.assertIn("frame-src 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("manifest-src 'none'", csp)
        self.assertIn('upgrade-insecure-requests', csp)
        # no-referrer makes editor writes, MCP and the footer logout arrive with Origin:null.
        self.assertEqual(headers['referrer-policy'], 'same-origin')
        self.assertEqual(headers['permissions-policy'], 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=(), hid=(), bluetooth=()')
        self.assertEqual(headers['x-frame-options'], 'DENY')
        context = json.loads(re.search(rb'id="sso-cad-context" type="application/json">(.*?)</script>', html)[1])
        self.assertEqual(context['selected']['userId'], student.owner)
        self.assertFalse(context['selected']['canDelete'])
        self.assertEqual({entry['userId'] for entry in context['owners']}, {maker.owner, student.owner})
        self.assertEqual(self.raw(student, path='/cad.php?owner='+teacher.owner)[0], 403)
        self.assertEqual(self.raw(maker, path='/cad.php?owner='+teacher.owner)[0], 403)
        self.assertEqual(self.raw(admin, path='/cad.php?owner='+teacher.owner)[0], 200)
        self.assertEqual(self.raw(admin, path='/cad.php?owner[]=x')[0], 400)
        self.assertEqual(self.raw(admin, path='/cad.php?owner='+'0'*32)[0], 403)
        probe = '/cad-session.php?owner=' + student.owner
        self.assertFalse(self.json(self.raw(maker, path=probe))['canDelete'])
        self.assertTrue(self.json(self.raw(admin, path=probe))['canDelete'])
        self.assertEqual(self.raw(admin, path=probe, headers={'X-SSO-CSRF':maker.csrf})[0], 403)
        self.assertEqual(self.raw(admin, path='/store.php?_sso_owner='+student.owner, headers={'X-SSO-CSRF':maker.csrf})[0], 403)
        self.json(self.raw(maker, path='/store.php?settings=default&_sso_owner='+student.owner), 403)
        self.json(self.raw(maker, path='/store.php?search=private&_sso_owner='+teacher.owner), 403)
        self.login(base.U1, ['ROLE_TEACHER'])
        self.json(self.raw(maker, path=probe), 403)
        self.json(self.raw(maker, path='/store.php?search=private&_sso_owner='+student.owner), 403)
        self.assertTrue(self.json(self.raw(admin, path=probe))['canDelete'])

    @unittest.skipUnless(OPTIONS.candidate,'Pass the verified real candidate to exercise Chromium')
    def test_19_browser_real_editor(self):
        classes = {'cad-class': self.class_prefix+'5a', 'second-class': self.class_prefix+'7c'}
        a=self.login(groups=list(classes), group_acts=classes, display_name='Änne Muster')
        b=self.login(base.U2, groups=list(classes), group_acts=classes, display_name='Änne Muster')
        unnamed=self.login('55555555-5555-5555-5555-555555555555', groups=['other-class'],
                           group_acts={'other-class': self.class_prefix+'6b'}, display_name=None)
        teacher=self.login('66666666-6666-6666-6666-666666666666', ['ROLE_TEACHER'], ['cad-class'], display_name='Änne Lehrkraft')
        maker = self.login(base.UM, ['ROLE_TEACHER'], [base.MAKER, 'cad-class'],
                           group_acts={'cad-class': classes['cad-class']}, display_name='Klara Betreuung')
        account_name = 'KonstruktionswerkstattSchuljahresabschlussprojekt' * 3
        account_id = 'arbeitsgruppenbenutzerkennung' * 5
        admin = self.login(base.UA, ['ROLE_TEACHER', self.rights_admin_role], [base.ADMIN],
                           display_name=account_name, preferred_username=account_id)
        self.seed_permissions(*self.ownership_rules(base.MAKER, base.ADMIN), self.publisher_rule())
        (self.private/'projects'/a.owner/Path(*['depth']*13)).mkdir(parents=True)
        [occt_index] = (OPTIONS.candidate/'public/occt').glob('*/index.js')
        payload = {'origin':self.origin, 'cookies':a.cookies, 'otherCookies':b.cookies,
            'occtIndex': '/' + occt_index.relative_to(OPTIONS.candidate/'public').as_posix(),
            'owner':a.owner, 'otherOwner':b.owner, 'unnamedOwner':unnamed.owner, 'teacherOwner':teacher.owner,
            'makerCookies':maker.cookies, 'teacherCookies':teacher.cookies,
            'makerOwner':maker.owner, 'adminCookies':admin.cookies, 'accountName':account_name, 'accountId':account_id}
        result=subprocess.run(['node',str(ROOT/'tests/cad_browser_test.mjs')],input=json.dumps(payload),text=True,capture_output=True,timeout=210)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-3000:])
        self.assertIn('CAD_BROWSER_OK',result.stdout)
        files=list((self.private/'projects'/a.owner/'Werkstatt').glob('*.lyl'));self.assertEqual(len(files),1)
        other_file=self.private/'projects'/b.owner/files[0].name
        first_copy=self.private/'projects'/a.owner/'CAD Aufgabe.lyl'
        second_copy=self.private/'projects'/b.owner/'CAD Aufgabe.lyl'
        for file, expected_shapes in [(files[0], 2), (other_file, 1), (first_copy, 2), (second_copy, 3)]:
            with zipfile.ZipFile(file) as archive:document=json.loads(archive.read('project.json'))
            scene = next(state for state in document['states'] if state['id'] == document['sceneStateId'])
            self.assertEqual(len(scene['rootNodeIds']), expected_shapes, 'only the selected student file gets the supervised edit')
        self.assertFalse(list((self.private/'projects'/maker.owner).glob('*.lyl')))
        [published] = (self.private/'templates').glob('*/project.lyl')
        with zipfile.ZipFile(published) as archive:document=json.loads(archive.read('project.json'))
        scene = next(state for state in document['states'] if state['id'] == document['sceneStateId'])
        self.assertEqual(len(scene['rootNodeIds']), 1, 'publication remains an immutable snapshot')

def mcp_demo():
    if not OPTIONS.candidate:
        parser.error('--mcp-demo requires a built --candidate')
    demo = CadHTTPTest('test_mcp_browser_and_stdio')
    try:
        demo.setUpClass()
        demo.setUp()
        account = demo.login(display_name='MCP-Testkonto', groups=['mcp-personal'])
        demo.enable_mcp()
        demo.seed_permissions(('group:mcp-personal', '', 'mcp', 'allow'))
        payload = {'origin': demo.origin, 'cookies': account.cookies, 'demo': True}
        command = ['node', str(ROOT/'tests/cad_browser_test.mjs')]
        with subprocess.Popen(command, stdin=subprocess.PIPE, text=True, start_new_session=True) as browser:
            try:
                browser.communicate(json.dumps(payload))
            except KeyboardInterrupt:
                browser.terminate()
                try:
                    browser.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    browser.kill()
                return
            if browser.returncode:
                raise subprocess.CalledProcessError(browser.returncode, command)
    finally:
        demo.doCleanups()
        demo.doClassCleanups()


if __name__ == '__main__':
    if OPTIONS.mcp_demo:
        mcp_demo()
    else:
        unittest.main(argv=[__file__]+remaining)
