"""Requires local PyTorch; optional in the lightweight repo CI."""
import unittest
try:
    import torch
    from commons_lab.model import Decoder, apply_rope
    from commons_lab.config import ModelConfig
    from commons_lab.protocol import outer_step
    from commons_lab.sanity import batches
    HAVE_TORCH=True
except ModuleNotFoundError as error:
    if error.name!='torch':raise
    HAVE_TORCH=False

@unittest.skipUnless(HAVE_TORCH,'PyTorch is not installed; this is not a passing ML test')
class TorchTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2);torch.manual_seed(7)
        self.c=ModelConfig(vocab_size=64,width=64,layers=2,heads=4,kv_heads=2,ff_width=192,context=32)
        self.m=Decoder(self.c)
    def test_exact_small_count(self):self.assertEqual(sum(p.numel() for p in self.m.parameters()),self.c.parameter_count())
    def test_causality(self):
        a=torch.randint(0,64,(1,16));b=a.clone();b[:,8:]=(b[:,8:]+1)%64
        with torch.no_grad():x=self.m(a);y=self.m(b)
        self.assertTrue(torch.allclose(x[:,:8],y[:,:8],rtol=0,atol=1e-6))
    def test_rope_norm(self):
        x=torch.randn(2,4,16,16);r=apply_rope(x,10000.)
        self.assertTrue(torch.allclose(x.square().sum(-1),r.square().sum(-1),atol=1e-4))
    def test_gradient_finite(self):
        self.m.loss(torch.randint(0,64,(2,17))).backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in self.m.parameters()))
    def test_nesterov_matches_pytorch(self):
        x=torch.nn.Parameter(torch.tensor([10.,-3.],dtype=torch.float64))
        opt=torch.optim.SGD([x],lr=.7,momentum=.9,nesterov=True)
        expected=(10.,-3.);v=(0.,0.)
        for delta in ((2.,-1.),(.3,.1),(-.1,.2)):
            x.grad=torch.tensor(delta,dtype=torch.float64);opt.step()
            expected,v=outer_step(expected,v,delta)
            self.assertTrue(torch.allclose(x,torch.tensor(expected,dtype=torch.float64),atol=1e-12,rtol=0))
    def test_optimizer_state_survives_parameter_copy(self):
        opt=torch.optim.AdamW(self.m.parameters(),lr=.001)
        b=batches(9,1)[0];self.m.loss(b).backward();opt.step()
        p=next(self.m.parameters());state=opt.state[p]['exp_avg'].clone()
        with torch.no_grad():p.copy_(torch.zeros_like(p))
        self.assertTrue(torch.equal(opt.state[p]['exp_avg'],state))
    def test_synthetic_split_identity(self):
        train={tuple(x.tolist()) for i in range(64) for b in batches(11,i) for x in b}
        val={tuple(x.tolist()) for i in range(16) for b in batches(7001,i,split='validation') for x in b}
        self.assertFalse(train&val)
    def test_context_bound(self):
        with self.assertRaises(ValueError):self.m(torch.zeros(1,33,dtype=torch.long))
if __name__=='__main__':unittest.main()
