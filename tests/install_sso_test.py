#!/usr/bin/env python3
"""Installer and production bootstrap tests in disposable local directories only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--php',required=True);p.add_argument('--layerling',type=Path);OPTIONS,remaining=p.parse_known_args()
spec=importlib.util.spec_from_file_location('sso_package',ROOT/'scripts/package-sso-test.py');package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='sso-sso-install-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.base=self.root/'host-private';self.base.mkdir()
        self.public=self.root/'web';self.public.mkdir()
        self.artifact=package.package(self.root/'artifact',str(self.base/'private'))
        self.env=self.base/'.env';self.env.write_text('SSO_LAYERLING_OIDC_CLIENT_ID=test-client\nSSO_LAYERLING_OIDC_CLIENT_SECRET=synthetic-secret-not-real\n');self.env.chmod(0o600)
        self.manifest=json.loads((self.artifact/'manifest.json').read_text());self.manifest['sourceCommit']='a'*40;self.save()
    def save(self): (self.artifact/'manifest.json').write_text(json.dumps(self.manifest))
    def install(self):
        return subprocess.run([OPTIONS.php,str(ROOT/'scripts/install-sso-test.php'),'--package='+str(self.artifact),'--base='+str(self.base),'--public='+str(self.public),'--local-test'],capture_output=True,text=True)
    def test_01_install_and_real_host_bootstrap(self):
        result=self.install();self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.base/'private/contexts').is_dir());self.assertTrue((self.base/'private/sso-sessions').is_dir())
        self.assertEqual((self.env.stat().st_mode&0o777),0o600)
        script="$_SERVER=['HTTP_HOST'=>'cad.example.invalid','HTTPS'=>'on','DOCUMENT_ROOT'=>$argv[1],'REQUEST_URI'=>'/','REQUEST_METHOD'=>'GET']; require $argv[1].'/index.php';"
        response=subprocess.run([OPTIONS.php,'-r',script,str(self.public)],capture_output=True,text=True)
        self.assertEqual(response.returncode,0,response.stderr);self.assertIn('Mit IServ anmelden',response.stdout)
        self.assertIn('href="/files.css"', response.stdout)
        self.assertEqual((self.public/'files.css').read_bytes(), (self.artifact/'public/files.css').read_bytes())
        self.assertNotIn('synthetic-secret',response.stdout+response.stderr)
    def test_02_checksum_mismatch_refused_before_activation(self):
        (self.artifact/'public/index.php').write_text('TAMPERED')
        self.assertNotEqual(self.install().returncode,0)
        self.assertFalse((self.base/'private/app').exists());self.assertFalse((self.public/'index.php').exists())
    def test_registered_client_mismatch_refused_before_activation(self):
        target=self.artifact/'private/app/deployment-target.json'
        target.write_text(json.dumps({'clientId':'synthetic-registered-client'}))
        self.manifest['files']['private/app/deployment-target.json']=hashlib.sha256(target.read_bytes()).hexdigest()
        self.save()
        result=self.install()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Wrong registered client',result.stderr)
        self.assertFalse((self.base/'private/app').exists())
        self.env.write_text('SSO_LAYERLING_OIDC_CLIENT_ID=synthetic-registered-client\nSSO_LAYERLING_OIDC_CLIENT_SECRET=synthetic-secret-not-real\n')
        result=self.install()
        self.assertEqual(result.returncode,0,result.stderr)
    def test_03_unmanaged_website_preserved(self):
        (self.public/'index.html').write_text('Existing website')
        self.assertNotEqual(self.install().returncode,0)
        self.assertEqual((self.public/'index.html').read_text(),'Existing website');self.assertFalse((self.public/'index.php').exists())
    def test_04_update_preserves_secret_principals_sessions_and_backup(self):
        self.assertEqual(self.install().returncode,0)
        private=self.base/'private';(private/'principals.json').write_text('{"fixture":"preserved"}')
        (private/'sso-sessions/sess_fixture').write_text('preserve')
        before=self.env.read_bytes()
        self.assertEqual(self.install().returncode,0)
        self.assertEqual((private/'principals.json').read_text(),'{"fixture":"preserved"}')
        self.assertEqual((private/'sso-sessions/sess_fixture').read_text(),'preserve');self.assertEqual(self.env.read_bytes(),before)
        self.assertEqual(len(list((self.base/'backups').iterdir())),1)
    def test_05_uncommitted_package_and_insecure_env_refused(self):
        self.manifest['sourceCommit']=None;self.save();self.assertNotEqual(self.install().returncode,0)
        self.manifest['sourceCommit']='a'*40;self.save();self.env.chmod(0o644)
        self.assertNotEqual(self.install().returncode,0);self.assertFalse((self.base/'private/app').exists())
    def test_06_added_public_endpoint_refused_even_with_new_hash(self):
        p=self.artifact/'public/store.php';p.write_text('<?php echo "forbidden";')
        self.manifest['files']['public/store.php']=hashlib.sha256(p.read_bytes()).hexdigest();self.save()
        self.assertNotEqual(self.install().returncode,0);self.assertFalse((self.public/'store.php').exists())
if __name__=='__main__':unittest.main(argv=['install_sso_test.py']+remaining,verbosity=2)
