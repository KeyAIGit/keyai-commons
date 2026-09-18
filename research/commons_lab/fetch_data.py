"""Explicit local research download: only the two preselected immutable files.
<=2,250,255,763 corpus bytes plus bounded provenance. Never imported by clients.
"""
import argparse, hashlib, json, os, time, urllib.request
from pathlib import Path
from .data import digest_file, write_json
REV='f54c09fd23315a6f9c86f9dc80f725de7d8f9c64'
PINNED={
 'TinyStoriesV2-GPT4-train.txt':(2227753162,'6418d412de72888f52b5142c761ac21a582f7d1166f0bfbdb5f03ccfdec90443'),
 'TinyStoriesV2-GPT4-valid.txt':(22502601,'6874bae9a4c1a4e7edcf0e53b86c17817e9cf881fc75ff2368da457b80c0585d')}


def fetch(folder:Path,timeout_seconds=900):
    folder.mkdir(parents=True,exist_ok=True);started=time.monotonic();report={}
    for name,(size,want) in PINNED.items():
        final=folder/name;temp=folder/(name+'.partial')
        if final.exists():
            if final.stat().st_size!=size or digest_file(final)!=want:raise ValueError('Existing raw file mismatch')
            report[name]={'bytes':size,'sha256':want,'reused':True};continue
        offset=temp.stat().st_size if temp.exists() else 0
        if offset>size:raise ValueError('Partial exceeds expected source size')
        if offset<size:
            url=f'https://huggingface.co/datasets/roneneldan/TinyStories/resolve/{REV}/{name}'
            headers={'User-Agent':'KeyAI-Commons-local-research/1'}
            if offset:headers['Range']=f'bytes={offset}-'
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as r:
                if not r.url.startswith('https://'):raise ValueError('Non-HTTPS redirect')
                if offset and (r.status!=206 or not r.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                    raise ValueError('Server did not honor resume range; existing partial kept')
                with temp.open('ab' if offset else 'xb') as f:
                    n=offset;last=n
                    while b:=r.read(4<<20):
                        n+=len(b)
                        if n>size or time.monotonic()-started>timeout_seconds:raise ValueError('Download budget exceeded')
                        f.write(b)
                        if n-last>128<<20:print('DOWNLOAD',name,n,'/',size,flush=True);last=n
                    f.flush();os.fsync(f.fileno())
        if temp.stat().st_size!=size or digest_file(temp)!=want:raise ValueError('Downloaded raw source hash mismatch')
        os.replace(temp,final);report[name]={'bytes':size,'sha256':want,'reused':False}
        print('VERIFIED',name,size,want,flush=True)
    for name,url in [('dataset-card.md',f'https://huggingface.co/datasets/roneneldan/TinyStories/raw/{REV}/README.md'),('CDLA-Sharing-1.0.html','https://cdla.dev/sharing-1-0/')]:
        p=folder/name
        if not p.exists():
            with urllib.request.urlopen(url,timeout=30) as r:raw=r.read(2<<20)
            if len(raw)>=2<<20:raise ValueError('Provenance exceeds cap')
            p.write_bytes(raw)
        report[name]={'url':url,'bytes':p.stat().st_size,'sha256':digest_file(p)}
    report['elapsed_seconds']=time.monotonic()-started
    write_json(folder/'download-report.json',report)
    print('RAW_SOURCE_READY',json.dumps(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',type=Path,required=True)
    p.add_argument('--download-reviewed-corpus',action='store_true',required=True)
    a=p.parse_args();fetch(a.raw)
