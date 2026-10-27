#!/usr/bin/env python3
"""Build an installable plugin archive, including hidden manifests and MCP configuration."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

FILES = ('README.md', 'LICENSE', 'CHANGELOG.md', 'CONTRIBUTING.md', 'PUBLICATION.md', 'AGENTS.md', '.mcp.json')
DIRECTORIES = ('skills', 'commands', 'rules', '.claude-plugin', '.cursor-plugin', '.codex-plugin', '.grok-plugin', '.agents/plugins')
SUFFIXES = {'.md', '.mdc', '.json', '.py'}


def build(root: Path, output: Path) -> Path:
    version = json.loads((root / '.claude-plugin/plugin.json').read_text())['version']
    paths = [root / name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend(p for p in (root / directory).rglob('*') if p.is_file() and p.suffix in SUFFIXES
                     and not any(part in {'__pycache__', 'node_modules', '.venv'} for part in p.parts))
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Missing or symlinked release file: {path.relative_to(root)}')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'shieldlabs-skills-v{version}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(set(paths)):
            info = zipfile.ZipInfo(f'shieldlabs-skills-{version}/{path.relative_to(root).as_posix()}', date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    print(build(Path(__file__).resolve().parent.parent, args.output))
