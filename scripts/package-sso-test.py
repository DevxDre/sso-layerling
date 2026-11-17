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

ROLE_ID = r'[A-Za-z0-9_.:-]{1,100}'
GROUP_ID = r'[A-Za-z0-9_-]{1,128}'
CLAIM_KEY = r'[A-Za-z0-9_.:/-]{1,200}'
URL_PATH = r'/(?!/)[A-Za-z0-9._~/-]{0,1023}'


def matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def identifiers(values, pattern, limit):
    return (isinstance(values, list) and len(values) <= limit
            and all(matches(value, pattern) for value in values) and len(set(values)) == len(values))


def provider_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {
        'name', 'endpoints', 'scopes', 'claims', 'classPrefixes', 'templatePublisherRoleIds',
    }:
        raise ValueError('Invalid provider profile')
    endpoints = profile['endpoints']
    if (not isinstance(endpoints, dict) or set(endpoints) != {'authorize', 'token', 'userinfo', 'jwks'}
            or not all(matches(path, URL_PATH) for path in endpoints.values())):
        raise ValueError('Invalid provider endpoint paths')
    if (not matches(profile['name'], r'[^\x00-\x1f\x7f]{1,80}') or not profile['name'].strip()
            or not identifiers(profile['scopes'], r'[A-Za-z0-9_.:/-]{1,128}', 32)
            or 'openid' not in profile['scopes']
            or not identifiers(profile['classPrefixes'], r'[^\x00-\x20\x7f]{1,80}', 16)
            or not identifiers(profile['templatePublisherRoleIds'], ROLE_ID, 100)):
        raise ValueError('Invalid provider settings')
    claims = profile['claims']
    if not isinstance(claims, dict) or set(claims) != {'identity', 'name', 'username', 'roles', 'groups'}:
        raise ValueError('Invalid claim mappings')
    identity = claims['identity']
    if (not isinstance(identity, dict) or set(identity) != {'claim', 'format'}
            or not matches(identity['claim'], CLAIM_KEY) or identity['format'] not in ('uuid', 'opaque')
            or (identity['claim'] == 'sub' and identity['format'] != 'opaque')
            or not all(matches(claims[key], CLAIM_KEY) for key in ['name', 'username'])):
        raise ValueError('Invalid identity or profile claims')
    for key in ['roles', 'groups']:
        mapping = claims[key]
        formats = ('strings', 'objects', 'map') if key == 'groups' else ('strings', 'objects')
        if (not isinstance(mapping, dict) or mapping.get('format') not in formats
                or not matches(mapping.get('claim'), CLAIM_KEY)):
            raise ValueError('Invalid role or group claim mapping')
        required = {'claim', 'format'} if mapping['format'] == 'strings' else {'claim', 'format', 'id'}
        optional = {'label', 'account'} if key == 'groups' and mapping['format'] != 'strings' else set()
        if not required <= set(mapping) <= required | optional or any(
            not matches(mapping[field], CLAIM_KEY) for field in set(mapping) - {'format'}
        ):
            raise ValueError('Invalid claim fields')
    security_claims = [claims[key]['claim'] for key in ['identity', 'roles', 'groups']]
    if (len(set(security_claims)) != len(security_claims)
            or any(claim in {'iss', 'aud', 'nonce', 'exp', 'iat', 'nbf', 'azp', 'at_hash', 'sub'}
                   for claim in security_claims[1:])
            or security_claims[0] in {'iss', 'aud', 'nonce', 'exp', 'iat', 'nbf', 'azp', 'at_hash'}):
        raise ValueError('Ambiguous security claim mappings')
    return profile


