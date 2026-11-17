#!/usr/bin/env python3
"""Build the hosted SSO validation portal. Never copies .env or user/runtime data."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INSTALLED_PRIVATE = '/home/repos/sso-layerling/private'

def https_origin(value):
    if not isinstance(value, str) or not re.fullmatch(r'https://[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]{1,5})?', value):
        raise ValueError('Deployment addresses must be HTTPS origins without credentials, paths or query strings')
    parsed = urlsplit(value)
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Invalid deployment port')
    return value

def deployment_config(path: Path | None = None):
    """Examples are synthetic; real deployment metadata must be supplied explicitly."""
    if path is not None and (path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077):
        raise ValueError('Private deployment configuration must be a regular file with mode 0600')
    values = json.loads((path or ROOT/'config/oidc.example.json').read_text())
    https_origin(values.get('origin'))
    https_origin(values.get('issuer'))
    if values.get('redirectUri') != values['origin'] + '/auth/callback.php':
        raise ValueError('Callback must match the configured application origin')
    if values.get('clientSecret'):
        raise ValueError('Keep secrets in the separate private .env, never in deployment JSON')
    if path is not None:
        if not isinstance(values.get('clientId'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', values['clientId']) or values['clientId'] == 'test-client':
            raise ValueError('Configure the registered client ID for deployment')
        groups = values.get('groupBindings', {})
        for key in ['makerspace', 'admins']:
            value = groups.get(key)
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) or value in ['maker-fixture', 'admin-fixture']:
                raise ValueError('Configure verified group IDs for deployment')
        if groups['makerspace'] == groups['admins']:
            raise ValueError('Ambiguous deployment groups')
    return values

def materialize_targets(app: Path, config):
    # Freeze validated private addresses into the package, never into repository files.
    targets = {'https://login.example.invalid': config['issuer'], 'https://cad.example.invalid': config['origin']}
    for directory in [app/'src', app/'scripts']:
        for file in directory.rglob('*.php'):
            text = file.read_text()
            text = re.sub(r'https://(?:login|cad)\.example\.invalid', lambda match: targets[match[0]], text)
            file.write_text(text)

def package(output: Path, installed_private: str = INSTALLED_PRIVATE, layerling: Path | None = None, installed_public: str = '/home/www/layerling', *, deployment_config_path: Path | None = None):
    config = deployment_config(deployment_config_path)
    if output.exists() or output.is_symlink():
        raise ValueError('Output must not exist')
    if not installed_private.startswith('/') or any(c not in '/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in installed_private):
        raise ValueError('Invalid private installation path')
    if not (ROOT / 'vendor/autoload.php').is_file():
        raise ValueError('Install the locked production dependency locally first')
    output = output.parent.resolve(strict=True) / output.name
    output.mkdir(mode=0o700)
    private, public = output/'private', output/'public'
    app = private/'app'
    app.mkdir(parents=True, mode=0o700)
    (app/'deployment-target.json').write_text(json.dumps({'clientId':config['clientId']})+'\n')
    public.mkdir(mode=0o700)
    for name in ['src', 'vendor']:
        source = ROOT/name
        if any(p.is_symlink() for p in source.rglob('*')):
            raise ValueError('Symlinks are not packaged')
        shutil.copytree(source, app/name, ignore=shutil.ignore_patterns('.env', '.env.*', '.DS_Store', '__pycache__', '*.pyc', '.git'))
    (app/'scripts').mkdir(mode=0o700)
    shutil.copyfile(ROOT/'scripts/install-sso-test.php', app/'scripts/install-sso-test.php')
    for name in ['composer.json', 'composer.lock']:
        shutil.copyfile(ROOT/name, app/name)
    shutil.copyfile(ROOT/'public/index.php', public/'index.php')
    shutil.copytree(ROOT/'public/auth', public/'auth')
    (public/'_sso.php').write_text("<?php\ndeclare(strict_types=1);\nini_set('display_errors', '0');\nreturn require '"+installed_private+"/app/src/Oidc/host-bootstrap.php';\n")
    (public/'.sso-layerling-sso-test').write_text('Managed Layerling test installation.\n')
    kind = 'sso-layerling-sso-test'
    if layerling is not None:
        kind = 'sso-layerling-storage-test'
        if not installed_public.startswith('/') or any(c not in '/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in installed_public):
            raise ValueError('Invalid public installation path')
        lock = json.loads((ROOT/'upstream.lock.json').read_text())
        if len(lock['commit']) != 40 or any(c not in 'abcdef0123456789' for c in lock['commit']) or lock['path'] != 'apps/web/public/store.php':
            raise ValueError('Invalid upstream pin')
        git_env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        upstream = subprocess.run(['git','--no-optional-locks','-C',str(layerling),'show',lock['commit']+':'+lock['path']],env=git_env,capture_output=True,check=True).stdout
        if hashlib.sha256(upstream).hexdigest() != lock['sha256']:
            raise ValueError('Upstream hash mismatch')
        (app/'upstream').mkdir(mode=0o700)
        (app/'upstream/store.php').write_bytes(upstream)
        shutil.copyfile(ROOT/'upstream.lock.json',app/'upstream.lock.json')
        example = config
        storage = {'mode':'sso-storage-test','enabled':True,'authorizationModel':'sso-last-login',
            'origin':example['origin'],'publicRoot':installed_public,
            'absoluteSeconds':140*60,'idleSeconds':70*60,
            'groupIds':{key:example['groupBindings'][key] for key in ['makerspace','admins']},
            'studentGroupIds':example['groupBindings']['students'],'studentRoleId':example['studentRoleId']}
        (app/'storage.json').write_text(json.dumps(storage,indent=2)+'\n')
        for name in ['files.php','files.js','files.css','vorlagen.js']:
            shutil.copyfile(ROOT/'public'/name,public/name)
        for name,method in [('store.php','store'),('session.php','session'),('owners.php','owners'),('vorlagen.php','templates')]:
            (public/name).write_text("<?php\ndeclare(strict_types=1);\nini_set('display_errors','0');\n(require '"+installed_private+"/app/src/storage-bootstrap.php')->"+method+"();\n")
    materialize_targets(app, config)
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    head = subprocess.run(['git','-C',str(ROOT),'rev-parse','--verify','HEAD'],capture_output=True,text=True,env=env)
    status = subprocess.run(['git','-C',str(ROOT),'status','--porcelain'],capture_output=True,text=True,check=True,env=env)
    manifest = {'kind':kind,'sourceCommit':head.stdout.strip() if head.returncode==0 and not status.stdout else None,
        'installedPrivate':installed_private, 'files':{str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(output.rglob('*')) if p.is_file()}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for p in output.rglob('*'):
        p.chmod(0o700 if p.is_dir() else 0o600)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--layerling',type=Path,help='Explicitly build the integrated SSO/file test using this fixed local Git source')
    parser.add_argument('--deployment-config', type=Path, required=True, help='Private deployment metadata; no secrets')
    args=parser.parse_args()
    try:
        output=package(args.output,layerling=args.layerling,deployment_config_path=args.deployment_config)
    except (OSError,ValueError,subprocess.CalledProcessError):
        parser.exit(1,'Packaging failed; existing installations/configuration not changed.\n')
    print(f'Test package: {output}. No .env or user data included; storage only when explicitly requested.')
