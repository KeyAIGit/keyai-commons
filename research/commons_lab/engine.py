"""Local optimizer engine for language data. Logical learners are sequential.
This is not an Internet backend. Public applications never import this package.
"""
from __future__ import annotations
import copy, math, platform, random
from dataclasses import dataclass, asdict
from contextlib import nullcontext
import numpy as np
import torch
from torch.nn.utils import parameters_to_vector, vector_to_parameters
from .model import Decoder
from .config import ModelConfig
from . import snapshot

@dataclass(frozen=True)
class TrainConfig:
    method: str='single'
    workers: int=4
    local_steps: int=8
    microbatch: int=2
    accumulation: int=4
    seed: int=11
    lr: float=.0004
    total_tokens: int=16_777_216
    precision: str='fp32'
    attention: str='math'
    outer_lr: float=.7
    momentum: float=.9
    def validate(self):
        if self.method not in ('single','fedavg','diloco') or self.precision not in ('fp32','fp16') or self.attention not in ('math','auto'):
            raise ValueError('Unsupported training mode')
        for k,lo,hi in [('workers',1,4),('local_steps',1,128),('microbatch',1,16),('accumulation',1,32),('total_tokens',1,200_000_000),('seed',0,2**31)]:
            v=getattr(self,k)
            if type(v) is not int or not lo<=v<=hi:raise ValueError('Invalid '+k)
        if not 0<self.lr<1 or not 0<self.outer_lr<2 or not 0<=self.momentum<1:raise ValueError('Invalid optimization hyperparameters')

