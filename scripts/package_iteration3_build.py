"""Package prebuilt JAR/dist and build evidence. Run Maven/npm builds first."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0-iteration3-build.1'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode().strip()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--log-dir', required=True)
    parser.add_argument('--source-commit', default='HEAD')
    args = parser.parse_args()
    out, logs = Path(args.output_dir).resolve(), Path(args.log_dir).resolve()
    source = git('rev-parse', args.source_commit)
    for folder in ['backend', 'frontend']:
        if git('rev-parse', f'{source}:{folder}') != git('rev-parse', f'HEAD:{folder}'):
            raise RuntimeError('Source commit does not match current application tree')
    if git('status', '--porcelain', '--untracked-files=no', '--', 'backend', 'frontend'):
        raise RuntimeError('Tracked application files have uncommitted changes')
    suites = [ET.parse(p).getroot() for p in (ROOT/'backend/target/surefire-reports').glob('TEST-*.xml')]
    counts = {k: sum(int(s.get(k, '0')) for s in suites) for k in ['tests', 'failures', 'errors', 'skipped']}
    if not suites or counts['tests'] == 0 or any(counts[k] for k in ['failures', 'errors', 'skipped']):
        raise RuntimeError('Backend test reports missing or not all passing')
    for name, marker in [('backend.log', 'BUILD SUCCESS'), ('frontend.log', 'built in')]:
        if marker not in (logs/name).read_text(encoding='utf-8', errors='replace'):
            raise RuntimeError('Successful build log missing: '+name)
    jar = ROOT/'backend/target/shop-0.1.0.jar'
    with zipfile.ZipFile(jar) as z:
        assert z.testzip() is None
        entry = 'BOOT-INF/classes/com/team/shop/ShopApplication.class'
        major = int.from_bytes(z.read(entry)[6:8], 'big')
        assert major == 61, ('Expected Java 17 bytecode', major)
    dist = ROOT/'frontend/dist'
    html = (dist/'index.html').read_text(encoding='utf-8')
    for ref in re.findall(r'(?:src|href)="(/assets/[^"]+)"', html):
        assert (dist/ref.lstrip('/')).is_file(), ref
    folder = out/f'OxStore-{VERSION}'
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'build/backend').mkdir(parents=True)
    shutil.copy2(jar, folder/'build/backend/shop-0.1.0.jar')
    shutil.copytree(dist, folder/'build/frontend')
    shutil.copy2(ROOT/'docs/iterationB/build-guide.md', folder/'构建过程手册.md')
    (folder/'evidence/logs').mkdir(parents=True)
    for name in ['backend.log', 'npm-ci.log', 'frontend.log']:
        text = (logs/name).read_text(encoding='utf-8', errors='replace')
        text = re.sub(r'Using generated security password: .*', 'Using generated security password: [test value omitted]', text)
        (folder/'evidence/logs'/name).write_text(text, encoding='utf-8')
    (folder/'evidence/junit-summary.json').write_text(json.dumps({
        'totals': counts, 'suites': [{**{k:s.get(k) for k in ['name','tests','failures','errors','skipped']},
        'cases':[c.get('name') for c in s.findall('testcase')]} for s in suites]
    }, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    manifest = {'version': VERSION, 'builtAt': datetime.now(timezone.utc).isoformat(),
                'sourceCommit': source,
                'sourceTrees': {f:git('rev-parse', f'{source}:{f}') for f in ['backend','frontend']},
                'backendTests': counts, 'javaClassMajorVersion':major,
                'tools': json.loads((logs/'tools.json').read_text(encoding='utf-8-sig')),
                'commands':['mvn -B -ntp -f backend/pom.xml clean verify',
                            'npm ci --registry=https://registry.npmjs.org','npm run build'],
                'scope':'Build outputs and backend JUnit tests; no new deployment or MySQL acceptance run.'}
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sums = ''.join(f'{sha(p)}  {p.relative_to(folder).as_posix()}\n' for p in sorted(folder.rglob('*')) if p.is_file())
    (folder/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    archive = out/f'{folder.name}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for line in (folder/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
            digest, path = line.split('  ',1)
            assert hashlib.sha256(z.read(folder.name+'/'+path)).hexdigest()==digest
    (out/'SHA256SUMS.txt').write_text(f'{sha(archive)}  {archive.name}\n',encoding='utf-8')
    manifest['archive']={'filename':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive)}
    (out/'build-results.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
