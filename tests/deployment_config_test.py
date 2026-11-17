#!/usr/bin/env python3
"""Private deployment metadata is explicit; public examples cannot authorize a hosted package."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--layerling', type=Path, required=True)
parser.add_argument('--php', required=True)
options, remaining = parser.parse_known_args()
spec = importlib.util.spec_from_file_location('package', ROOT/'scripts/package-sso-test.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)

class DeploymentConfigTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='sso-deployment-config-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.config = self.root/'deployment.local.json'
        self.values = json.loads((ROOT/'config/oidc.example.json').read_text())
        self.values.update(clientId='synthetic-registered-client')
        self.values['groupBindings'].update(makerspace='synthetic-verified-maker', admins='synthetic-verified-admin')
        self.save()

    def save(self):
        self.config.write_text(json.dumps(self.values))
        self.config.chmod(0o600)

    def test_private_metadata_drives_storage_and_installer_target(self):
        output = package.package(self.root/'artifact', layerling=options.layerling, deployment_config_path=self.config)
        app = output/'private/app'
        self.assertEqual(json.loads((app/'storage.json').read_text())['groupIds'],
                         {'makerspace':'synthetic-verified-maker', 'admins':'synthetic-verified-admin'})
        self.assertEqual(json.loads((app/'deployment-target.json').read_text()), {'clientId':'synthetic-registered-client'})
        self.assertFalse(any(p.name in ['.env', 'deployment.local.json', 'entwicklung-intern.md'] for p in output.rglob('*')))
        manifest = json.loads((output/'manifest.json').read_text())
        self.assertIn('private/app/deployment-target.json', manifest['files'])

    def test_synthetic_defaults_have_no_registered_target(self):
        output = package.package(self.root/'artifact')
        self.assertEqual(json.loads((output/'private/app/deployment-target.json').read_text()), {'clientId':''})

    def test_private_addresses_work_through_packaged_installer(self):
        self.values.update(issuer='https://identity.example.invalid:8443', origin='https://design.example.invalid',
                           redirectUri='https://design.example.invalid/auth/callback.php')
        self.save()
        base, public = self.root/'base', self.root/'www'
        base.mkdir(); public.mkdir()
        env = base/'.env'
        env.write_text('SSO_LAYERLING_OIDC_CLIENT_ID=synthetic-registered-client\nSSO_LAYERLING_OIDC_CLIENT_SECRET=synthetic-secret-not-real\n')
        env.chmod(0o600)
        output = package.package(self.root/'artifact', str(base/'private'), options.layerling, str(public), deployment_config_path=self.config)
        manifest = json.loads((output/'manifest.json').read_text())
        manifest['sourceCommit'] = 'a'*40
        (output/'manifest.json').write_text(json.dumps(manifest))
        installer = output/'private/app/scripts/install-sso-test.php'
        result = subprocess.run([options.php, str(installer), '--package='+str(output), '--base='+str(base),
                                 '--public='+str(public), '--local-test'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        code = r"require $argv[1]; $p=\Sso\Layerling\Oidc\Profile::load(dirname($argv[2]).'/oidc-profile.json'); $c=new \Sso\Layerling\Oidc\Config('fixture',str_repeat('s',32),$p); echo json_encode([$p->issuer,$c->redirectUri,\Sso\Layerling\StorageConfig::load($argv[2])->values['origin']]);"
        result = subprocess.run([options.php, '-r', code, str(base/'private/app/vendor/autoload.php'),
                                 str(base/'private/app/storage.json')], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [self.values['issuer'], self.values['redirectUri'], self.values['origin']])

    def test_subject_binding_refuses_a_new_client_registration(self):
        self.values = json.loads((ROOT/'tests/oidc-alternate.json').read_text())
        base, public = self.root/'base', self.root/'www'
        base.mkdir()
        public.mkdir()
        env = base/'.env'

        def install(name, client):
            self.values['clientId'] = client
            self.save()
            env.write_text('SSO_LAYERLING_OIDC_CLIENT_ID=' + client +
                           '\nSSO_LAYERLING_OIDC_CLIENT_SECRET=synthetic-secret-not-real\n')
            env.chmod(0o600)
            artifact = package.package(self.root/name, str(base/'private'), options.layerling, str(public),
                                       deployment_config_path=self.config)
            manifest_file = artifact/'manifest.json'
            manifest = json.loads(manifest_file.read_text())
            manifest['sourceCommit'] = 'a'*40
            manifest_file.write_text(json.dumps(manifest))
            return subprocess.run([options.php, str(artifact/'private/app/scripts/install-sso-test.php'),
                                   '--package='+str(artifact), '--base='+str(base), '--public='+str(public),
                                   '--local-test'], capture_output=True, text=True)

        first = install('first', 'fixture-client-a')
        self.assertEqual(first.returncode, 0, first.stderr)
        metadata = base/'private/deployment.json'
        earlier = metadata.read_bytes()
        self.assertEqual(json.loads(earlier)['oidcIdentity'][-1], 'fixture-client-a')
        second = install('second', 'fixture-client-b')
        self.assertNotEqual(second.returncode, 0)
        self.assertIn('requires an explicit migration', second.stderr)
        self.assertEqual(metadata.read_bytes(), earlier)
        script = r"""$_SERVER=['HTTP_HOST'=>'workshop.example.invalid','HTTPS'=>'on','DOCUMENT_ROOT'=>$argv[1],'REQUEST_URI'=>'/','REQUEST_METHOD'=>'GET']; try {require $argv[1].'/index.php';} catch (\Sso\Layerling\Oidc\LoginFailed $error) {echo 'Client configuration rejected';}"""
        bootstrap = subprocess.run([options.php, '-r', script, str(public)], capture_output=True, text=True, check=True)
        self.assertEqual(bootstrap.stdout, 'Client configuration rejected')

    def test_invalid_provider_mappings_are_refused_before_output(self):
        fixture = json.loads((ROOT/'tests/oidc-alternate.json').read_text())
        for keys, bad_value in [
            (('endpoints', 'token'), '//other.example.invalid/token'),
            (('scopes',), ['profile']),
            (('templatePublisherRoleIds',), ['instructor', None]),
            (('claims', 'identity', 'claim'), 'aud'),
            (('claims', 'groups', 'id'), None),
            (('classPrefixes',), ['']),
        ]:
            with self.subTest(keys=keys):
                self.values = json.loads(json.dumps(fixture))
                target = self.values['provider']
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = bad_value
                self.save()
                with self.assertRaises(ValueError):
                    package.package(self.root/'refused', deployment_config_path=self.config)
                self.assertFalse((self.root/'refused').exists())

    def test_invalid_private_addresses_are_refused_before_output(self):
        for changes in [{'issuer':'http://identity.example.invalid'},
                        {'issuer':"https://identity.example.invalid';evil"},
                        {'issuer':'https://user:password@identity.example.invalid'},
                        {'origin':'https://design.example.invalid/path'},
                        {'origin':'https://design.example.invalid:99999'},
                        {'redirectUri':'https://other.example.invalid/auth/callback.php'}]:
            with self.subTest(changes=changes):
                original = self.values.copy()
                self.values.update(changes); self.save()
                with self.assertRaises(ValueError):
                    package.package(self.root/'refused', deployment_config_path=self.config)
                self.assertFalse((self.root/'refused').exists())
                self.values = original

    def test_examples_secrets_and_ambiguous_groups_are_refused_before_output(self):
        original = json.loads(json.dumps(self.values))
        changes = [
            {'clientId':''}, {'clientId':'test-client'}, {'clientSecret':'synthetic-secret-for-rejection'},
            {'groupBindings':{'makerspace':'maker-fixture','admins':'synthetic-admin'}},
            {'groupBindings':{'makerspace':'same','admins':'same'}},
        ]
        for change in changes:
            with self.subTest(change=list(change)):
                self.values = original | change
                self.save()
                with self.assertRaises(ValueError):
                    package.package(self.root/'refused', deployment_config_path=self.config)
                self.assertFalse((self.root/'refused').exists())

    def test_readable_or_symlinked_private_config_is_refused(self):
        self.config.chmod(0o644)
        with self.assertRaises(ValueError): package.deployment_config(self.config)
        self.config.chmod(0o600)
        link = self.root/'link.json'
        link.symlink_to(self.config)
        with self.assertRaises(ValueError): package.deployment_config(link)

    def test_hosted_cli_requires_explicit_private_config(self):
        result = subprocess.run(['python3', str(ROOT/'scripts/package-sso-test.py'), '--output', str(self.root/'refused')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--deployment-config', result.stderr)
        self.assertFalse((self.root/'refused').exists())

if __name__ == '__main__':
    unittest.main(argv=[__file__, *remaining], verbosity=2)
