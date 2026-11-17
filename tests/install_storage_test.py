#!/usr/bin/env python3
"""Disposable integrated installer/upgrade/downgrade and cleanup tests; no host writes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--php',required=True);p.add_argument('--layerling',type=Path,required=True);OPTIONS,remaining=p.parse_known_args()
spec=importlib.util.spec_from_file_location('legacy_install',ROOT/'tests/install_sso_test.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
class StorageInstallTest(unittest.TestCase):
    install=legacy.InstallTest.install
    save=legacy.InstallTest.save
    def setUp(self):
        legacy.InstallTest.setUp(self)
        self.portal=self.artifact
        self.artifact=legacy.package.package(self.root/'storage-artifact',str(self.base/'private'),OPTIONS.layerling,str(self.public))
        manifest=json.loads((self.artifact/'manifest.json').read_text());manifest['sourceCommit']='b'*40;(self.artifact/'manifest.json').write_text(json.dumps(manifest))
    def refresh_hash(self,name):
        p=self.artifact/name;manifest=json.loads((self.artifact/'manifest.json').read_text());manifest['files'][name]=hashlib.sha256(p.read_bytes()).hexdigest();(self.artifact/'manifest.json').write_text(json.dumps(manifest))
    def test_01_install_storage_and_real_native_bootstrap(self):
        r=self.install();self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue((self.base/'private/projects').is_dir());self.assertTrue((self.base/'private/sessions').is_dir());self.assertTrue((self.public/'files.php').exists())
        script="$_SERVER=['HTTP_HOST'=>'cad.example.invalid','HTTPS'=>'on','DOCUMENT_ROOT'=>$argv[1],'REQUEST_URI'=>'/','REQUEST_METHOD'=>'GET']; require $argv[1].'/index.php';"
        result=subprocess.run([OPTIONS.php,'-r',script,str(self.public)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Der Dateitest ist freigeschaltet',result.stdout)
        script="$_SERVER=['HTTP_HOST'=>'cad.example.invalid','HTTPS'=>'on','DOCUMENT_ROOT'=>$argv[1],'REQUEST_URI'=>'/store.php','REQUEST_METHOD'=>'GET'];register_shutdown_function(static fn()=>fwrite(STDERR,(string)http_response_code()));require $argv[1].'/store.php';"
        result=subprocess.run([OPTIONS.php,'-r',script,str(self.public)],capture_output=True,text=True)
        self.assertEqual(result.stderr,'401');self.assertEqual(json.loads(result.stdout),{'error':'authentication_required'})
    def test_02_upgrade_preserves_secret_and_runtime(self):
        storage=self.artifact;self.artifact=self.portal;self.assertEqual(self.install().returncode,0);self.artifact=storage
        runtime=self.base/'private';(runtime/'principals.json').write_text('{"preserved":true}');(runtime/'sso-sessions/sess_fixture').write_text('preserved')
        before=self.env.read_bytes();self.assertEqual(self.install().returncode,0)
        self.assertEqual(self.env.read_bytes(),before);self.assertEqual((runtime/'principals.json').read_text(),'{"preserved":true}')
        self.assertEqual((runtime/'sso-sessions/sess_fixture').read_text(),'preserved');self.assertEqual(len(list((self.base/'backups').iterdir())),1)
    def test_03_managed_downgrade_removes_api_but_keeps_projects(self):
        self.assertEqual(self.install().returncode,0);data=self.base/'private/projects/keep';data.write_text('kept')
        self.artifact=self.portal;r=self.install();self.assertEqual(r.returncode,0,r.stderr)
        for name in ['files.php','files.js','files.css','store.php','owners.php','session.php']:self.assertFalse((self.public/name).exists())
        self.assertEqual(data.read_text(),'kept');self.assertFalse((self.base/'private/app/storage.json').exists())
    def test_04_upstream_hash_mismatch_refused(self):
        path='private/app/upstream/store.php';f=self.artifact/path;f.write_bytes(f.read_bytes()+b'\n//tampered');self.refresh_hash(path)
        self.assertNotEqual(self.install().returncode,0);self.assertFalse((self.public/'store.php').exists())
    def test_05_role_and_public_target_configuration_checked(self):
        path='private/app/storage.json';f=self.artifact/path;original=f.read_text()
        for change in [{'studentRoleId':'ROLE_TEACHER'},{'publicRoot':'/wrong'}]:
            values=json.loads(original);values.update(change);f.write_text(json.dumps(values));self.refresh_hash(path)
            self.assertNotEqual(self.install().returncode,0);self.assertFalse((self.base/'private/app').exists())
    def test_06_cleanup_removes_only_expired_native_context_files(self):
        self.assertEqual(self.install().returncode,0)
        root=self.base/'private';old=root/'sessions'/('sess_'+'a'*64);fresh=root/'sessions'/('sess_'+'b'*64)
        old.write_text('expired');fresh.write_text('current')
        now = time.time()
        os.utime(old, (now-140*60-1, now-140*60-1))
        os.utime(fresh, (now-65*60, now-65*60))
        context=root/'contexts'/('c'*64+'.json');context.write_text('{}');os.utime(context,(time.time()-86400,time.time()-86400))
        project=root/'projects/keep';project.write_text('preserved')
        result=subprocess.run([OPTIONS.php,str(root/'app/src/Oidc/cleanup.php')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(old.exists());self.assertFalse(context.exists());self.assertTrue(fresh.exists());self.assertTrue(project.exists())
if __name__=='__main__':unittest.main(argv=[__file__,*remaining],verbosity=2)
