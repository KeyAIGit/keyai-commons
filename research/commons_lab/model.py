"""Inspectable dense decoder reference; not a new model architecture.
Uses PyTorch SDPA, RMSNorm, RoPE, GQA, SwiGLU and tied embeddings.
Random initialization only; no external weights, dynamic code or downloads.
"""
from .config import ModelConfig
import math
import torch
from torch import nn
from torch.nn import functional as F

class RMSNorm(nn.Module):
    def __init__(self, width, eps):
        super().__init__(); self.weight=nn.Parameter(torch.ones(width)); self.eps=eps
    def forward(self,x):
        z=x.float(); z=z*torch.rsqrt(z.square().mean(-1,keepdim=True)+self.eps)
        return z.to(x.dtype)*self.weight.to(x.dtype)

def apply_rope(x, theta):
    # Adjacent-pair convention. Numerically equivalent family, not a claim of
    # binary checkpoint compatibility with any third-party weight layout.
    n,d=x.shape[-2:]; positions=torch.arange(n,device=x.device,dtype=torch.float32)
    inv=theta**(-torch.arange(0,d,2,device=x.device,dtype=torch.float32)/d)
    angle=positions[:,None]*inv[None,:]
    c,s=angle.cos().to(x.dtype),angle.sin().to(x.dtype)
    even,odd=x[...,0::2],x[...,1::2]
    return torch.stack((even*c-odd*s,even*s+odd*c),dim=-1).flatten(-2)

class Block(nn.Module):
    def __init__(self,cfg):
        super().__init__(); self.cfg=cfg; w=cfg.width; self.d=w//cfg.heads
        self.n1=RMSNorm(w,cfg.norm_eps); self.n2=RMSNorm(w,cfg.norm_eps)
        self.q=nn.Linear(w,w,bias=False); self.k=nn.Linear(w,self.d*cfg.kv_heads,bias=False)
        self.v=nn.Linear(w,self.d*cfg.kv_heads,bias=False); self.o=nn.Linear(w,w,bias=False)
        self.gate=nn.Linear(w,cfg.ff_width,bias=False); self.up=nn.Linear(w,cfg.ff_width,bias=False)
        self.down=nn.Linear(cfg.ff_width,w,bias=False)
    def forward(self,x):
        c=self.cfg; b,t,_=x.shape; z=self.n1(x)
        q=self.q(z).view(b,t,c.heads,self.d).transpose(1,2)
        k=self.k(z).view(b,t,c.kv_heads,self.d).transpose(1,2)
        v=self.v(z).view(b,t,c.kv_heads,self.d).transpose(1,2)
        q,k=apply_rope(q,c.rope_theta),apply_rope(k,c.rope_theta)
        k=k.repeat_interleave(c.heads//c.kv_heads,dim=1)
        v=v.repeat_interleave(c.heads//c.kv_heads,dim=1)
        a=F.scaled_dot_product_attention(q,k,v,dropout_p=0.0,is_causal=True)
        x=x+self.o(a.transpose(1,2).contiguous().view(b,t,c.width))
        z=self.n2(x); return x+self.down(F.silu(self.gate(z))*self.up(z))

class Decoder(nn.Module):
    def __init__(self,cfg):
        super().__init__(); cfg.validate(); self.cfg=cfg
        self.embedding=nn.Embedding(cfg.vocab_size,cfg.width)
        self.blocks=nn.ModuleList([Block(cfg) for _ in range(cfg.layers)])
        self.norm=RMSNorm(cfg.width,cfg.norm_eps)
        self.apply(self._init)
        # Residual projections use depth-scaled initialization, fixed in config docs.
        for block in self.blocks:
            nn.init.normal_(block.o.weight,std=.02/math.sqrt(2*cfg.layers))
            nn.init.normal_(block.down.weight,std=.02/math.sqrt(2*cfg.layers))
    @staticmethod
    def _init(m):
        if isinstance(m,(nn.Linear,nn.Embedding)): nn.init.normal_(m.weight,std=.02)
    def forward(self,tokens):
        if tokens.ndim!=2 or not 1 <= tokens.shape[1] <= self.cfg.context:
            raise ValueError('Expected bounded [batch, sequence] token IDs')
        x=self.embedding(tokens)
        for block in self.blocks:x=block(x)
        return F.linear(self.norm(x),self.embedding.weight)
    def loss(self,batch):
        if batch.ndim!=2 or batch.shape[1]<2:raise ValueError('At least two tokens needed')
        logits=self(batch[:,:-1]); return F.cross_entropy(logits.float().flatten(0,1),batch[:,1:].flatten())
