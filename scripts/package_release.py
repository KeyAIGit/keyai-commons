#!/usr/bin/env python3
"""Portable CPU-pilot builds. No compiler or installer downloads at client launch."""
import argparse, hashlib, json, os, pathlib, re, subprocess, tempfile, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
TARGETS=[('windows','amd64','Windows-x64'),('windows','arm64','Windows-arm64'),('linux','amd64','Linux-x64'),('linux','arm64','Linux-arm64'),('darwin','amd64','macOS-x64'),('darwin','arm64','macOS-arm64')]
START='''KeyAI Commons 0.2.0 | Research preview

NO COMPILER NEEDED. Extract the archive completely.
Windows: double-click START-CLIENT.cmd (or KeyAI-Commons.exe).
Linux/macOS: run ./start-client.sh. macOS also has START-CLIENT.command.
For a standalone demonstration use LOCAL-DEMO.cmd or ./local-demo.sh.

NETWORK: Open the client, enter the organizer's HTTPS coordinator address,
review its identity, choose CPU pacing and explicitly enable a short session.
Training starts ONLY after an operator command AND your consent.
Closing a browser tab does NOT exit the client. Use Pause now or Exit application.
No hidden startup, silent update, downloaded executable task, mining, or payments.

This release is UNSIGNED and macOS builds are NOT NOTARIZED. Do not disable
OS protections. Use an invited test or inspect/build the source instead.
The program has NOT had an independent security audit.

It trains a fixed 65-parameter CPU neural network on synthetic data. It is not
an LLM or GPU network. Full server replay duplicates work; no compute savings
or million-node performance is claimed. A free ephemeral test host may lose
registrations and checkpoints on restart; reconnect explicitly when required.
The program never automatically restores consent after a client restart.

Source: https://github.com/KeyAIGit/keyai-commons
Releases: https://github.com/KeyAIGit/keyai-commons/releases
Русская инструкция: https://github.com/KeyAIGit/keyai-commons/blob/main/README_RU.md
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--go',default='go');p.add_argument('--output',default=str(ROOT/'dist-v02'));p.add_argument('--target',action='append');a=p.parse_args()
 out=pathlib.Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
 tool=subprocess.check_output([a.go,'version'],text=True).strip()
 m=re.search(r'go(\d+)\.(\d+)\.(\d+)',tool)
 if not m or tuple(map(int,m.groups()))<(1,27,1):raise SystemExit('Network preview packaging requires Go 1.27.1 or newer; refusing an old build.')
 subprocess.run([a.go,'test','-count=1','./...'],cwd=ROOT/'src',check=True)
 try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 except (subprocess.CalledProcessError,FileNotFoundError):commit='not-in-git'
 artifacts=[]
 for goos,arch,label in TARGETS:
  if a.target and label not in a.target:continue
  with tempfile.TemporaryDirectory(prefix='commons-package-') as temp:
   d=pathlib.Path(temp);binary='KeyAI-Commons.exe' if goos=='windows' else 'keyai-commons'
   env=dict(os.environ,GOOS=goos,GOARCH=arch,CGO_ENABLED='0')
   subprocess.run([a.go,'build','-trimpath','-buildvcs=false','-ldflags=-s -w','-o',str(d/binary),'.'],cwd=ROOT/'src',env=env,check=True)
   (d/'START-HERE.txt').write_text(START,encoding='utf-8');(d/'LICENSE').write_bytes((ROOT/'LICENSE').read_bytes())
   if goos=='windows':
    for name,mode in [('START-CLIENT.cmd','client'),('LOCAL-DEMO.cmd','demo')]:
     (d/name).write_bytes(('@echo off\r\ncd /d "%~dp0"\r\n"%~dp0KeyAI-Commons.exe" '+mode+'\r\nif errorlevel 1 pause\r\n').encode())
   else:
    for name,mode in [('start-client.sh','client'),('local-demo.sh','demo')]:
     text='#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexec ./keyai-commons '+mode+' "$@"\n';(d/name).write_text(text)
    if goos=='darwin':
     (d/'START-CLIENT.command').write_text((d/'start-client.sh').read_text());(d/'LOCAL-DEMO.command').write_text((d/'local-demo.sh').read_text())
   filename='KeyAI-Commons-'+label+'.zip';dest=out/filename
   with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(d.iterdir()):
     info=zipfile.ZipInfo(f.name,(2026,9,17,0,0,0));info.create_system=3
     info.external_attr=((0o100755 if f.name==binary or f.suffix in ('.sh','.command') else 0o100644)<<16)
     z.writestr(info,f.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
   artifacts.append({'file':filename,'sha256':sha(dest),'bytes':dest.stat().st_size,'os':goos,'arch':arch,'publisher_signed':False})
   print('BUILT',filename,artifacts[-1]['sha256'],flush=True)
 report={'version':'0.2.0','source_commit':commit,'toolchain':tool,'workload':'tiny-xor-mlp-v1 CPU only','artifacts':artifacts,'independent_security_audit':False}
 (out/'BUILD-MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'SHA256SUMS.txt').write_text(''.join(f"{v['sha256']}  {v['file']}\n" for v in artifacts))
 print('PACKAGES_READY',out)
if __name__=='__main__':main()
