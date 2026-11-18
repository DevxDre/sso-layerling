#!/usr/bin/env python3
"""Exercise the real installer with a pinned CAD export and disposable hosting paths."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--php', required=True)
parser.add_argument('--layerling', type=Path, required=True)
parser.add_argument('--source', type=Path, required=True)
options, remaining = parser.parse_known_args()


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cad = load('cad_package', 'cad-candidate.py')
storage = load('storage_package', 'package-sso-test.py')


class CadInstallerTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='sso-cad-install-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        self.base = root / 'base'
        self.public = root / 'www'
        self.private = self.base / 'private'
        self.base.mkdir()
        self.public.mkdir()
        secret = self.base / '.env'
        secret.write_text('SSO_LAYERLING_OIDC_CLIENT_ID=test-client\nSSO_LAYERLING_OIDC_CLIENT_SECRET=synthetic-secret-not-real\n')
        secret.chmod(0o600)
        self.storage = storage.package(root / 'storage', str(self.private), options.layerling, str(self.public))
        self.cad = cad.package(options.source, options.layerling, root / 'cad', str(self.private), str(self.public))
        for package, kind, commit in [
            (self.storage, 'sso-layerling-storage-test', 'a' * 40),
            (self.cad, 'sso-layerling-cad-test', 'b' * 40),
        ]:
            manifest = self.metadata(package / 'manifest.json')
            manifest.update(kind=kind, sourceCommit=commit)
            (package / 'manifest.json').write_text(json.dumps(manifest))
        self.install_ok(self.storage)
        self.fixtures = {
            self.private / 'projects' / 'fixture.lyl': b'synthetic project',
            self.private / 'sessions' / ('sess_' + 'a'*64): b'synthetic session',
            self.private / 'principals.json': b'{}',
            self.private / 'permissions.json': b'{"version":1,"rules":[],"patterns":["makerspace^"]}',
            self.private / 'audit.jsonl': b'{"fixture":true}\n',
            self.public / '.well-known/acme-challenge/proof': b'acme proof',
            secret: secret.read_bytes(),
        }
        for path, contents in self.fixtures.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)

    @staticmethod
    def metadata(path):
        return json.loads(path.read_text())

    def install(self, package, *flags):
        return subprocess.run([options.php, str(ROOT / 'scripts/install-sso-test.php'),
            '--package=' + str(package), '--base=' + str(self.base),
            '--public=' + str(self.public), '--local-test', *flags],
            capture_output=True, text=True)

    def install_ok(self, package, *flags):
        result = self.install(package, *flags)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def assert_preserved(self):
        for path, value in self.fixtures.items():
            self.assertEqual(path.read_bytes(), value, path.name)

    def request(self, route):
        script = """$_SERVER=['HTTP_HOST'=>'cad.example.invalid','HTTPS'=>'on',
            'DOCUMENT_ROOT'=>$argv[1],'REQUEST_URI'=>$argv[2],'REQUEST_METHOD'=>'GET'];
            register_shutdown_function(static fn()=>fwrite(STDERR,(string)http_response_code()));
            require $argv[1].$argv[2];"""
        return subprocess.run([options.php, '-r', script, str(self.public), route],
            capture_output=True, text=True)

    def test_cad_install_and_exact_downgrade(self):
        before = cad.hashes(self.public)
        self.assertNotEqual(self.install(self.cad).returncode, 0)
        self.assertEqual(cad.hashes(self.public), before)
        self.install_ok(self.cad, '--cad-test')
        deployed = self.metadata(self.private / 'deployment.json')
        self.assertEqual(deployed['kind'], 'sso-layerling-cad-test')
        for route, status in [('/cad.php', '303'), ('/cad-session.php', '401'), ('/store.php', '401')]:
            self.assertEqual(self.request(route).stderr, status)
        self.assertTrue((self.public / 'manifold.wasm').is_file())
        for path in ['index.html', 'sw.js', 'private', 'index.txt']:
            self.assertFalse((self.public / path).exists())
        self.assert_preserved()
        self.install_ok(self.storage)
        self.assertEqual(cad.hashes(self.public), before)
        self.assertFalse((self.private / 'app/cad').exists())
        self.assertEqual(self.metadata(self.private / 'deployment.json')['sourceCommit'], 'a' * 40)
        self.assert_preserved()

    def test_forged_static_report_cannot_publish_executable(self):
        report = self.cad / 'private/app/cad/build.json'
        extra = self.cad / 'public/assets/extra.php.html'
        extra.write_text('<?php echo "fixture";')
        value = self.metadata(report)
        value['files']['assets/extra.php.html'] = hashlib.sha256(extra.read_bytes()).hexdigest()
        report.write_text(json.dumps(value))
        manifest = self.metadata(self.cad / 'manifest.json')
        for file in (report, extra):
            manifest['files'][str(file.relative_to(self.cad))] = hashlib.sha256(file.read_bytes()).hexdigest()
        (self.cad / 'manifest.json').write_text(json.dumps(manifest))
        before = cad.hashes(self.public)
        result = self.install(self.cad, '--cad-test')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected CAD asset', result.stderr)
        self.assertEqual(cad.hashes(self.public), before)
        self.assert_preserved()

    def test_update_and_rollback_across_new_routes(self):
        previous = self.cad.with_name('previous-cad')
        shutil.copytree(self.cad, previous)
        manifest = self.metadata(previous / 'manifest.json')
        for path in ['public/vorlagen.php', 'public/vorlagen.js', 'private/app/src/TemplateCatalog.php',
                     'public/konto/index.php', 'public/files/index.php', 'public/rechte.php',
                     'private/app/src/PermissionRules.php', 'private/app/src/Oidc/permissions-page.php']:
            (previous / path).unlink()
            del manifest['files'][path]
        bundle_path = 'private/app/cad/manifest.json'
        bundle = self.metadata(previous / bundle_path)
        del bundle['entryRoutes']
        (previous / bundle_path).write_text(json.dumps(bundle))
        manifest['files'][bundle_path] = hashlib.sha256((previous / bundle_path).read_bytes()).hexdigest()
        manifest['sourceCommit'] = 'c' * 40
        (previous / 'manifest.json').write_text(json.dumps(manifest))
        self.install_ok(previous, '--cad-test')
        self.install_ok(self.cad, '--cad-test')
        self.assertEqual(self.request('/vorlagen.php').stderr, '401')
        self.assertEqual(self.request('/rechte.php').stderr, '401')
        self.assertTrue((self.public / 'konto/index.php').is_file())
        self.assertTrue((self.public / 'files/index.php').is_file())
        snapshot = self.private / 'templates' / 'fixture'
        snapshot.write_bytes(b'private template data')
        self.install_ok(previous, '--cad-test')
        self.assertFalse((self.public / 'vorlagen.php').exists())
        self.assertFalse((self.public / 'rechte.php').exists())
        self.assertFalse((self.public / 'vorlagen.js').exists())
        self.assertFalse((self.public / 'konto/index.php').exists())
        self.assertFalse((self.public / 'files/index.php').exists())
        self.assertEqual(snapshot.read_bytes(), b'private template data')
        self.assert_preserved()

    def test_partial_activation_restores_previous_files_and_app(self):
        (self.public / 'cad.php').mkdir()
        before = cad.hashes(self.public)
        app = cad.hashes(self.private / 'app')
        deployment = (self.private / 'deployment.json').read_bytes()
        result = self.install(self.cad, '--cad-test')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Cannot activate file', result.stderr)
        self.assertEqual(cad.hashes(self.public), before)
        self.assertEqual(cad.hashes(self.private / 'app'), app)
        self.assertEqual((self.private / 'deployment.json').read_bytes(), deployment)
        self.assert_preserved()


if __name__ == '__main__':
    unittest.main(argv=[__file__, *remaining], verbosity=2)
