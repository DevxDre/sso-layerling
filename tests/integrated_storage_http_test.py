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
parser.add_argument('--alternate-profile', action='store_true');OPTIONS,remaining=parser.parse_known_args()
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
    alternate = json.loads((ROOT/'tests/oidc-alternate.json').read_text()) if OPTIONS.alternate_profile else None
    alternate_roles = {'ROLE_STUDENT': 'learner', 'ROLE_TEACHER': 'instructor',
                       'ROLE_ADMIN': 'operator', 'ROLE_TEACH_AKTIV': 'active-instructor'}
    class_prefix = 'cohort-' if alternate else 'klasse.'
    router = ROOT/'scripts/mcp-test-router.php'
    rights_admin_role = 'permissions-operator'

    def provider_role(self, role):
        return self.alternate_roles.get(role, role) if self.alternate else role

    def provider_group(self, group):
        if self.alternate and group in (MAKER, ADMIN):
            return self.alternate['groupBindings']['makerspace' if group == MAKER else 'admins']
        return group
    @classmethod
    def setUpClass(cls):
        original=sso.package.package
        def package(output, installed_private):
            deployment = None
            if cls.alternate:
                deployment = output.parent/'deployment.local.json'
                deployment.write_text(json.dumps(cls.alternate))
                deployment.chmod(0o600)
            return original(output, installed_private, OPTIONS.layerling, str(output/'public'),
                            deployment_config_path=deployment)
        with patch.object(sso.package,'package',package):sso.SsoHTTPTest.setUpClass.__func__(cls)
        for name in ['sessions','projects','templates']:(cls.private/name).mkdir(mode=0o700)
        (cls.private/'audit.jsonl').touch()
        config=cls.private/'app/storage.json';values=json.loads(config.read_text());values['origin']=cls.origin;config.write_text(json.dumps(values))
        bootstrap=cls.runtime/'public/_sso.php';text=bootstrap.read_text()
        text=text.replace(",'"+cls.origin+"');", ",'"+cls.origin+"',\\Sso\\Layerling\\StorageConfig::load('"+str(config)+"'));")
        cls.dotenv = cls.root/'.env'
        cls.dotenv.touch(mode=0o600)
        cls.dotenv_defaults = ('SSO_LAYERLING_OIDC_CLIENT_ID=test-client\n'
                               'SSO_LAYERLING_OIDC_CLIENT_SECRET=synthetic-secret-not-real\n')
        text = text.replace(
            r"new \Sso\Layerling\Oidc\Config('test-client',str_repeat('s',32),$profile)",
            rf"\Sso\Layerling\Oidc\Config::fromFile('{cls.dotenv}',$profile)",
        )
        bootstrap.write_text(text)
    def setUp(self):
        sso.SsoHTTPTest.setUp(self)
        (self.private/'principals.json').write_text('{}')
        (self.private/'permissions.json').unlink(missing_ok=True)
        self.dotenv.write_text(self.dotenv_defaults + 'SSO_LAYERLING_ADMIN_ROLE=' + self.rights_admin_role + '\n')
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
        if self.alternate:
            memberships = [{'key': self.provider_group(group), 'title': value['name'],
                            'handle': value.get('act')} for group, value in claims['iserv:groups'].items()]
            claims = {'sub': claims['sub'], 'permissions': [self.provider_role(r['id']) for r in claims['iserv:roles']],
                      'memberships': memberships, 'display_name': claims.get('name'),
                      'login_handle': claims.get('preferred_username')}
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

    def seed_permissions(self, *rules):
        records = [dict(actor=actor, owner=owner, operation=operation, effect=effect)
                   for actor, owner, operation, effect in rules]
        (self.private/'permissions.json').write_text(json.dumps({'version': 1, 'rules': records, 'patterns': []}))

    def ownership_rules(self, *groups):
        for group in groups:
            actor = 'group:' + self.provider_group(group)
            roles = ['ROLE_STUDENT'] if group == MAKER else ['ROLE_STUDENT', 'ROLE_TEACHER']
            operations = ['read', 'write'] if group == MAKER else ['read', 'write', 'delete']
            for role in roles:
                for operation in operations:
                    yield (actor, 'role:' + self.provider_role(role), operation, 'allow')

    def publisher_rule(self):
        return ('role:' + self.provider_role('ROLE_TEACHER'), '', 'publish', 'allow')

    def change_rule(self, admin, operation, actor, *, owner='', effect='allow', group_names_version=''):
        form = {'csrf': admin.csrf, 'action': 'save-rule', 'operation': operation,
                'actor': actor, 'owner': owner, 'effect': effect, 'groupNamesVersion': group_names_version}
        response = admin.request('/rechte.php', 'POST', form)
        self.assertEqual((response[0], response[1].get('location')), (303, '/rechte.php?saved=1'), response[2][:300])

    def test_permissions_page_access_and_file_rules(self):
        path = '/rechte.php'
        learner = self.login(groups=['lab', 'legacy-only'], group_acts={'lab': 'makerspace-lab'})
        legacy_admin = self.login(U2, ['ROLE_ADMIN'], [ADMIN])
        operator = self.login(UA, [self.rights_admin_role])
        tutor = self.login(UM, ['ROLE_TEACHER'], ['tutoring'], group_acts={'tutoring': 'mentors'})
        self.assertEqual(self.raw(sso.Client(self), path=path)[0], 401)
        self.assertEqual(legacy_admin.request(path)[0], 403)
        self.assertEqual(self.raw(operator, path=path)[0], 200)
        options = self.raw(operator, path=path)[2]
        self.assertIn(b'value="groups:makerspace-lab"', options)
        self.assertNotIn(b'value="group:lab"', options)
        self.assertNotIn(b'value="group:legacy-only"', options)
        self.assertIn(b'value="groups:mentors"', options)
        group_names_version = re.search(rb'name="groupNamesVersion" value="([a-f0-9]{64})"', options)[1].decode()
        self.assertIn(b'value="role:' + self.provider_role('ROLE_TEACHER').encode() + b'"', options)
        form = {'csrf': operator.csrf, 'action': 'add-pattern', 'pattern': 'makerspace^'}
        self.assertEqual(tutor.request(path, 'POST', form | {'csrf': tutor.csrf})[0], 403)
        self.assertEqual(operator.request(path, 'POST', form | {'csrf': 'invalid'})[0], 403)
        self.assertEqual(operator.request(path, 'POST', form, {'Origin': 'https://foreign.invalid'})[0], 403)
        invalid_pattern = operator.request(path, 'POST', form | {'pattern': '.*'})
        self.assertEqual(invalid_pattern[0], 400)
        self.assertRegex(invalid_pattern[2], rb'id="group-pattern"[^>]+value="\.\*"[^>]+aria-describedby="group-pattern-error" autofocus')
        self.assertIn(b'id="group-pattern-error" role="alert"', invalid_pattern[2])
        invalid_rule = operator.request(path, 'POST', {
            'csrf': operator.csrf, 'action': 'save-rule', 'ruleForm': 'features',
            'actor': 'Gruppe <Test>', 'operation': 'mcp', 'effect': 'deny',
        })
        self.assertEqual(invalid_rule[0], 400)
        self.assertRegex(invalid_rule[2], rb'id="features-actor"[^>]+value="Gruppe &lt;Test&gt;"[^>]+aria-describedby="features-actor-error"')
        self.assertIn(b'<option value="mcp" selected>', invalid_rule[2])
        self.assertIn(b'<option value="deny" selected>', invalid_rule[2])
        self.assertFalse((self.private/'permissions.json').exists())

        original = self.json(self.upload(learner, 'original'), 201)['project']
        delete_headers = {'If-Match': '"' + original['revision'] + '"'}
        filename = '/store.php?' + urlencode({'_sso_owner': learner.owner, 'fileName': 'same.lyl'})
        teacher_role = 'role:' + self.provider_role('ROLE_TEACHER')
        subject_role = 'role:' + self.provider_role('ROLE_STUDENT')
        self.json(self.raw(operator, path=filename), 403)
        self.json(self.raw(legacy_admin, path=filename), 403)
        self.json(self.upload(legacy_admin, 'denied', learner.owner, name='legacy.lyl'), 403)
        self.json(self.raw(legacy_admin, 'DELETE', filename, headers=delete_headers), 403)
        self.assertEqual(len(self.json(self.raw(legacy_admin, path='/owners.php'))['owners']), 1)
        self.change_rule(operator, 'read', teacher_role, owner='groups:makerspace-lab',
                         group_names_version=group_names_version)
        saved = json.loads((self.private/'permissions.json').read_text())['rules']
        self.assertEqual(saved[0]['owner'], 'group:lab')
        visible = self.json(self.raw(tutor, path='/owners.php'))['owners']
        other = next(record for record in visible if record['userId'] == learner.owner)
        self.assertFalse(other['canWrite'])
        self.assertFalse(other['canDelete'])
        self.assertEqual(self.raw(tutor, path=filename)[2], project('original'))
        self.json(self.upload(tutor, 'changed', learner.owner, name='new.lyl'), 403)
        self.change_rule(operator, 'write', 'group:tutoring', owner=subject_role)
        self.assertEqual(self.upload(tutor, 'changed', learner.owner, name='new.lyl')[0], 201)
        self.assertEqual(self.raw(learner, path='/store.php?fileName=new.lyl')[2], project('changed'))
        self.json(self.raw(tutor, 'DELETE', filename), 403)
        self.change_rule(operator, 'delete', teacher_role, owner=subject_role)
        self.assertEqual(self.raw(tutor, 'DELETE', filename, headers=delete_headers)[0], 200)
        new_file = filename.replace('same.lyl', 'new.lyl')
        self.change_rule(operator, 'read', 'group:tutoring', owner=subject_role, effect='deny')
        self.json(self.raw(tutor, path=new_file), 403)
        self.assertNotIn(learner.owner, [entry['userId'] for entry in self.json(self.raw(tutor, path='/owners.php'))['owners']])
        self.change_rule(operator, 'write', teacher_role, owner='group:legacy-only', effect='deny')
        self.json(self.upload(tutor, 'denied', learner.owner, name='denied.lyl'), 403)

        saved_page = operator.request(path)[2]
        self.assertIn(b'<span class="sso-wrap">groups:makerspace-lab</span>', saved_page)
        self.assertIn(b'<span class="sso-wrap">groups:mentors</span>', saved_page)
        self.assertIn(b'<span class="sso-wrap">group:legacy-only</span>', saved_page)
        keys = re.findall(rb'name="key" value="([a-f0-9]{64})"', saved_page)
        self.assertEqual(len(keys), 5)
        self.assertEqual(operator.request(path, 'POST', {
            'csrf': operator.csrf, 'action': 'remove-rule', 'key': keys[3].decode(), 'effect': 'deny',
        })[0], 303)
        self.assertEqual(self.raw(tutor, path=new_file)[2], project('changed'))

        self.login(groups=['lab'], group_acts={'lab': 'renamed-lab'})
        self.login(U2, ['ROLE_ADMIN'], [ADMIN, 'other-lab'], group_acts={'other-lab': 'makerspace-lab'})
        rules_before = (self.private/'permissions.json').read_bytes()
        outdated = operator.request(path, 'POST', {
            'csrf': operator.csrf, 'action': 'save-rule', 'operation': 'read',
            'actor': teacher_role, 'owner': 'groups:makerspace-lab', 'effect': 'allow',
            'groupNamesVersion': group_names_version,
        })
        self.assertEqual(outdated[0], 400)
        self.assertIn('Wähle die betroffenen Gruppenaccounts erneut aus.'.encode(), outdated[2])
        self.assertRegex(outdated[2], rb'id="accounts-owner"[^>]+value=""')
        self.assertRegex(outdated[2], rb'id="accounts-actor"[^>]+value="' + re.escape(teacher_role.encode()) + rb'"')
        self.assertEqual((self.private/'permissions.json').read_bytes(), rules_before)
        self.assertIn(b'<span class="sso-wrap">groups:renamed-lab</span>', operator.request(path)[2])
        self.assertEqual(self.raw(tutor, path=new_file)[2], project('changed'))
        self.dotenv.write_text(self.dotenv_defaults)
        self.assertEqual(operator.request(path)[0], 403)
        self.dotenv.write_text(self.dotenv_defaults + 'SSO_LAYERLING_ADMIN_ROLE=' + self.rights_admin_role + '\n')
        self.login(UA, ['ROLE_TEACHER'])
        self.assertEqual(operator.request(path)[0], 403)

    def test_permission_rules_for_templates_and_mcp(self):
        operator = self.login(UA, [self.rights_admin_role])
        instructor = self.login(UM, ['ROLE_ADMIN'], ['target', 'other'],
                                group_acts={'target': 'makerspace-demo', 'other': 'archive-makerspace'})
        learner = self.login(groups=['target'])
        actor = 'role:' + self.provider_role('ROLE_ADMIN')
        self.json(self.raw(instructor, path='/vorlagen.php'), 403)
        self.change_rule(operator, 'publish', actor)
        form = {'csrf': operator.csrf, 'action': 'add-pattern', 'pattern': 'makerspace^'}
        self.assertEqual(operator.request('/rechte.php', 'POST', form)[0], 303)
        result = self.raw(instructor, path='/vorlagen.php')
        self.assertEqual(result[0], 200)
        self.assertIn(b'name="groups[]" value="target"', result[2])
        self.assertNotIn(b'name="groups[]" value="other"', result[2])
        self.json(self.publish_template(instructor, ['other']), 403)
        self.assertEqual(self.publish_template(instructor, ['target'])[0], 201)
        self.assertIn(b'data-copy-template', self.raw(learner, path='/vorlagen.php')[2])
        self.change_rule(operator, 'publish', actor, effect='deny')
        self.json(self.publish_template(instructor, ['target']), 403)
        self.assertIn(b'data-copy-template', self.raw(learner, path='/vorlagen.php')[2])

        config_path = self.private/'app/mcp-test.json'
        legacy = {'accounts': [instructor.owner], 'roles': [], 'groups': []}
        config_path.write_text(json.dumps({'allow': legacy, 'deny': dict(legacy, accounts=[])}))
        self.addCleanup(config_path.unlink, missing_ok=True)
        mcp = '/api/layerling-mcp'
        def pair():
            return self.raw(instructor, 'POST', mcp, '{"type":"pair"}', {'Content-Type': 'application/json'})
        self.json(pair(), 403)
        config_path.write_text(json.dumps({'allow': dict(legacy, accounts=[]), 'deny': legacy}))
        self.change_rule(operator, 'mcp', 'group:target')
        token = self.json(pair())['token']
        bearer = {'Authorization': 'Bearer ' + token}
        self.assertEqual(self.raw(sso.Client(self), path=mcp, headers=bearer)[0], 200)
        self.change_rule(operator, 'mcp', actor, effect='deny')
        self.json(pair(), 403)
        self.json(self.raw(sso.Client(self), path=mcp, headers=bearer), 403)

    def test_template_permissions_follow_latest_iserv_login(self):
        path = '/vorlagen.php'
        self.json(self.raw(sso.Client(self), path=path), 401)
        teacher = self.login(UA, ['ROLE_TEACHER', 'ROLE_TEACH_AKTIV'], ['class-a', 'class-b'])
        student = self.login(U1, groups=['class-b'])
        outsider = self.login(U2, groups=['class-c'])
        admin = self.login(UM, ['ROLE_ADMIN'], [ADMIN, 'class-a'])
        self.json(self.raw(teacher, path=path), 403)
        self.json(self.publish_template(teacher, ['class-a']), 403)
        self.seed_permissions(self.publisher_rule())
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
    @unittest.skipUnless(OPTIONS.alternate_profile, 'Alternate provider claim contract')
    def test_alternate_profile_login_diagnostics_and_claim_validation(self):
        client = sso.Client(self)
        csrf, page = self.page(client)
        self.assertIn(b'Mit Campus &lt;Test&gt; anmelden', page[2])
        self.assertIn("form-action 'self' https://identity.example.invalid", page[1]['content-security-policy'])
        response = client.request('/auth/start.php', 'POST', {'csrf': csrf})
        self.assertTrue(response[1]['location'].startswith('https://identity.example.invalid/workshop/oauth/authorize?'))
        self.assertIn('scope=openid%20profile%20memberships', response[1]['location'])
        mentor = self.provider_group(MAKER)
        claims = {'sub': 'Case-Sensitive-User', 'permissions': ['learner'], 'memberships': [
            {'key': mentor, 'title': 'Verified mentors'},
            {'key': 'unlisted', 'title': 'Private fixture'},
        ]}
        callback = self.callback_for_redirect(client, response, claims=claims)
        self.assertEqual(client.request(callback)[0], 303)
        profile_page = client.request('/konto/' if getattr(self, 'login_page', '/') == '/index.php' else '/')[2]
        self.assertIn('Anmeldung über Campus &lt;Test&gt; erfolgreich'.encode(), profile_page)
        self.assertIn(b'Verified mentors', profile_page)
        self.assertNotIn(b'Private fixture', profile_page)
        owners = self.json(self.raw(client, path='/owners.php'))['owners']
        owner = next(entry['userId'] for entry in owners if entry['isSelf'])
        registry = json.loads((self.private/'principals.json').read_text())
        self.assertEqual(registry[owner]['identityHash'],
                         hashlib.sha256(b'https://identity.example.invalid/realms/workshop\0Case-Sensitive-User').hexdigest())

        for override, userinfo in [
            ({'permissions': {'0': 'instructor'}}, {}),
            ({'memberships': [{'key': mentor, 'title': 'x'}, {'key': mentor, 'title': 'y'}]}, {}),
            ({'memberships': [{'key': 123}]}, {}),
            ({}, {'permissions': ['instructor']}),
        ]:
            with self.subTest(override=override, userinfo=userinfo):
                rejected = sso.Client(self)
                callback, _ = self.begin(rejected, claims=claims | override, userinfoClaims=userinfo)
                self.assertEqual(rejected.request(callback)[0], 503)
                self.assertNotIn('SSO_LAYERLING_SESSION', rejected.cookies)
        self.assertEqual(json.loads((self.private/'principals.json').read_text()), registry)

        ordinary = self.login(U2, ['ROLE_ADMIN'])
        spoof = sso.Client(self)
        spoof_claims = {'sub': 'same-label-account', 'permissions': ['operator'],
                        'memberships': [{'key': 'unlisted', 'title': mentor}]}
        callback, _ = self.begin(spoof, claims=spoof_claims)
        self.assertEqual(spoof.request(callback)[0], 303)
        self.json(self.raw(spoof, path='/store.php?'+urlencode({'_sso_owner': ordinary.owner})), 403)
        self.json(self.raw(spoof, path='/vorlagen.php'), 403)

    @unittest.skipUnless(OPTIONS.alternate_profile, 'Alternate provider claim contract')
    def test_group_claim_change_requires_fresh_privileges_and_keeps_student_owner(self):
        student = self.login()
        mentor = self.login(UM, ['ROLE_TEACHER'], [MAKER])
        self.seed_permissions(*self.ownership_rules(MAKER))
        self.json(self.upload(student, 'existing student'), 201)
        personal = '/store.php?fileName=same.lyl'
        foreign = personal + '&' + urlencode({'_sso_owner': student.owner})
        self.assertEqual(self.raw(mentor, path=foreign)[2], project('existing student'))

        app = self.private/'app'
        profile_file, storage_file = app/'oidc-profile.json', app/'storage.json'
        original_profile, original_storage = profile_file.read_text(), storage_file.read_text()
        profile, storage = json.loads(original_profile), json.loads(original_storage)
        profile['provider']['claims']['groups']['claim'] = 'verified_memberships'
        default = json.loads((ROOT/'config/oidc-iserv.json').read_text())
        storage['authorizationMapping'] = sso.package.authorization_mapping(profile['provider'], default)
        profile_file.write_text(json.dumps(profile))
        storage_file.write_text(json.dumps(storage))
        try:
            self.json(self.raw(mentor, path=foreign), 403)
            self.assertEqual(self.raw(student, path=personal)[2], project('existing student'))
            refreshed = sso.Client(self)
            callback, _ = self.begin(refreshed, claims={
                'sub': 'pairwise-' + UM, 'permissions': ['instructor'],
                'verified_memberships': [{'key': self.provider_group(MAKER)}],
            })
            self.assertEqual(refreshed.request(callback)[0], 303)
            self.json(self.raw(refreshed, path=foreign), 403)
            refreshed_student = sso.Client(self)
            callback, _ = self.begin(refreshed_student, claims={
                'sub': 'pairwise-' + U1, 'permissions': ['learner'], 'verified_memberships': [],
            })
            self.assertEqual(refreshed_student.request(callback)[0], 303)
            self.assertEqual(self.raw(refreshed, path=foreign)[2], project('existing student'))
            owners = self.json(self.raw(refreshed, path='/owners.php'))['owners']
            self.assertEqual(next(owner['userId'] for owner in owners if owner['isSelf']), mentor.owner)
        finally:
            profile_file.write_text(original_profile)
            storage_file.write_text(original_storage)

    def test_profile_presentation_upgrade_keeps_owner_projects_and_templates(self):
        teacher = self.login(UA, ['ROLE_TEACHER'], ['class-b'])
        student = self.login(U1, groups=['class-b'])
        self.json(self.upload(student, 'stored before profile update'), 201)
        self.seed_permissions(self.publisher_rule())
        self.assertEqual(self.publish_template(teacher, ['class-b'])[0], 201)
        profile = self.private/'app/oidc-profile.json'
        original = profile.read_text()
        config = json.loads(original)
        config['provider']['name'] = 'Renamed test provider'
        config['provider']['endpoints'] = {
            key: '/updated/' + key for key in config['provider']['endpoints']
        }
        profile.write_text(json.dumps(config))
        try:
            again = self.login(U1, groups=['class-b'])
            self.assertEqual(again.owner, student.owner)
            self.assertEqual(self.raw(again, path='/store.php?fileName=same.lyl')[2], project('stored before profile update'))
            self.assertIn(b'data-copy-template', self.raw(again, path='/vorlagen.php')[2])
            self.assertEqual(self.login(UA, ['ROLE_TEACHER'], ['class-b']).owner, teacher.owner)
        finally:
            profile.write_text(original)

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
        self.assertEqual(len(self.json(self.raw(maker,path='/owners.php'))['owners']), 1)
        self.seed_permissions(*self.ownership_rules(MAKER))
        owners=self.json(self.raw(maker,path='/owners.php'))['owners'];ids={o['userId']for o in owners}
        self.assertEqual(ids,{a.owner,b.owner,maker.owner});self.assertNotIn(teacher.owner,ids)
        self.assertFalse(next(o['canDelete']for o in owners if o['userId']==a.owner))
        self.json(self.upload(maker,'edited',a.owner,record['revision']))
        self.assertEqual(self.raw(a,path='/store.php?fileName=same.lyl')[2],project('edited'))
        self.json(self.raw(maker,'DELETE','/store.php?'+urlencode({'_sso_owner':a.owner,'fileName':'same.lyl'})),403)
        self.json(self.raw(maker,path='/store.php?'+urlencode({'_sso_owner':teacher.owner})),403)
        self.json(self.raw(maker,path='/store.php?'+urlencode({'_sso_owner':a.owner,'settings':'default'})),403)
    def test_05_explicit_admin_rules_allow_selected_owners_and_delete(self):
        a=self.login(U1);teacher=self.login(U2,['ROLE_TEACHER']);self.json(self.upload(teacher,'teacher'),201)
        admin=self.login(UA,['ROLE_TEACHER','ROLE_ADMIN','ROLE_TEACH_AKTIV'],[MAKER,ADMIN])
        self.seed_permissions(*self.ownership_rules(ADMIN))
        owners=self.json(self.raw(admin,path='/owners.php'))['owners']
        self.assertEqual({o['userId']for o in owners},{a.owner,teacher.owner,admin.owner});self.assertTrue(all(o['canDelete']for o in owners))
        record=self.json(self.raw(admin,path='/store.php?'+urlencode({'_sso_owner':teacher.owner})))['projects'][0]
        self.json(self.raw(admin,'DELETE','/store.php?'+urlencode({'_sso_owner':teacher.owner,'fileName':'same.lyl'}),headers={'If-Match':'"'+record['revision']+'"'}))
        self.assertFalse((self.private/'projects'/teacher.owner/'same.lyl').exists())
    def test_06_new_owner_login_changes_student_status_without_changing_files(self):
        a=self.login(U1);self.json(self.upload(a,'keep'),201);maker=self.login(UM,['ROLE_TEACHER'],[MAKER])
        self.seed_permissions(*self.ownership_rules(MAKER))
        query='/store.php?'+urlencode({'_sso_owner':a.owner,'fileName':'same.lyl'});self.assertEqual(self.raw(maker,path=query)[0],200)
        changed=self.login(U1,['ROLE_TEACHER']);self.assertEqual(changed.owner,a.owner)
        self.json(self.raw(maker,path=query),403)
        self.assertNotIn(a.owner,{o['userId']for o in self.json(self.raw(maker,path='/owners.php'))['owners']})
        self.assertEqual(self.raw(a,path='/store.php?fileName=same.lyl')[2],project('keep'))
    def test_07_group_revocation_applies_to_existing_native_session(self):
        a=self.login(U1);maker=self.login(UM,['ROLE_TEACHER'],[MAKER])
        self.seed_permissions(*self.ownership_rules(MAKER))
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
