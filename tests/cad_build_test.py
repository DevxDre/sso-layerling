#!/usr/bin/env python3
"""CAD pin/source integrity and candidate boundaries, using only temporary sources."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--layerling',type=Path,required=True);parser.add_argument('--php',required=True);parser.add_argument('--candidate',type=Path)
OPTIONS,remaining=parser.parse_known_args()
spec=importlib.util.spec_from_file_location('cad',ROOT/'scripts/cad-candidate.py');cad=importlib.util.module_from_spec(spec);spec.loader.exec_module(cad)
class CadBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='sso-cad-build-test-');cls.addClassCleanup(cls.tmp.cleanup)
        cls.root=Path(cls.tmp.name).resolve();cls.source=cls.root/'source';cad.prepare(OPTIONS.layerling,cls.source)
    def test_01_pin_and_original_backend_unchanged(self):
        cad.verify_source_tree(self.source,OPTIONS.layerling)
        self.assertEqual(cad.digest((self.source/'apps/web/public/store.php').read_bytes()),cad.pin()[0]['sha256'])
        self.assertFalse((self.source/'.env').exists())
    def test_02_change_outside_adapter_is_refused(self):
        file=self.source/'apps/web/src/lib/sharedProjectsEndpoint.ts';old=file.read_bytes()
        try:
            file.write_bytes(old+b'\n// changed\n')
            with self.assertRaises(ValueError):cad.verify_source_tree(self.source,OPTIONS.layerling)
        finally:file.write_bytes(old)
    def test_03_added_route_and_environment_refused(self):
        for file in [self.source/'apps/web/src/app/extra.ts',self.source/'apps/web/.env.local',self.source/'apps/web/next.config.js']:
            try:
                file.write_text('synthetic-only')
                with self.assertRaises(ValueError):cad.verify_source_tree(self.source,OPTIONS.layerling)
            finally:file.unlink()
    def test_04_forged_adaptation_report_does_not_override_pin(self):
        file=self.source/'apps/web/src/lib/offlineSupport.ts';old=file.read_bytes();marker=self.source/cad.SOURCE_MARKER;report=marker.read_bytes()
        try:
            file.write_bytes(old+b'\n// changed\n');metadata=json.loads(report)
            metadata['adapted']['apps/web/src/lib/offlineSupport.ts']=cad.digest(file.read_bytes());marker.write_text(json.dumps(metadata))
            cad.validate_source(self.source)
            with self.assertRaises(ValueError):cad.verify_source_tree(self.source,OPTIONS.layerling)
        finally:file.write_bytes(old);marker.write_bytes(report)
    def test_05_existing_source_never_overwritten(self):
        with self.assertRaises(ValueError):cad.prepare(OPTIONS.layerling,self.source)
        cad.verify_source_tree(self.source,OPTIONS.layerling)
    @unittest.skipUnless(OPTIONS.candidate,'Pass verified CAD candidate')
    def test_06_candidate_excludes_public_editor_html_php_and_offline(self):
        root=OPTIONS.candidate;manifest=json.loads((root/'manifest.json').read_text())
        self.assertEqual(manifest['kind'],'sso-layerling-cad-candidate')
        self.assertEqual(manifest['files'],{str(p.relative_to(root)):cad.digest(p.read_bytes())for p in root.rglob('*')if p.is_file()and p!=root/'manifest.json'})
        public=root/'public'
        for name in ['index.html','index.txt','sw.js','manifest.webmanifest','view.html','support.html']:self.assertFalse((public/name).exists())
        self.assertNotIn(b'/manifest.webmanifest', (root/'private/app/cad/index.html').read_bytes())
        occt = json.loads((root/'private/app/cad/build.json').read_text())['occtRuntime']
        self.assertIn('-sso-csp-', occt['version'])
        glue = (public/'occt'/occt['version']/'occt-wasm.js').read_bytes()
        self.assertEqual(cad.digest(glue), occt['sha256'])
        self.assertNotIn(b'new Function(', glue)
        for name, expected in cad.pin()[1]['manifoldRuntime']['files'].items():
            self.assertEqual(cad.digest((public/name).read_bytes()), expected)
        self.assertIn(b'Gateway', (root/'private/app/src/Gateway.php').read_bytes())
        self.assertNotEqual(cad.digest((public/'store.php').read_bytes()),cad.pin()[0]['sha256'])
        self.assertEqual({str(p.relative_to(public))for p in public.rglob('*.php')},{'index.php','_sso.php','store.php','session.php','owners.php','files.php','files/index.php','konto/index.php','cad.php','cad-session.php','mcp.php','vorlagen.php','auth/start.php','auth/callback.php','auth/logout.php'})
        self.assertFalse(any(p.name=='.env' for p in root.rglob('*')))
    def test_07_current_installer_refuses_candidate_even_with_commit(self):
        package=self.root/'unsupported';package.mkdir()
        (package/'manifest.json').write_text(json.dumps({'kind':'sso-layerling-cad-candidate','sourceCommit':'a'*40,'installedPrivate':str(self.root/'base/private'),'files':{}}))
        result=subprocess.run([OPTIONS.php,str(ROOT/'scripts/install-sso-test.php'),'--package='+str(package),'--base='+str(self.root/'base'),'--public='+str(self.root/'www'),'--local-test'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1);self.assertIn('Uncommitted or wrong-target package refused',result.stderr)
        self.assertFalse((self.root/'base').exists())
if __name__=='__main__':unittest.main(argv=[__file__]+remaining)
