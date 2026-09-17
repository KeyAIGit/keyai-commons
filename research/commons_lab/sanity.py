"""Bounded single-process optimizer sanity experiment, NEVER a WAN benchmark.
The data are project-generated integer sequences, not a language corpus.
"""
import argparse, copy, hashlib, json, math, platform, random, time
from dataclasses import asdict
from pathlib import Path
import torch
from torch.nn.utils import parameters_to_vector, vector_to_parameters
from .config import ModelConfig
from .model import Decoder

def batches(seed, step, workers=4, batch=2, length=32, vocab=64, split='train'):
    out=[]
    for w in range(workers):
        rows=[]
        for b in range(batch):
            # Stable sample IDs rather than process-dependent hash().
            key=f'{split}:{seed}:{step}:{w}:{b}'.encode()
            if split not in ('train','validation'):raise ValueError('Unknown fixture split')
            rng=random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8],'big'))
            for attempt in range(10000):
                token=rng.randrange(4,vocab); row=[token]; delta=1
                for pos in range(length):
                    if pos%8==0:delta=rng.randrange(1,4)
                    token=4+(token-4+delta)%(vocab-4); row.append(token)
                # Independent seeds alone do NOT prevent duplicate sequences.
                # Content-hash split is applied before training/evaluation use.
                is_validation=int.from_bytes(hashlib.sha256(bytes(row)).digest()[:8],'big')%10==0
                if is_validation==(split=='validation'):break
            else:raise ValueError('No sample matched the deterministic content split')
            rows.append(row)
        out.append(torch.tensor(rows,dtype=torch.long))
    return out

def evaluate(model, val):
    model.eval()
    with torch.no_grad():value=float(model.loss(val))
    model.train();return value

def run(mode='single',seed=11,steps=128,local_steps=8,workers=4,max_seconds=90):
    if mode not in ('single','fedavg','diloco'):raise ValueError('Unknown method')
    if not 1<=steps<=1024 or not 1<=workers<=8 or not 1<=local_steps<=128:
        raise ValueError('Reference workload out of bounds')
    if steps%local_steps:raise ValueError('Steps must divide the exchange interval')
    if not 1<=max_seconds<=120:raise ValueError('Max runtime must be 1..120 seconds')
    torch.set_num_threads(2);torch.manual_seed(seed)
    cfg=ModelConfig(vocab_size=64,width=64,layers=2,heads=4,kv_heads=2,ff_width=192,context=32)
    server=Decoder(cfg);models=[copy.deepcopy(server) for _ in range(workers)] if mode!='single' else [server]
    opts=[torch.optim.AdamW(m.parameters(),lr=.002,betas=(.9,.95),eps=1e-8,weight_decay=.01,foreach=False) for m in models]
    val=torch.cat([x for i in range(16) for x in batches(7001,i,split='validation')])
    initial=evaluate(server,val);velocity=torch.zeros(sum(p.numel() for p in server.parameters()))
    history=[];processed=0;transfers=0;started=time.monotonic();completed=True
    for block in range(0,steps,local_steps):
        if time.monotonic()-started>max_seconds:completed=False;break
        parent=parameters_to_vector(server.parameters()).detach().clone()
        for m in models:
            if mode!='single':
                with torch.no_grad():vector_to_parameters(parent.clone(),m.parameters())
        for step in range(block,block+local_steps):
            if time.monotonic()-started>max_seconds:
                completed=False;break
            items=batches(seed,step,workers=workers)
            if mode=='single':
                opts[0].zero_grad(set_to_none=True)
                for item in items:(models[0].loss(item)/workers).backward()
                torch.nn.utils.clip_grad_norm_(models[0].parameters(),1.0,error_if_nonfinite=True)
                opts[0].step()
            else:
                for m,opt,item in zip(models,opts,items):
                    opt.zero_grad(set_to_none=True);loss=m.loss(item)
                    if not torch.isfinite(loss):raise ValueError('Non-finite local loss')
                    loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.0,error_if_nonfinite=True);opt.step()
            processed+=workers*2*32
        if not completed:break
        if mode!='single':
            delta=sum((parent-parameters_to_vector(m.parameters()).detach())/workers for m in models)
            if not torch.isfinite(delta).all():raise ValueError('Non-finite outer delta')
            if mode=='fedavg':updated=parent-delta
            else:
                velocity=.9*velocity+delta;updated=parent-.7*(delta+.9*velocity)
            with torch.no_grad():vector_to_parameters(updated,server.parameters())
            # Hypothetical FP32 star exchange. This is NOT measured network traffic.
            transfers+=2*workers*parent.numel()*parent.element_size()
        history.append({'tokens':processed,'validation_nll':evaluate(server,val)})
    elapsed=time.monotonic()-started
    return {'scope':'one CPU process; sequential logical learners; generated integer sequences; no real WAN/English training',
            'method':mode,'seed':seed,'model':asdict(cfg),'parameters':cfg.parameter_count(),
            'completed':completed,'logical_workers':workers,'local_steps':local_steps,'local_optimizer_steps_per_worker':steps if completed else processed//(workers*64),
            'processed_target_tokens':processed,'initial_nll':initial,'final_nll':history[-1]['validation_nll'] if history else initial,
            'elapsed_cpu_wall_seconds':elapsed,'runtime_limit_scope':'checked before each local step; not an OS-enforced hard deadline','estimated_fp32_star_payload_bytes':transfers,
            'payload_scope':'formula only; excludes TCP/TLS/retry/metadata; single mode has no transport',
            'torch':torch.__version__,'python':platform.python_version(),'history':history,
            'not_demonstrated':['natural-language convergence','distributed speedup','GPU performance','Byzantine robustness','public deployment']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--method',choices=['single','fedavg','diloco'],default='single')
    p.add_argument('--seed',type=int,default=11);p.add_argument('--steps',type=int,default=128);p.add_argument('--local-steps',type=int,default=8)
    p.add_argument('--max-seconds',type=int,default=90);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Output exists; use a new run name')
    report=run(a.method,a.seed,a.steps,a.local_steps,max_seconds=a.max_seconds)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('history','model')},indent=2))
if __name__=='__main__':main()