def authorization_mapping(provider, default):
    def relevant(profile):
        return [{key: value for key, value in profile['claims'][claim].items() if key not in {'label', 'account'}}
                for claim in ['roles', 'groups']]

    mapping = relevant(provider)
    if mapping == relevant(default):
        return None
    return hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def deployment_config(path: Path | None = None):
    """Examples are synthetic; real deployment metadata must be supplied explicitly."""
    if path is not None and (path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077):
        raise ValueError('Private deployment configuration must be a regular file with mode 0600')
    values = json.loads((path or ROOT/'config/oidc.example.json').read_text())
    if not isinstance(values, dict):
        raise ValueError('Deployment configuration must be an object')
    https_origin(values.get('origin'))
    issuer = values.get('issuer')
    if not isinstance(issuer, str) or not issuer.startswith('https://'):
        raise ValueError('Invalid issuer')
    authority, delimiter, path_suffix = issuer[len('https://'):].partition('/')
    https_origin('https://' + authority)
    if delimiter and not matches('/' + path_suffix, URL_PATH):
        raise ValueError('Invalid issuer path')
    if values.get('redirectUri') != values['origin'] + '/auth/callback.php':
        raise ValueError('Callback must match the configured application origin')
    if values.get('clientSecret'):
        raise ValueError('Keep secrets in the separate private .env, never in deployment JSON')
    default = json.loads((ROOT/'config/oidc-iserv.json').read_text())
    provider = provider_profile(values.get('provider', default))
    scopes = values.get('scopes')
    if 'provider' not in values and scopes is not None:
        # Older IServ deployments carried a top-level scope list.
        provider = provider_profile({**provider, 'scopes': scopes})
    if 'provider' not in values and values.get('identity', {'binding': 'issuer-and-iserv-uuid'}) != {'binding': 'issuer-and-iserv-uuid'}:
        raise ValueError('Use provider.claims.identity to configure the identity binding')
    values['provider'] = provider
    values['authorizationMapping'] = authorization_mapping(provider, default)
    groups = values.get('groupBindings')
    if (not isinstance(groups, dict) or not all(matches(groups.get(key), GROUP_ID) for key in ['makerspace', 'admins'])
            or groups['makerspace'] == groups['admins'] or not identifiers(groups.get('students'), GROUP_ID, 128)):
        raise ValueError('Configure distinct, verified group IDs and a student group list')
    if ('studentRoleId' not in values
            or (values['studentRoleId'] is not None and not matches(values['studentRoleId'], ROLE_ID))):
        raise ValueError('Invalid student role binding')
    values.setdefault('diagnosticGroupIds', [groups['makerspace'], groups['admins']])
    if not identifiers(values['diagnosticGroupIds'], GROUP_ID, 128):
        raise ValueError('Invalid diagnostic group IDs')
    if path is not None:
        if not matches(values.get('clientId'), r'[A-Za-z0-9_-]{1,128}') or values['clientId'] == 'test-client':
            raise ValueError('Configure the registered client ID for deployment')
        for key in ['makerspace', 'admins']:
            if groups[key] in ['maker-fixture', 'admin-fixture']:
                raise ValueError('Configure verified group IDs for deployment')
    return values


def metadata_json(values):
    text = json.dumps(values, ensure_ascii=False, separators=(',', ':')) + '\n'
    if len(text.encode('utf-8')) > 16384:
        raise ValueError('Packaged metadata exceeds the runtime size limit')
    return text


def package(output: Path, installed_private: str = INSTALLED_PRIVATE, layerling: Path | None = None, installed_public: str = '/home/www/layerling', *, deployment_config_path: Path | None = None):
    config = deployment_config(deployment_config_path)
    groups = config['groupBindings']
    profile = {key: config[key] for key in ['issuer', 'origin', 'provider', 'diagnosticGroupIds', 'studentRoleId']}
    profile_json = metadata_json({**profile, 'studentGroupIds': groups['students']})
    storage_json = None
    if layerling is not None:
        storage_json = metadata_json({
            'mode': 'sso-storage-test', 'enabled': True, 'authorizationModel': 'sso-last-login',
            'origin': config['origin'], 'publicRoot': installed_public,
            'absoluteSeconds': 140 * 60, 'idleSeconds': 70 * 60,
            'groupIds': {key: groups[key] for key in ['makerspace', 'admins']},
            'studentGroupIds': groups['students'], 'studentRoleId': config['studentRoleId'],
            'templatePublisherRoleIds': config['provider']['templatePublisherRoleIds'],
            'authorizationMapping': config['authorizationMapping'],
        })
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
    (app/'config').mkdir(mode=0o700)
    shutil.copyfile(ROOT/'config/oidc-iserv.json', app/'config/oidc-iserv.json')
    (app/'oidc-profile.json').write_text(profile_json, encoding='utf-8')
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
        (app/'storage.json').write_text(storage_json, encoding='utf-8')
        for name in ['files.php','files.js','files.css','vorlagen.js']:
            shutil.copyfile(ROOT/'public'/name,public/name)
        for name,method in [('store.php','store'),('session.php','session'),('owners.php','owners'),('vorlagen.php','templates')]:
            (public/name).write_text("<?php\ndeclare(strict_types=1);\nini_set('display_errors','0');\n(require '"+installed_private+"/app/src/storage-bootstrap.php')->"+method+"();\n")
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
