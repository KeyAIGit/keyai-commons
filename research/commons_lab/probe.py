"""A bounded shape/gradient/optimizer probe, not model training or a GPU benchmark.
Default device is CPU; choosing CUDA explicitly never enables a public worker.
"""
import argparse, hashlib, json, platform, time
from dataclasses import asdict
from pathlib import Path
import torch
from .config import ModelConfig
from .model import Decoder

def probe(device='cpu',steps=3):
    if device not in ('cpu','cuda') or not 1<=steps<=5:raise ValueError('Bounded CPU/CUDA probe only')
    if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA not available')
    torch.set_num_threads(2);torch.manual_seed(1709)
    c=ModelConfig();started=time.monotonic();m=Decoder(c).to(device)
    n=sum(p.numel() for p in m.parameters());assert n==22029696
    opt=torch.optim.AdamW(m.parameters(),lr=4e-4,betas=(.9,.95),eps=1e-8,weight_decay=.1,foreach=False)
    generator=torch.Generator().manual_seed(2026)
    batch=torch.randint(0,c.vocab_size,(1,129),generator=generator).to(device)
    losses=[]
    for _ in range(steps):
        opt.zero_grad(set_to_none=True);loss=m.loss(batch)
        if not torch.isfinite(loss):raise AssertionError('Non-finite loss')
        loss.backward();norm=torch.nn.utils.clip_grad_norm_(m.parameters(),1.,error_if_nonfinite=True);opt.step()
        losses.append(float(loss.detach()))
    if device=='cuda':torch.cuda.synchronize()
    return dict(scope='one device; FP32; 128-token repeated random batch; shape/gradient/update probe only',
                parameters=n,model=asdict(c),steps=steps,losses=losses,
                elapsed_seconds_including_initialization=time.monotonic()-started,device=device,
                torch=torch.__version__,python=platform.python_version(),
                peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated() if device=='cuda' else None,
                gpu_6gb_fit_verified=False,natural_language_training=False,
                limitations=['sequence 512 throughput not measured','not a held-out-quality result','no multi-host run'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--device',choices=('cpu','cuda'),default='cpu');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Output exists; use a new run name')
    r=probe(a.device);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
