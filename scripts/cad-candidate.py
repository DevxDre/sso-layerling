#!/usr/bin/env python3
"""Prepare/build/package an isolated CAD candidate. No deployment."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MARKER = '.sso-cad-source.json'
BUILD_MARKER = '.sso-cad-build.json'
OCCT_ADAPTER = ROOT/'cad/occt-no-eval.js'
PATCHES = {
    'apps/web/src/components/LayerlingEditor.tsx': [
        ('    if (!localDevelopment && process.env.NEXT_PUBLIC_STATIC_EXPORT === "true") {',
         '    const ssoMcpTest = document.documentElement.dataset.ssoMcpTest === "true";\n'
         '    if (!localDevelopment && process.env.NEXT_PUBLIC_STATIC_EXPORT === "true" && !ssoMcpTest) {', 1),
        ('            if (retry) {\n              pollRetryTimer',
         '            if (retry || ssoMcpTest) {\n              pollRetryTimer', 1),
    ],
    'apps/web/src/app/layout.tsx': [
        ('  manifest: "/manifest.webmanifest",\n', '', 1),
    ],
    'apps/web/src/components/workplane/MyShapesSection.tsx': [
        ('title={t("common.delete")}',
         'title={t("common.delete")} data-sso-delete', 1),
        ('title={t("myShapes.deleteFolder")}',
         'title={t("myShapes.deleteFolder")} data-sso-delete', 1),
    ],
    'apps/web/src/lib/customShapesServer.ts': [
        ('/** There is no renaming a file in the store, so it is a copy under the new name, then away with the old one. */',
         '/** Use the PHP store rename with its revision check. */', 1),
        ('query(shape.folder, shape.fileName, { copyTo: target })',
         'query(shape.folder, shape.fileName, { renameFileTo: target })', 1),
        ('  await deleteServerCustomShape(shape);\n',
         '', 1),
    ],
    'apps/web/src/lib/useAppUpdate.ts': [
        ('checkAppUpdate(currentVersion)', 'Promise.resolve<AppUpdateInfo | null>(null) // SSO: reviewed releases only', 1),
    ],
    'apps/web/src/lib/useWhatsNew.ts': [
        ('export function useWhatsNew(current: string) {',
         'export function useWhatsNew(current: string, showOnLoad = true) {', 1),
        ('    const seen = lastSeenVersion(readLastSeen(), hasStoredDesigns());',
         '    if (!showOnLoad) return;\n    const seen = lastSeenVersion(readLastSeen(), hasStoredDesigns());', 1),
        ('    else rememberVersion(current);\n  }, [current]);',
         '    else rememberVersion(current);\n  }, [current, showOnLoad]);', 1),
    ],
    'apps/web/src/lib/offlineSupport.ts': [
        ('export const BUILD_HAS_SERVICE_WORKER = process.env.NEXT_PUBLIC_STATIC_EXPORT === "true";',
         'export const BUILD_HAS_SERVICE_WORKER = false; // SSO: online-only', 1),
    ],
    'apps/web/src/lib/editorMeshCore.ts': [
        ('new URL("manifold.js", assetBase)', 'new URL("manifold.js?v=sso-3.5.5", assetBase)', 1),
        ('new URL("manifold.wasm", assetBase)', 'new URL("manifold.wasm?v=sso-3.5.5", assetBase)', 1),
    ],
    'apps/web/src/app/page.tsx': [
        ('import { DashboardWelcome, useWelcomeHidden } from "@/components/DashboardWelcome";\n',
         '', 1),
        ('import { useOfflineAvailable } from "@/lib/offlineSupport";\n', '', 1),
        ('  const offlineOk = useOfflineAvailable();\n', '', 1),
        ('  const whatsNew = useWhatsNew(LYL_CREATED_WITH_VERSION);',
         '  const whatsNew = useWhatsNew(LYL_CREATED_WITH_VERSION, false); // SSO: open only from the footer', 1),
        ('  const welcome = useWelcomeHidden();\n'
         '  // Brought back from the footer: open, and scrolled into view.\n'
         '  const [welcomeReopened, setWelcomeReopened] = useState(false);\n'
         '  const showWelcome = () => {\n'
         '    welcome.show();\n'
         '    setWelcomeReopened(true);\n'
         '    window.requestAnimationFrame(() => document.getElementById("welcome")?.scrollIntoView({ behavior: "smooth", block: "start" }));\n'
         '  };\n\n', '', 1),
        ('          {welcome.hidden === false && !simpleMode ? (\n'
         '            <DashboardWelcome open={(!hasProjects && !sharedTotal) || welcomeReopened} offline={offlineOk} onHide={welcome.hide} />\n'
         '          ) : null}\n', '', 1),
        (' onShowWelcome={welcome.hidden && !simpleMode ? showWelcome : undefined}', '', 1),
        ('const PROJECTS_STORAGE_KEY',
         '// Capture the selected owner when this document starts.\nconst SSO_CAD_OWNER = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("owner");\n\nfunction ssoCadUrl(projectId?: string | null) {\n  const params = new URLSearchParams();\n  if (SSO_CAD_OWNER) params.set("owner", SSO_CAD_OWNER);\n  if (projectId !== undefined) params.set("editor", "1");\n  if (projectId) params.set("project", projectId);\n  const query = params.toString();\n  return query ? `/cad.php?${query}` : "/cad.php";\n}\n\nconst PROJECTS_STORAGE_KEY', 1),
        ('    createAndOpenProject();\n  };\n\n  const openDashboard',
         '    void createNewDesign();\n  };\n\n  const openDashboard', 1),
        ('      setDashboardNotice(error instanceof Error ? localizedError(error.message) : t("notice.saveSharedFailed"));\n    }\n    setProjects((current) => [{ ...project, sharedProject: binding }, ...current]);',
         '      setDashboardNotice(error instanceof Error ? localizedError(error.message) : t("notice.saveSharedFailed"));\n      return; // SSO: do not open an unsaved server project.\n    }\n    setProjects((current) => [{ ...project, sharedProject: binding }, ...current]);', 1),
        ('    } else {\n      serverAnswer.defaults();',
         '    } else {\n      serverNewDesignsRef.current = "always";\n      setServerNewDesigns("always");\n      serverAnswer.defaults();', 1),
        ('window.history.replaceState(null, "", "/");', 'window.history.replaceState(null, "", ssoCadUrl());', 5),
        ('const nextUrl = projectId ? `/?editor=1&project=${encodeURIComponent(projectId)}` : "/?editor=1";',
         'const nextUrl = ssoCadUrl(projectId);', 1),
        ('type SharedSearchResult = {\n  query: string;',
         'type SharedSearchResult = {\n  query: string;\n  failed?: boolean;', 1),
        ('          const payload = await response.json() as { projects?: SharedProject[]; folders?: SharedFolder[]; truncated?: boolean };',
         '          if (!response.ok) throw new Error("Server search failed");\n'
         '          const payload = await response.json() as { projects?: SharedProject[]; folders?: SharedFolder[]; truncated?: boolean };\n'
         '          if (!Array.isArray(payload.projects) || !Array.isArray(payload.folders)) throw new Error("Invalid search response");', 1),
        ('          // Eine Suche, die nicht durchkommt, ist keine Meldung wert - die\n'
         '          // Liste bleibt leer und die Kurzmeldung dem Speichern vorbehalten.\n'
         '          if (!controller.signal.aborted) setSharedSearch({ query: term, projects: [], folders: [], truncated: false });',
         '          if (!controller.signal.aborted) setSharedSearch({ query: term, failed: true, projects: [], folders: [], truncated: false });', 1),
        ('const searchResults = sharedProjectsEnabled && searchTerm ? sharedSearch : null;',
         'const searchResults = sharedProjectsEnabled && searchTerm && sharedSearch?.query === searchTerm ? sharedSearch : null;', 1),
        ('const shownSharedProjects = searchResults ? searchResults.projects : sharedProjects;',
         'const shownSharedProjects = searchTerm ? searchResults?.projects ?? [] : sharedProjects;', 1),
        ('...(searchResults ? searchResults.folders : sharedFolders)',
         '...(searchTerm ? searchResults?.folders ?? [] : sharedFolders)', 1),
        ('    dropTarget: dropFolderPath === "server",\n    dropProps: {',
         '    dropTarget: dropFolderPath === "server",\n    dropProps: {\n      ...{ "data-sso-server-tab": "" },', 1),
        ('<input value={query} onChange={(event) => onQueryChange(event.currentTarget.value)}',
         '<input data-sso-design-search={sharedProjectsEnabled ? "" : undefined} value={query} onChange={(event) => onQueryChange(event.currentTarget.value)}', 1),
        ('                <div className="project-empty">\n'
         '                  <strong>{searchTerm\n'
         '                    ? (sharedSearchLoading || !searchResults ? t("shared.loadingTitle") : t("shared.searchEmptyTitle"))\n'
         '                    : (sharedProjectsLoading ? t("shared.loadingTitle") : t("shared.emptyTitle"))}</strong>\n'
         '                  <span>{searchTerm && searchResults ? t("shared.searchEmptyHint") : t("shared.emptyHint")}</span>',
         '                <div className="project-empty" role="status">\n'
         '                  {searchTerm ? (\n'
         '                    <strong>{sharedSearchLoading || !searchResults ? t("shared.loadingTitle")\n'
         '                      : searchResults.failed ? t("notice.sharedLoadFailed")\n'
         '                      : searchResults.truncated ? t("shared.searchTruncated")\n'
         '                      : t("shared.searchEmptyTitle")}</strong>\n'
         '                  ) : (\n'
         '                    <strong>{sharedProjectsLoading ? t("shared.loadingTitle") : t("shared.emptyTitle")}</strong>\n'
         '                  )}\n'
         '                  {searchTerm ? (searchResults && !searchResults.failed && !searchResults.truncated && <span>{t("shared.searchEmptyHint")}</span>)\n'
         '                    : <span>{t("shared.emptyHint")}</span>}', 1),
    ],
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def pin(layerling_commit=None):
    upstream = json.loads((ROOT/'upstream.lock.json').read_text())
    adapter = json.loads((ROOT/'config/cad-adapter.lock.json').read_text())
    if upstream['commit'] != adapter['commit']:
        raise ValueError('CAD adapter has not been reviewed for this upstream commit')
    if layerling_commit is not None:
        if not re.fullmatch(r'[a-f0-9]{40}', layerling_commit):
            raise ValueError('Layerling commit must be a full Git object ID')
        upstream['commit'] = layerling_commit
    return upstream, adapter

def modified(path, data):
    text = data.decode()
    for before, after, count in PATCHES[path]:
        if text.count(before) != count:
            raise ValueError('CAD source pattern mismatch: '+path)
        text = text.replace(before, after)
    return text.encode()

def verify_preimages(archive, upstream, adapter):
    for path, expected in adapter['preimages'].items():
        if digest(archive.extractfile(path).read()) != expected:
            raise ValueError('Unreviewed source: '+path)
    if digest(archive.extractfile(upstream['path']).read()) != upstream['sha256']:
        raise ValueError('Upstream store mismatch')


def source_archive(layerling, commit):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    upstream_git = ['git', '-C', str(layerling)]
    baseline = pin()[0]['commit']
    if commit != baseline:
        ancestry = subprocess.run([*upstream_git, 'merge-base', '--is-ancestor', baseline, commit], env=env)
        if ancestry.returncode != 0:
            raise ValueError('Layerling update must descend from the reviewed pin')

        def dependency_lock(revision):
            lock = json.loads(subprocess.check_output(
                [*upstream_git, 'show', revision+':package-lock.json'], env=env))
            # These two fields identify Layerling itself, rather than its dependencies.
            lock.pop('version', None)
            lock['packages'][''].pop('version', None)
            return lock

        if dependency_lock(commit) != dependency_lock(baseline):
            raise ValueError('Layerling dependencies changed and require review')
    return subprocess.check_output([*upstream_git, 'archive', '--format=tar', commit], env=env)


def prepare(layerling, output, *, layerling_commit=None):
    upstream, adapter = pin(layerling_commit)
    if output.exists() or output.is_symlink():
        raise ValueError('Output must not exist')
    archive = source_archive(layerling, upstream['commit'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        verify_preimages(source, upstream, adapter)
        output.mkdir(mode=0o700)
        source.extractall(output, filter='data')
    transformed = {}
    for path in PATCHES:
        file = output/path
        file.write_bytes(modified(path, file.read_bytes()))
        transformed[path] = digest(file.read_bytes())
    metadata = {'kind':'sso-layerling-cad-source-v1', 'commit':upstream['commit'],
        'archiveSha256':digest(archive), 'packageLockSha256':digest((output/'package-lock.json').read_bytes()), 'adapted':transformed}
    (output/SOURCE_MARKER).write_text(json.dumps(metadata, indent=2)+'\n')
    return metadata

def validate_source(source, *, layerling_commit=None):
    upstream, _ = pin(layerling_commit)
    metadata = json.loads((source/SOURCE_MARKER).read_text())
    if metadata['commit'] != upstream['commit'] or metadata['kind'] != 'sso-layerling-cad-source-v1':
        raise ValueError('Wrong source identity')
    if metadata['packageLockSha256'] != digest((source/'package-lock.json').read_bytes()):
        raise ValueError('Dependency lock changed')
    for path in PATCHES:
        if metadata['adapted'][path] != digest((source/path).read_bytes()):
            raise ValueError('Adapted source changed')
    return metadata

def verify_source_tree(source, layerling, *, layerling_commit=None):
    upstream, adapter = pin(layerling_commit)
    archive = source_archive(layerling, upstream['commit'])
    if digest(archive) != json.loads((source/SOURCE_MARKER).read_text())['archiveSha256']:
        raise ValueError('Source archive identity changed')
    for base in [source, source/'apps/web']:
        if any(p.name != '.env.example' for p in base.glob('.env*')):
            raise ValueError('Local environment files must not enter CAD builds')
    with tarfile.open(fileobj=io.BytesIO(archive)) as original:
        verify_preimages(original, upstream, adapter)
        members = {item.name for item in original if item.isfile()}
        for directory, allowed in [(source, {'node_modules', SOURCE_MARKER, BUILD_MARKER}),
                (source/'apps/web', {'.next', '.next-export', 'next-env.d.ts', 'tsconfig.tsbuildinfo'})]:
            relative = str(directory.relative_to(source))
            start = '' if relative == '.' else relative+'/'
            expected = {name[len(start):].split('/')[0] for name in members if name.startswith(start)}
            for path in directory.iterdir():
                if path.is_symlink() or path.name not in expected | allowed:
                    raise ValueError('Unexpected build input: '+str(path.relative_to(source)))
        for directory in [source/'apps/web/src', source/'scripts']:
            for path in directory.rglob('*'):
                if path.is_symlink() or (path.is_file() and str(path.relative_to(source)) not in members):
                    raise ValueError('Unreviewed source added')
        for item in original:
            if item.issym() or item.islnk(): raise ValueError('Source symlink refused')
            if not item.isfile(): continue
            data = original.extractfile(item).read()
            if item.name in PATCHES: data = modified(item.name, data)
            path = source/item.name
            if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                raise ValueError('Unexpected source change: '+item.name)


def adapt_occt_runtime(source):
    _, adapter = pin()
    expected = adapter['occtRuntime']
    package = source/'node_modules/occt-wasm'
    metadata = package/'package.json'
    package_data = json.loads(metadata.read_text())
    version = package_data['version']
    glue = package/'dist/occt-wasm.js'
    original = glue.read_bytes()
    if version != expected['version'] or digest(original) != expected['sha256']:
        raise ValueError('Unreviewed OCCT JavaScript runtime')
    replacement = OCCT_ADAPTER.read_bytes()
    patched = original
    for start, end, code in [
        (b'function createJsInvoker(', b'var __embind_register_class_constructor=', replacement),
        (b'var __emval_create_invoker=', b'function __emval_get_global(', b'var __emval_create_invoker=createEmvalInvoker;'),
    ]:
        if patched.count(start) != 1 or patched.count(end) != 1:
            raise ValueError('OCCT invoker boundaries changed')
        begin = patched.index(start)
        finish = patched.index(end, begin)
        patched = patched[:begin] + code + patched[finish:]
    if b'new Function(' in patched:
        raise ValueError('Dynamic JavaScript compilation remains in OCCT')
    glue.write_bytes(patched)

    # The upstream copier and Next config both use this version as the URL component.
    # A new URL prevents browsers from reusing the previously served JavaScript glue.
    runtime_version = version + '-sso-csp-' + digest(replacement)[:12]
    package_data['version'] = runtime_version
    metadata.write_text(json.dumps(package_data, indent=2)+'\n')
    return {'version':runtime_version, 'sha256':digest(patched), 'adapterSha256':digest(replacement)}


def build(source, layerling, *, layerling_commit=None):
    metadata = validate_source(source, layerling_commit=layerling_commit)
    verify_source_tree(source, layerling, layerling_commit=layerling_commit)
    env = {k:v for k,v in os.environ.items() if k in ['PATH','HOME','TMPDIR','LANG','LC_ALL','SHELL']}
    env.update({'NEXT_TELEMETRY_DISABLED':'1', 'LAYERLING_BUILD_CPUS':'2',
        'NEXT_PUBLIC_SUPPORT_HINT':'off', 'NEXT_PUBLIC_ANNOUNCEMENTS':'off'})
    subprocess.run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=source, env=env, check=True)
    occt = adapt_occt_runtime(source)
    subprocess.run(['npm', 'run', 'export'], cwd=source, env=env, check=True)
    validate_source(source, layerling_commit=layerling_commit)
    verify_source_tree(source, layerling, layerling_commit=layerling_commit)
    export = source/'apps/web/.next-export'
    _, adapter = pin()
    manifold = adapter['manifoldRuntime']
    runtime = source/'node_modules/manifold-3d'
    if json.loads((runtime/'package.json').read_text())['version'] != manifold['version']:
        raise ValueError('Unreviewed Manifold version')
    for name, expected in manifold['files'].items():
        data = (runtime/name).read_bytes()
        if digest(data) != expected:
            raise ValueError('Unreviewed Manifold asset: '+name)
        (export/name).write_bytes(data)
    files = hashes(export)
    if files.get(f"occt/{occt['version']}/occt-wasm.js") != occt['sha256']:
        raise ValueError('Adapted OCCT runtime missing from export')
    for name in ['index.html','store.php','_next']:
        if not (export/name).exists():
            raise ValueError('Incomplete export')
    metadata = {'source':metadata, 'node':subprocess.check_output(['node','--version'], text=True).strip(),
        'npm':subprocess.check_output(['npm','--version'], text=True).strip(), 'supportHint':'off', 'occtRuntime':occt, 'files':files}
    (source/BUILD_MARKER).write_text(json.dumps(metadata, indent=2)+'\n')
    return metadata

def hashes(directory):
    result = {}
    for file in sorted(directory.rglob('*')):
        if file.is_symlink():
            raise ValueError('Symlink refused')
        if file.is_file(): result[str(file.relative_to(directory))] = digest(file.read_bytes())
    return result

def package(source, layerling, output, installed_private=None, installed_public='/home/www/layerling', *, hosted_test=False, deployment_config_path=None, layerling_commit=None):
    if hosted_test and deployment_config_path is None:
        raise ValueError('Hosted CAD test packaging requires private deployment configuration')
    metadata = validate_source(source, layerling_commit=layerling_commit)
    verify_source_tree(source, layerling, layerling_commit=layerling_commit)
    report = json.loads((source/BUILD_MARKER).read_text())
    export = source/'apps/web/.next-export'
    if report['source'] != metadata or report.get('supportHint') != 'off' or report['files'] != hashes(export):
        raise ValueError('Export changed after verified build')
    occt = report.get('occtRuntime', {})
    if (occt.get('adapterSha256') != digest(OCCT_ADAPTER.read_bytes())
        or report['files'].get(f"occt/{occt['version']}/occt-wasm.js") != occt['sha256']):
        raise ValueError('Export does not contain the current OCCT adapter')
    upstream, adapter = pin(layerling_commit)
    if any(report['files'].get(name) != expected for name, expected in adapter['manifoldRuntime']['files'].items()):
        raise ValueError('Export does not contain the reviewed Manifold runtime')
    if digest((export/'store.php').read_bytes()) != upstream['sha256']:
        raise ValueError('Unexpected upstream backend')
    spec = importlib.util.spec_from_file_location('sso_package', ROOT/'scripts/package-sso-test.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    private = installed_private or module.INSTALLED_PRIVATE
    module.package(output, private, layerling, installed_public,
                   deployment_config_path=deployment_config_path, layerling_commit=layerling_commit)
    public = output/'public'
    bundle = output/'private/app/cad'; bundle.mkdir(mode=0o700)
    shutil.copyfile(export/'index.html', bundle/'index.html')
    (bundle/'manifest.json').write_text(json.dumps({'kind':'sso-layerling-cad-owner-v2',
        'entryRoutes':'cad-first-v1', 'hostedMcp':True, 'source':metadata, 'indexSha256':digest((bundle/'index.html').read_bytes())}, indent=2)+'\n')
    shutil.copyfile(source/BUILD_MARKER, bundle/'build.json')
    # Exact verified export, with executable PHP and alternative app/HTML entry points excluded.
    excluded = {'index.html','index.txt','store.php','sw.js','manifest.webmanifest','support.html','view.html',
        '404.html','robots.txt','sitemap.xml'}
    for relative in report['files']:
        path = Path(relative)
        if relative in excluded or path.parts[0] == '404': continue
        if path.suffix.lower() in ['.php','.phtml','.phar'] or any(p.startswith('.') for p in path.parts):
            raise ValueError('Unexpected executable/hidden export')
        target = public/path
        if target.exists(): raise ValueError('Export would overwrite wrapper file')
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(export/path, target)
    shutil.copyfile(ROOT/'public/cad.php', public/'cad.php')
    for name in ['konto', 'files']:
        directory = public/name
        directory.mkdir(mode=0o700)
        shutil.copyfile(ROOT/'public'/name/'index.php', directory/'index.php')
    for suffix in ['js','css']: shutil.copyfile(ROOT/'cad'/('bridge.'+suffix), public/('cad-bridge.'+suffix))
    (public/'cad-session.php').write_text("<?php\ndeclare(strict_types=1);\nini_set('display_errors','0');\n(require '"+private+"/app/src/storage-bootstrap.php')->cadSession();\n")
    (public/'mcp.php').write_text("<?php\ndeclare(strict_types=1);\nrequire '" + private + "/app/src/mcp-bootstrap.php';\n")
    manifest_path = output/'manifest.json'; manifest = json.loads(manifest_path.read_text())
    if hosted_test and not manifest['sourceCommit']:
        raise ValueError('CAD test packaging requires a clean committed wrapper')
    manifest['kind'] = 'sso-layerling-cad-test' if hosted_test else 'sso-layerling-cad-candidate'
    manifest['files'] = {str(p.relative_to(output)):digest(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file() and p != manifest_path}
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    for p in output.rglob('*'): p.chmod(0o700 if p.is_dir() else 0o600)
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--layerling', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('build'); p.add_argument('--source', type=Path, required=True); p.add_argument('--layerling', type=Path, required=True)
    p = commands.add_parser('package'); p.add_argument('--source', type=Path, required=True); p.add_argument('--layerling', type=Path, required=True); p.add_argument('--output', type=Path, required=True); p.add_argument('--hosted-test', action='store_true')
    p.add_argument('--deployment-config', type=Path, help='Private deployment metadata, required with --hosted-test')
    for command in commands.choices.values():
        command.add_argument('--layerling-commit', help='Use a compatible descendant of the reviewed Layerling pin')
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            prepare(args.layerling.resolve(), args.output.resolve(), layerling_commit=args.layerling_commit)
            print('Isolated CAD source prepared.')
        elif args.action == 'build':
            build(args.source.resolve(), args.layerling.resolve(), layerling_commit=args.layerling_commit)
            print('CAD candidate build verified.')
        else:
            package(args.source.resolve(), args.layerling.resolve(), args.output.resolve(), hosted_test=args.hosted_test,
                    deployment_config_path=args.deployment_config, layerling_commit=args.layerling_commit)
            print('CAD test package prepared for explicit installation.' if args.hosted_test else 'Local CAD candidate packaged.')
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'CAD {args.action} failed: {error}\n')
