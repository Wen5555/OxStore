"""Prepare/export an offline course release, excluding runtime configuration."""
from __future__ import annotations
import argparse
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0-docker.1'
IMAGES = ['oxstore/backend:' + VERSION, 'oxstore/frontend:' + VERSION, 'mysql:8.0.46']


def command(*args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout.decode('utf-8', errors='replace')


def prepare(folder: Path):
    folder.mkdir(parents=True, exist_ok=False)
    for name in ['compose.yml', '.env.example', 'init-env.ps1', 'init-env.sh', 'README.md']:
        shutil.copy2(ROOT / 'deploy/docker' / name, folder / name)
    shutil.copy2(ROOT / 'docs/build.md', folder / 'build-guide.md')
    (folder / 'database').mkdir()
    db = ROOT / 'backend/src/main/resources/db'
    shutil.copy2(db / 'schema.sql', folder / 'database/schema.sql')
    shutil.copytree(db / 'migrations', folder / 'database/migrations')
    shutil.copy2(ROOT / 'docs/design/database.md', folder / 'database/database-guide.md')
    shutil.copy2(ROOT / 'docs/runbook.md', folder / 'database/runbook.md')
    (folder / 'scripts').mkdir()
    shutil.copy2(ROOT / 'scripts/verify_docker_release.py', folder / 'scripts/verify_docker_release.py')
    for name in ['docker_ui_smoke.js', 'verify_docker_ui.ps1']:
        shutil.copy2(ROOT / 'scripts' / name, folder / 'scripts' / name)
    (folder / 'evidence').mkdir()
    (folder / 'build').mkdir()


def extract(image: str, source: str, target: Path):
    name = 'oxstore-artifact-' + uuid.uuid4().hex[:10]
    command('docker', 'create', '--name', name, image)
    try:
        command('docker', 'cp', name + ':' + source, str(target))
    finally:
        command('docker', 'rm', name)


def export(folder: Path, save_images=True):
    if (folder / '.env').exists():
        raise ValueError('Runtime .env must never be included in the release')
    # Refresh selected public files after final documentation changes.
    for name in ['compose.yml', '.env.example', 'init-env.ps1', 'init-env.sh', 'README.md']:
        shutil.copy2(ROOT / 'deploy/docker' / name, folder / name)
    shutil.copy2(ROOT / 'docs/build.md', folder / 'build-guide.md')
    shutil.copy2(ROOT / 'scripts/verify_docker_release.py', folder / 'scripts/verify_docker_release.py')
    for name in ['docker_ui_smoke.js', 'verify_docker_ui.ps1']:
        shutil.copy2(ROOT / 'scripts' / name, folder / 'scripts' / name)
    if save_images:
        extract(IMAGES[0], '/app/app.jar', folder / 'build/shop-0.1.0.jar')
        dist = folder / 'build/frontend-dist'
        extract(IMAGES[1], '/usr/share/nginx/html', dist)
        with zipfile.ZipFile(folder / 'build/frontend-dist.zip', 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(dist.rglob('*')):
                if f.is_file():
                    z.write(f, f.relative_to(dist).as_posix())
        tar = folder / 'images.tar'
        command('docker', 'image', 'save', '-o', str(tar), *IMAGES)
        with tar.open('rb') as src, gzip.open(folder / 'images.tar.gz', 'wb', compresslevel=1) as dst:
            shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
        # A single archive produced above, resolved within the explicit bundle; no recursive removal.
        if tar.resolve().parent != folder.resolve():
            raise ValueError('Unexpected archive path')
        tar.unlink()
    images = []
    for tag in IMAGES:
        info = json.loads(command('docker', 'image', 'inspect', tag))[0]
        images.append({'tag': tag, 'id': info['Id'], 'repo_digests': info.get('RepoDigests', []),
                       'platform': info['Os'] + '/' + info['Architecture'], 'size': info['Size']})
    manifest = {'version': VERSION, 'created_at': datetime.now().astimezone().isoformat(),
                'repository': 'https://github.com/Wen5555/OxStore',
                'source_commit': command('git', '-C', str(ROOT), 'rev-parse', 'HEAD').strip(),
                'working_tree_clean': not command('git', '-C', str(ROOT), 'status', '--porcelain').strip(),
                'docker_version': command('docker', 'version', '--format', '{{.Server.Version}}').strip(),
                'compose_version': command('docker', 'compose', 'version', '--short').strip(), 'images': images}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = []
    for file in sorted(folder.rglob('*')):
        if file.is_file() and file.name != 'SHA256SUMS':
            rel = file.relative_to(folder).as_posix()
            if file.name.startswith('.env') and file.name != '.env.example':
                raise ValueError('Unexpected runtime configuration')
            with file.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            lines.append(digest + '  ' + rel)
    (folder / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    archive = folder.parent / (folder.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for file in sorted(folder.rglob('*')):
            if file.is_file():
                rel = file.relative_to(folder.parent).as_posix()
                z.write(file, rel, compress_type=zipfile.ZIP_STORED if file.name.endswith(('.gz', '.zip', '.webm', '.mp4')) else zipfile.ZIP_DEFLATED)
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                      'sha256': hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'export', 'finalize'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.output.resolve())
    else:
        export(args.output.resolve(), save_images=args.mode == 'export')
