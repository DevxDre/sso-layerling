#!/usr/bin/env python3
"""Same real upstream storage regressions under the new, isolated last-SSO-login model.

The historical 35-test suite remains unchanged and runs separately. Only its two
model-specific freshness/configuration tests are overridden with the new contract.
All sessions, principals and logins here are synthetic CLI-only fixtures.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import unittest
spec=importlib.util.spec_from_file_location('storage_support',Path(__file__).with_name('storage_http_test.py'))
storage=importlib.util.module_from_spec(spec);spec.loader.exec_module(storage)

class SsoStorageHTTPTest(storage.StorageHTTPTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path=cls.private/'config.json';c=json.loads(path.read_text())
        c.update(authorizationModel='sso-last-login',studentRoleId='ROLE_STUDENT',studentGroupIds=['test-student-id'])
        path.write_text(json.dumps(c))
    def principal(self,user,**changes):
        records=json.loads((self.private/'principals.json').read_text())
        current=records.get(user,{})
        roles=changes.get('roles',current.get('roles',[]));groups=changes.get('groups',current.get('groups',[]))
        classified=roles==['ROLE_STUDENT'] or (roles==[] and isinstance(groups,list) and 'test-student-id' in groups)
        changes.setdefault('identityHash',current.get('identityHash',hashlib.sha256(('fixture-'+user).encode()).hexdigest()))
        changes.setdefault('loginSequence',current.get('loginSequence',1))
        changes.setdefault('student',classified)
        super().principal(user,**changes)
    def login(self,uuid,sequence,roles=None,groups=None,at=None):
        claims={'sub':'pairwise-fixture','iserv:uuid':uuid,'iserv:groups':{} if groups is None else {g:{'id':g,'name':'Fixture'}for g in groups}}
        if roles is not None:claims['iserv:roles']=[{'id':role}for role in roles]
        fixture=r"""
        require $argv[1];
        try {
            $data=json_decode($argv[3],true,32,JSON_THROW_ON_ERROR);
            $identity=new \Sso\Layerling\Oidc\Identity(\Sso\Layerling\Oidc\Config::ISSUER,$data['sub'],$data,$data,'site','/');
            $claims=\Sso\Layerling\Oidc\Claims::from($identity);
            $owner=(new \Sso\Layerling\Oidc\PrincipalWriter($argv[2]))->write($claims,(int)$argv[4],(int)$argv[5],['test-student-id'],'ROLE_STUDENT');
            echo $owner;
        } catch(\Sso\Layerling\Oidc\LoginFailed $e) { exit(5); }
        """
        return subprocess.run([storage.OPTIONS.php,'-r',fixture,str(storage.ROOT/'vendor/autoload.php'),str(self.private),json.dumps(claims),str(sequence),str(int(time.time())if at is None else at)],capture_output=True,text=True)
    def test_24_stale_future_and_missing_evidence_fail_closed(self):
        client,actor=self.privileged()
        self.principal(storage.B,roles=['ROLE_STUDENT'],checkedAt=int(time.time())-365*86400)
        self.principal(actor,checkedAt=int(time.time())-3600)
        self.json_response(self.request(query=self.scoped(storage.B),client=client))
        for stamp in [int(time.time())+100,None,'recent',0]:
            self.principal(actor,checkedAt=stamp)
            self.json_response(self.request(query=self.scoped(storage.B),client=client),403)
        self.principal(actor,checkedAt=int(time.time()))
        expired=self.issue(actor,issuedAt=int(time.time())-3601,lastSeen=int(time.time()))
        self.json_response(self.request(query=self.scoped(storage.B),client=expired),401)
        self.principal(storage.B,enabled=False)
        self.json_response(self.request(query=self.scoped(storage.B),client=client),403)
        self.principal(actor,groups=['test-admins-id'])
        self.json_response(self.request(query=self.scoped(storage.B),client=client))
    def test_29_registry_and_policy_configuration_fail_closed(self):
        path=self.private/'config.json';original=json.loads(path.read_text())
        bad=[{'authorizationModel':'unknown'},{'studentGroupIds':'test-student-id'},
             {'studentGroupIds':['test-student-id',123]},{'studentRoleId':['ROLE_STUDENT']},
             {'groupIds':{'makerspace':'same','admins':'same'}}]
        try:
            for change in bad:
                path.write_text(json.dumps({**original,**change}))
                self.json_response(self.request(client=self.a),503)
        finally:path.write_text(json.dumps(original))
        for change in [{'student':True,'roles':['ROLE_TEACHER']},{'roles':None},{'groups':None},
                       {'identityHash':'bad'},{'loginSequence':None},{'student':'true'}]:
            self.principal(storage.A,**change)
            self.json_response(self.request(client=self.a),403)
            self.principal(storage.A,roles=[],groups=[],student=False,identityHash='a'*64,loginSequence=1)
        registry=self.private/'principals.json';saved=registry.read_text()
        try:
            registry.write_text('[]');self.json_response(self.request(client=self.a),503)
            registry.write_text('{}');self.json_response(self.request(client=self.a),403)
            registry.write_text('not json');self.json_response(self.request(client=self.a),503)
        finally:registry.write_text(saved)
    def test_36_role_only_student_without_groups_via_real_writer(self):
        result=self.login('11111111-1111-1111-1111-111111111111',10,['ROLE_STUDENT'],[],int(time.time())-365*86400)
        self.assertEqual(result.returncode,0);owner=result.stdout;student=self.issue(owner)
        record=json.loads((self.private/'principals.json').read_text())[owner]
        self.assertTrue(record['student']);self.assertEqual(record['groups'],[])
        self.json_response(self.upload(student,marker='role-only-student'),201)
        maker,_=self.privileged()
        self.assertEqual(self.request(query=self.scoped(owner,fileName='same.lyl'),client=maker)[2],storage.project('role-only-student'))
    def test_37_missing_and_empty_roles_group_fallback_via_writer(self):
        maker,_=self.privileged()
        for i,roles in enumerate([None,[]]):
            result=self.login(f'22222222-2222-2222-2222-22222222222{i}',20+i,roles,['test-student-id'])
            self.assertEqual(result.returncode,0);owner=result.stdout
            self.assertTrue(json.loads((self.private/'principals.json').read_text())[owner]['student'])
            self.json_response(self.request(query=self.scoped(owner),client=maker))
            self.json_response(self.request('DELETE',self.scoped(owner,fileName='missing.lyl'),client=maker),403)
    def test_38_teacher_and_mixed_roles_do_not_fallback(self):
        maker,_=self.privileged()
        for i,roles in enumerate([['ROLE_TEACHER'],['ROLE_STUDENT','ROLE_TEACHER'],['ROLE_TEACHER','ROLE_ADMIN','ROLE_TEACH_AKTIV']]):
            result=self.login(f'33333333-3333-3333-3333-33333333333{i}',30+i,roles,['test-student-id'])
            self.assertEqual(result.returncode,0);owner=result.stdout
            self.assertFalse(json.loads((self.private/'principals.json').read_text())[owner]['student'])
            self.json_response(self.request(query=self.scoped(owner),client=maker),403)
    def test_39_next_owner_login_revokes_student_status_without_changing_owner(self):
        uuid='44444444-4444-4444-4444-444444444444'
        first=self.login(uuid,40,['ROLE_STUDENT']);self.assertEqual(first.returncode,0);owner=first.stdout
        original=self.issue(owner);self.json_response(self.upload(original,marker='keep-owner'),201)
        maker,_=self.privileged();self.assertEqual(self.request(query=self.scoped(owner,fileName='same.lyl'),client=maker)[0],200)
        next_login=self.login(uuid,41,['ROLE_TEACHER']);self.assertEqual(next_login.stdout,owner)
        self.json_response(self.request(query=self.scoped(owner,fileName='same.lyl'),client=maker),403)
        stale=self.login(uuid,40,['ROLE_STUDENT']);self.assertEqual(stale.returncode,5)
        self.json_response(self.request(query=self.scoped(owner,fileName='same.lyl'),client=maker),403)
        self.assertEqual(self.request(query={'fileName':'same.lyl'},client=original)[2],storage.project('keep-owner'))
    def test_40_next_actor_login_revokes_groups_in_existing_session(self):
        uuid='55555555-5555-5555-5555-555555555555'
        self.principal(storage.B,roles=['ROLE_STUDENT'])
        first=self.login(uuid,50,['ROLE_TEACHER'],['test-makerspace-id','test-admins-id']);self.assertEqual(first.returncode,0)
        client=self.issue(first.stdout);self.json_response(self.request(query=self.scoped(storage.B),client=client))
        revoked=self.login(uuid,51,['ROLE_ADMIN'],[]);self.assertEqual(revoked.stdout,first.stdout)
        self.json_response(self.request(query=self.scoped(storage.B),client=client),403)
        stale=self.login(uuid,50,['ROLE_TEACHER'],['test-admins-id']);self.assertEqual(stale.returncode,5)
        self.json_response(self.request(query=self.scoped(storage.B),client=client),403)
        self.json_response(self.request(client=client,path='/session.php'))

if __name__=='__main__':unittest.main(argv=[__file__,*storage.remaining],verbosity=2)
