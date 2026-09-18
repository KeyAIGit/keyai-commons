"""Single-file, atomic, pickle-free local research checkpoints.
Integrity hashes are not authority signatures. No network input is accepted.
Snapshot only at completed optimizer-step boundaries; incomplete work is lost.
"""
from __future__ import annotations
import hashlib, json, math, os, tempfile
from pathlib import Path
import torch
from safetensors import safe_open
from safetensors.torch import save_file

MAX_BYTES=4*1024**3
MAX_NODES=500_000


def sha256(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()


def save(path: Path, state: dict) -> str:
    if path.exists():raise FileExistsError('Immutable snapshot already exists')
    path.parent.mkdir(parents=True,exist_ok=True)
    tensors={}; nodes=0; total=0
    def encode(value,depth=0):
        nonlocal nodes,total
        nodes+=1
        if depth>64 or nodes>MAX_NODES:raise ValueError('Checkpoint structure limit')
        if isinstance(value,torch.Tensor):
            if value.layout!=torch.strided:raise ValueError('Dense tensors only')
            if value.is_floating_point() and not torch.isfinite(value).all():raise ValueError('Nonfinite checkpoint tensor')
            total+=value.numel()*value.element_size()
            if total>MAX_BYTES:raise ValueError('Checkpoint tensor budget')
            key=f't{len(tensors):06d}';tensors[key]=value.detach().cpu().contiguous().clone()
            return ['tensor',key]
        if type(value) in (str,int,bool) or value is None:return ['scalar',value]
        if type(value) is float:
            if not math.isfinite(value):raise ValueError('Nonfinite metadata')
            return ['scalar',value]
        if isinstance(value,dict):return ['dict',[[encode(k,depth+1),encode(v,depth+1)] for k,v in value.items()]]
        if type(value) in (list,tuple):return ['tuple' if type(value) is tuple else 'list',[encode(v,depth+1) for v in value]]
        raise ValueError('Unsupported checkpoint type: '+str(type(value)))
    tree=json.dumps(encode(state),separators=(',',':'),allow_nan=False)
    if len(tree)>16<<20:raise ValueError('Checkpoint metadata budget')
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.partial',dir=path.parent);os.close(fd)
    try:
        save_file(tensors,tmp,metadata={'format':'commons-local-state-v1','tree':tree})
        with open(tmp,'rb') as f:os.fsync(f.fileno())
        if path.exists():raise FileExistsError(path)
        # Single-writer research artifact. The directory and file are local, not a shared service.
        os.replace(tmp,path)
        if os.name=='posix':
            fd=os.open(path.parent,os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return sha256(path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def load(path: Path, expected_hash: str) -> dict:
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_BYTES+(32<<20):
        raise ValueError('Checkpoint file invalid')
    if len(expected_hash)!=64 or sha256(path)!=expected_hash:raise ValueError('Checkpoint hash mismatch')
    with safe_open(path,framework='pt',device='cpu') as f:
        meta=f.metadata() or {}
        if meta.get('format')!='commons-local-state-v1' or len(meta.get('tree',''))>16<<20:
            raise ValueError('Checkpoint format/metadata invalid')
        tree=json.loads(meta['tree']);used=set();nodes=0
        def decode(item,depth=0):
            nonlocal nodes
            nodes+=1
            if depth>64 or nodes>MAX_NODES or not isinstance(item,list) or len(item)!=2:
                raise ValueError('Invalid checkpoint tree')
            kind,value=item
            if kind=='tensor':
                if value in used:raise ValueError('Duplicate tensor reference')
                used.add(value);t=f.get_tensor(value)
                if t.is_floating_point() and not torch.isfinite(t).all():raise ValueError('Nonfinite checkpoint')
                return t
            if kind=='scalar':
                if type(value) not in (str,int,float,bool,type(None)) or (type(value) is float and not math.isfinite(value)):
                    raise ValueError('Invalid scalar')
                return value
            if kind in ('list','tuple'):
                result=[decode(v,depth+1) for v in value]
                return tuple(result) if kind=='tuple' else result
            if kind=='dict':
                out={}
                for k,v in value:
                    key=decode(k,depth+1)
                    if type(key) not in (str,int) or key in out:raise ValueError('Invalid/duplicate dictionary key')
                    out[key]=decode(v,depth+1)
                return out
            raise ValueError('Unknown checkpoint tag')
        state=decode(tree)
        if used!=set(f.keys()) or not isinstance(state,dict):raise ValueError('Unreferenced tensors or invalid root')
    return state