class Engine:
    def __init__(self, model_config:ModelConfig, config:TrainConfig, stream, device='cpu'):
        config.validate();model_config.validate()
        if stream.split!='train':raise ValueError('Training requires the training split')
        if stream.context!=model_config.context:raise ValueError('Context mismatch')
        if config.precision=='fp16' and not str(device).startswith('cuda'):raise ValueError('FP16 training requires CUDA')
        self.mc,self.tc,self.stream,self.device=model_config,config,stream,torch.device(device)
        self.global_step=0;self.cursor=0;self.tokens=0;self.outer_updates=0;self.ledger='0'*64
        self.targets=config.workers*config.microbatch*config.accumulation*model_config.context
        if config.total_tokens%self.targets:raise ValueError('Token budget must contain whole global steps')
        random.seed(config.seed);torch.manual_seed(config.seed)
        self.server=Decoder(model_config).to(self.device)
        n=1 if config.method=='single' else config.workers
        self.models=[self.server] if n==1 and config.method=='single' else [copy.deepcopy(self.server) for _ in range(n)]
        self.opts=[torch.optim.AdamW(m.parameters(),lr=config.lr,betas=(.9,.95),eps=1e-8,weight_decay=.1,foreach=False) for m in self.models]
        self.scalers=[torch.amp.GradScaler('cuda',enabled=config.precision=='fp16',init_scale=1024.) for _ in self.models]
        self.parent=parameters_to_vector(self.server.parameters()).detach().clone()
        self.velocity=torch.zeros_like(self.parent)
    def context(self):
        return torch.autocast('cuda',dtype=torch.float16) if self.tc.precision=='fp16' else nullcontext()
    def attention(self):
        return torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.MATH) if self.tc.attention=='math' else nullcontext()
    def lr(self):
        progress=self.tokens/self.tc.total_tokens
        if progress<.05:return self.tc.lr*max(progress/.05,1/(self.tc.total_tokens/self.targets*.05))
        return self.tc.lr*(.1+.9*.5*(1+math.cos(math.pi*(progress-.05)/.95)))
    def step(self):
        import hashlib
        c=self.tc
        if self.tokens+self.targets>c.total_tokens:raise ValueError('Token budget exhausted')
        windows=c.workers*c.microbatch*c.accumulation
        if self.cursor+windows>self.stream.windows:raise ValueError('Corpus exhausted; no silent wrap/repeat')
        rows=[self.stream.window(i) for i in range(self.cursor,self.cursor+windows)]
        ids=np.stack(rows);mean=0.
        for index,(model,opt,scaler) in enumerate(zip(self.models,self.opts,self.scalers)):
            opt.zero_grad(set_to_none=True)
            for group in opt.param_groups:group['lr']=self.lr()
            first=0 if c.method=='single' else index*c.microbatch*c.accumulation
            count=windows if c.method=='single' else c.microbatch*c.accumulation
            micro_count=count//c.microbatch
            for offset in range(first,first+count,c.microbatch):
                batch=torch.from_numpy(ids[offset:offset+c.microbatch]).to(self.device)
                with self.attention(),self.context():loss=model.loss(batch)
                if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
                mean+=float(loss.detach())/((windows//c.microbatch))
                scaler.scale(loss/micro_count).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
            scaler.step(opt);scaler.update();opt.zero_grad(set_to_none=True)
        self.cursor+=windows;self.tokens+=self.targets;self.global_step+=1
        self.ledger=hashlib.sha256(bytes.fromhex(self.ledger)+ids.astype('<u2').tobytes()).hexdigest()
        if c.method!='single' and self.global_step%c.local_steps==0:
            delta=torch.zeros_like(self.parent)
            for m in self.models:delta.add_((self.parent-parameters_to_vector(m.parameters()).detach())/c.workers)
            if not torch.isfinite(delta).all():raise ValueError('Nonfinite outer delta')
            if c.method=='fedavg':updated=self.parent-delta
            else:
                self.velocity.mul_(c.momentum).add_(delta)
                updated=self.parent-c.outer_lr*(delta+c.momentum*self.velocity)
            if not torch.isfinite(updated).all():raise ValueError('Nonfinite canonical update')
            with torch.no_grad():
                vector_to_parameters(updated.clone(),self.server.parameters())
                for m in self.models:vector_to_parameters(updated.clone(),m.parameters())
            self.parent=updated.detach().clone();self.outer_updates+=1
        elif c.method=='single':self.parent=parameters_to_vector(self.server.parameters()).detach().clone()
        return mean
    def state(self):
        return {'schema':1,'model_config':asdict(self.mc),'training_config':asdict(self.tc),
                'environment':{'torch':str(torch.__version__),'python':platform.python_version(),'device_type':self.device.type},
                'manifest_sha256':self.stream.manifest_hash,'split':self.stream.split,
                'global_step':self.global_step,'cursor':self.cursor,'tokens':self.tokens,'outer_updates':self.outer_updates,'ledger':self.ledger,
                'server':self.server.state_dict(),'models':[m.state_dict() for m in self.models],
                'optimizers':[o.state_dict() for o in self.opts],'scalers':[s.state_dict() for s in self.scalers],
                'parent':self.parent,'velocity':self.velocity,'python_rng':random.getstate(),'torch_rng':torch.get_rng_state(),
                'cuda_rng':torch.cuda.get_rng_state_all() if self.device.type=='cuda' else [],
                'boundary':'completed global optimizer step; no pending gradients; in-round learner differences preserved'}
    def restore(self,state):
        expected=self.state()
        for key in ('schema','model_config','training_config','environment','manifest_sha256','split'):
            if state.get(key)!=expected[key]:raise ValueError('Resume identity mismatch: '+key)
        step=state['global_step'];cursor=state['cursor'];tokens=state['tokens']
        if type(step) is not int or step<0 or tokens!=step*self.targets or cursor*self.mc.context!=tokens or tokens>self.tc.total_tokens:
            raise ValueError('Resume token/cursor mismatch')
        if cursor>self.stream.windows or state['outer_updates']!=(0 if self.tc.method=='single' else step//self.tc.local_steps):
            raise ValueError('Resume round mismatch')
        for key in ('models','optimizers','scalers'):
            if len(state[key])!=len(self.models):raise ValueError('Resume worker count mismatch')
        if state['parent'].shape!=self.parent.shape or state['velocity'].shape!=self.velocity.shape:raise ValueError('Resume anchor shape mismatch')
        self.server.load_state_dict(state['server'],strict=True)
        for m,s in zip(self.models,state['models']):m.load_state_dict(s,strict=True)
        for opt,s in zip(self.opts,state['optimizers']):opt.load_state_dict(s)
        for scaler,s in zip(self.scalers,state['scalers']):scaler.load_state_dict(s)
        self.parent=state['parent'].to(self.device);self.velocity=state['velocity'].to(self.device)
        for key in ('global_step','cursor','tokens','outer_updates','ledger'):setattr(self,key,state[key])
        random.setstate(state['python_rng']);torch.set_rng_state(state['torch_rng'])
        if self.device.type=='cuda':torch.cuda.set_rng_state_all(state['cuda_rng'])
    def save(self,path):return snapshot.save(path,self.state())
    def load(self,path,sha):self.restore(snapshot.load(path,sha))
    def evaluate(self,stream,windows=16):
        if stream.split!='dev':raise ValueError('Only development evaluation is enabled; final test remains locked')
        if stream.manifest_hash!=self.stream.manifest_hash:raise ValueError('Evaluation corpus identity mismatch')
        if not 1<=windows<=256 or stream.context!=self.mc.context:raise ValueError('Evaluation limits')
        self.server.eval();total=0.
        try:
            with torch.no_grad(),self.attention(),self.context():
                for i in range(min(windows,stream.windows)):
                    b=torch.from_numpy(stream.window(i)[None,:]).to(self.device)
                    loss=self.server.loss(b)
                    if not torch.isfinite(loss):raise ValueError('Nonfinite evaluation')
                    total+=float(loss)
            return total/min(windows,stream.windows)
        finally:self.server.train()
