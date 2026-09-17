"""Build explicit client/source archives. Never includes per-user state or keys."""
from __future__ import annotations
import hashlib,json,os,pathlib,re,shutil,subprocess,zipfile
ROOT=pathlib.Path(__file__).resolve().parent
GO=os.environ.get('GO_BINARY','go')
OUT=ROOT/'dist';OUT.mkdir(exist_ok=True)
BUILD_VERSION=subprocess.check_output([GO,'version'],text=True).strip()
m=re.search(r'go(\d+)\.(\d+)(?:\.(\d+))?(?:\s|$)',BUILD_VERSION)
LOCAL_ONLY=m is None or tuple(int(v or 0) for v in m.groups()) < (1,27,1)
TARGETS=[('Windows-x64','windows','amd64'),('Linux-x64','linux','amd64'),('macOS-arm64','darwin','arm64'),('macOS-x64','darwin','amd64')]
DOCS=['README_RU.md','README.md','LICENSE','BUILD.md','DEPLOY.md','ARCHITECTURE.md','SECURITY.md']
report={'toolchain':BUILD_VERSION,'release_state':'experimental; no public coordinator; unsigned','targets':[]}
for label,goos,arch in TARGETS:
 d=OUT/f'KeyAI-Commons-{label}';d.mkdir(exist_ok=True)
 exe='KeyAI-Commons.exe' if goos=='windows' else 'keyai-commons'
 env={**os.environ,'GOOS':goos,'GOARCH':arch,'CGO_ENABLED':'0'}
 subprocess.run([GO,'build','-trimpath','-ldflags=-s -w','-o',str(d/exe),'.'],cwd=ROOT/'src',env=env,check=True)
 for n in DOCS:shutil.copy2(ROOT/n,d/n)
 if goos=='windows':
  for fn,mode in [('RUN-CLIENT.cmd','client'),('LOCAL-DEMO.cmd','demo'),('RUN-COORDINATOR.cmd','coordinator')]:
   (d/fn).write_bytes(('@echo off\r\ncd /d "%~dp0"\r\n"%~dp0KeyAI-Commons.exe" '+mode+'\r\nif errorlevel 1 pause\r\n').encode())
 else:
  for fn,mode in [('run-client.sh','client'),('local-demo.sh','demo'),('run-coordinator.sh','coordinator')]:
   p=d/fn;p.write_text('#!/bin/sh\nset -eu\ncd -- "$(dirname -- "$0")"\nexec ./keyai-commons '+mode+'\n');p.chmod(0o755)
 # Explicitly label what this build can do; do not fake signing or notarization.
 local_only=LOCAL_ONLY
 manifest={'name':'KeyAI Commons','version':'0.1.0','platform':f'{goos}/{arch}','toolchain':BUILD_VERSION,'local_test_only':local_only,'publisher_signed':False,'macos_notarized':False,'gpu_training':False,'llm_training':False,'public_coordinator_deployed':False,'sha256':hashlib.sha256((d/exe).read_bytes()).hexdigest()}
 (d/'BUILD_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
 zip_path=OUT/(d.name+('.LOCAL-TEST.zip' if local_only else '.zip'))
 with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,9) as z:
  for p in sorted(d.iterdir()):z.write(p,pathlib.Path(d.name)/p.name)
 report['targets'].append({'archive':zip_path.name,'bytes':zip_path.stat().st_size,**manifest})
 print(zip_path.name,zip_path.stat().st_size,flush=True)
(OUT/'BUILD_REPORT.json').write_text(json.dumps(report,indent=2))
# Source contains explicit files only, never a recursive copy of unknown directories.
source=OUT/'KeyAI-Commons-Source.zip'
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,9) as z:
 for p in sorted((ROOT/'src').rglob('*')):
  if p.is_file() and (p.suffix in {'.go','.html'} or p.name=='go.mod'):z.write(p,pathlib.Path('KeyAI-Commons-Source')/p.relative_to(ROOT))
 for name in [*DOCS,'X_POST_EN.txt','X_POST_RU.txt','build_ui.py','package.py','integration_test.py','browser_test.py','render_preview.py','.gitignore','test-results.txt','integration-results.json','browser-results.json']:
  if (ROOT/name).exists():z.write(ROOT/name,pathlib.Path('KeyAI-Commons-Source')/name)
 z.write(OUT/'BUILD_REPORT.json','KeyAI-Commons-Source/BUILD_REPORT.json')
 for extra in ['site/index.html','CONTRIBUTING.md','ROADMAP.md','PRIVACY.md']:
  z.write(ROOT/extra,pathlib.Path('KeyAI-Commons-Source')/extra)
 # On a Windows PC with the source archive and a current Go compiler, this builds
 # and launches the ACTUAL downloaded source. No internet code is fetched.
 content='''@echo off\r\ncd /d "%~dp0"\r\nset "GOTOOL=go"\r\nif exist "C:\\KeyAI\\Commons\\toolchain\\go\\bin\\go.exe" set "GOTOOL=C:\\KeyAI\\Commons\\toolchain\\go\\bin\\go.exe"\r\ncd src\r\n"%GOTOOL%" version\r\nif errorlevel 1 goto failed\r\n"%GOTOOL%" test ./...\r\nif errorlevel 1 goto failed\r\n"%GOTOOL%" build -trimpath -ldflags="-s -w" -o ..\\KeyAI-Commons.exe .\r\nif errorlevel 1 goto failed\r\ncd ..\r\n"%~dp0KeyAI-Commons.exe" demo\r\nexit /b\r\n:failed\r\necho Build failed. No training was started.\r\npause\r\n'''
 z.writestr('KeyAI-Commons-Source/BUILD-AND-DEMO.cmd',content)
# A standalone site template, with only explicit local-pilot download links.
site=OUT/'KeyAI-Commons-Site';site.mkdir(exist_ok=True);(site/'downloads').mkdir(exist_ok=True)
html=(ROOT/'site'/'index.html').read_text()
for item in report['targets']:
 short=item['archive'].replace('.LOCAL-TEST.zip','.zip')
 html=html.replace('downloads/'+short,'downloads/'+item['archive'])
 shutil.copy2(OUT/item['archive'],site/'downloads'/item['archive'])
shutil.copy2(source,site/'downloads'/source.name)
(site/'index.html').write_text(html)
(site/'README.txt').write_text('Static website template, not deployed. Local-test downloads cannot connect over the Internet. Replace with reviewed current-toolchain builds and deploy a coordinator before a network launch. Never include private state files.\n')
sitezip=OUT/'KeyAI-Commons-Site.zip'
with zipfile.ZipFile(sitezip,'w',zipfile.ZIP_DEFLATED,6) as z:
 for p in sorted(site.rglob('*')):
  if p.is_file():z.write(p,pathlib.Path(site.name)/p.relative_to(site))
checksums=[]
for p in sorted(OUT.glob('*.zip')):checksums.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name)
(OUT/'SHA256SUMS.txt').write_text('\n'.join(checksums)+'\n')
print('SOURCE',source.name,source.stat().st_size)
print('SITE',sitezip.name,sitezip.stat().st_size)
