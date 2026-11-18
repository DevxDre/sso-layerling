#!/usr/bin/env python3
"""Prepare the stdio client for this wrapper from the pinned Layerling commit."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
CLIENT_FILES = (
    'LICENSE',
    'scripts/layerling-mcp-server.mjs',
    'scripts/layerling-mcp-tools.mjs',
    'scripts/layerling-mcp-open.mjs',
    'scripts/layerling-mcp-notes-wait.mjs',
)


def prepare(layerling: Path, output: Path) -> Path:
    if output.exists() or output.is_symlink():
        raise ValueError('MCP client output must not exist')
    commit = json.loads((ROOT / 'upstream.lock.json').read_text())['commit']
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    with TemporaryDirectory(prefix='sso-mcp-client-') as temp:
        source = Path(temp)
        for name in CLIENT_FILES:
            target = source / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(subprocess.check_output(
                ['git', '--no-replace-objects', '-C', str(layerling), 'show', f'{commit}:{name}'], env=env))
        subprocess.run(['git', 'apply', '--whitespace=error', str(ROOT / 'cad/mcp-client.patch')],
                       cwd=source, env=env, check=True)
        shutil.copytree(source, output)
    return output / 'scripts/layerling-mcp-server.mjs'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layerling', type=Path, required=True, help='Git checkout containing the pinned Layerling commit')
    parser.add_argument('--output', type=Path, required=True, help='New output directory for the client')
    args = parser.parse_args()
    print(prepare(args.layerling.resolve(), args.output.absolute()))
