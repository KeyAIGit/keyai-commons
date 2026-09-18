import array,copy,hashlib,json,os,random,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from commons_lab import data,snapshot
from commons_lab.config import ModelConfig
from commons_lab.engine import Engine,TrainConfig

torch.set_num_threads(2)
class FakeStream:
    context=16;windows=4096;manifest_hash='a'*64;split='train'
    def window(self,n):return np.asarray([(n+i)%24+4 for i in range(17)],dtype=np.int64)

def engine(mode='diloco'):
    return Engine(ModelConfig(vocab_size=32,width=32,layers=2,heads=4,kv_heads=2,ff_width=64,context=16),
                  TrainConfig(method=mode,workers=2,microbatch=1,accumulation=2,local_steps=4,total_tokens=1024,seed=11),FakeStream())

def equal(a,b):
    if isinstance(a,torch.Tensor):return torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return type(a)==type(b) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b

class DataTests(unittest.TestCase):
    def test_unicode_and_newlines(self):self.assertEqual(data.content_id(' e\u0301\r\na '),data.content_id('é\na'))
    def test_story_bounds_and_final_delimiter(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.txt';p.write_text('a\n<|endoftext|>\nb\n<|endoftext|>\n')
            self.assertEqual(list(data.stories(p)),['a','b'])
            with self.assertRaises(ValueError):list(data.stories(p,1))
            p.write_text('unfinished')
            with self.assertRaises(ValueError):list(data.stories(p))
    def test_audited_unterminated_source_fragment_is_not_trained(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw';p.write_text('complete\n<|endoftext|>\nunfinished')
            dropped=[]
            self.assertEqual(list(data.stories(p,dropped=dropped)),['complete'])
            self.assertEqual(len(dropped),1)
            self.assertEqual(dropped[0]['sha256'],data.content_id('unfinished').hex())
            self.assertEqual(dropped[0]['normalized_bytes'],10)
    def test_embedded_delimiter_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('a<|endoftext|>b')
            with self.assertRaises(ValueError):list(data.stories(p))
    def test_split_precedence_and_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);dev=next('s'+str(i) for i in range(10000) if data.train_role(data.content_id('s'+str(i)))=='dev')
            tr=next('t'+str(i) for i in range(100) if data.train_role(data.content_id('t'+str(i)))=='train')
            spec={'files':[]}
            for name,items in [('valid.txt',['held']),('train.txt',['held',tr,tr,dev])]:
                p=d/name;p.write_text(''.join(s+'\n<|endoftext|>\n' for s in items))
                spec['files'].append({'rfilename':name,'size':p.stat().st_size,'sha256':data.digest_file(p)})
            r=data.index_corpus(d,spec,d/'db');self.assertEqual(r['unique'],{'dev':1,'test':1,'train':1});self.assertEqual(r['train_excluded_by_final'],1)
            con,_=data.read_index(d/'db');self.assertEqual(con.execute('SELECT COUNT(*) FROM stories').fetchone()[0],3);con.close()
    def test_raw_hash_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);p=d/'a';p.write_text('x')
            with self.assertRaises(ValueError):data.index_corpus(d,{'files':[{'rfilename':'a','size':1,'sha256':'0'*64}]},d/'db')
    def corpus(self,d,ids=list(range(26))):
        w=data.ChunkWriter(d,'train',limit=7,vocab=32);w.append(ids);w.flush()
        m={'dtype':'uint16-le','context':4,'tokenizer':{'vocab_size':32},'splits':{'train':{'chunks':w.entries,'ids':len(ids),'windows':(len(ids)-1)//4}}}
        data.write_json(d/'manifest.json',m);return data.digest_file(d/'manifest.json')
    def test_cross_chunk_no_repeated_targets(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);h=self.corpus(d);s=data.TokenStream(d,'train',h,context=4)
            self.assertEqual([v for i in range(s.windows) for v in s.window(i)[1:] ],list(range(1,25)))
            with self.assertRaises(IndexError):s.window(s.windows)
    def test_chunk_invalid_id_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);w=data.ChunkWriter(d,'train',limit=8,vocab=32)
            for ids in [[-1],[32],[True],[1.5]]:
                with self.assertRaises(ValueError):w.append(ids)
            h=self.corpus(d);p=d/'train-00000.u16';p.write_bytes(b'x')
            with self.assertRaises(ValueError):data.TokenStream(d,'train',h,4)
    def test_partial_manifest_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'manifest.json.partial').write_text('{}')
            with self.assertRaises(FileNotFoundError):data.TokenStream(d,'train','0'*64,4)
    def test_bad_manifest_and_unsafe_path(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);h=self.corpus(d)
            with self.assertRaises(ValueError):data.TokenStream(d,'train','0'*64,4)
            m=json.loads((d/'manifest.json').read_text());m['splits']['train']['chunks'][0]['file']='../x'
            data.write_json(d/'manifest.json',m)
            with self.assertRaises(ValueError):data.TokenStream(d,'train',data.digest_file(d/'manifest.json'),4)

class ResumeTests(unittest.TestCase):
    def test_save_load_tree_no_pickle(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s';state={'t':torch.arange(7),'x':(None,True,2,1.5),'intkey':{1:'ok'}}
            h=snapshot.save(p,state);self.assertTrue(equal(snapshot.load(p,h),state))
            with self.assertRaises(FileExistsError):snapshot.save(p,state)
    def test_snapshot_nonfinite_unsupported(self):
        with tempfile.TemporaryDirectory() as d:
            for v in [float('nan'),torch.tensor(float('inf')),object()]:
                with self.assertRaises(ValueError):snapshot.save(Path(d)/'bad',{'v':v})
    def test_snapshot_integrity_and_interruption(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);p=d/'s';h=snapshot.save(p,{'v':torch.ones(2)})
            with patch('commons_lab.snapshot.save_file',side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):snapshot.save(d/'next',{'v':torch.ones(2)})
            self.assertTrue(equal(snapshot.load(p,h),{'v':torch.ones(2)}));self.assertFalse((d/'next').exists())
            p.write_bytes(p.read_bytes()[:-1]+b'x')
            with self.assertRaises(ValueError):snapshot.load(p,h)
    def test_full_state_resume_across_outer_update(self):
        for mode in ('single','fedavg','diloco'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
                a=engine(mode)
                for _ in range(3):a.step()
                p=Path(d)/'s';h=a.save(p)
                losses_a=[a.step() for _ in range(5)];ra=random.random();ta=torch.rand(3)
                b=engine(mode);b.load(p,h);losses_b=[b.step() for _ in range(5)]
                self.assertEqual(losses_a,losses_b)
                self.assertEqual(ra,random.random());self.assertTrue(torch.equal(ta,torch.rand(3)))
                self.assertTrue(equal(a.state(),b.state()))
    def test_resume_rejects_wrong_data_and_cursor(self):
        a=engine();a.step();state=copy.deepcopy(a.state())
        for key,value in [('manifest_sha256','x'*64),('cursor',123),('tokens',12),('outer_updates',1)]:
            bad=copy.deepcopy(state);bad[key]=value
            with self.assertRaises(ValueError):engine().restore(bad)
    def test_inner_optimizer_not_recreated_at_exchange(self):
        e=engine();ident=[id(o) for o in e.opts]
        for _ in range(4):e.step()
        self.assertEqual(ident,[id(o) for o in e.opts]);self.assertEqual(e.outer_updates,1)
        for o in e.opts:self.assertTrue(all(int(v['step'])==4 for v in o.state.values()))
    def test_same_data_ledger_all_methods(self):
        ledgers=[]
        for mode in ('single','fedavg','diloco'):
            e=engine(mode)
            for _ in range(4):e.step()
            ledgers.append(e.ledger)
        self.assertEqual(len(set(ledgers)),1)
    def test_final_test_locked_and_budget(self):
        e=engine();s=FakeStream();s.split='test'
        with self.assertRaises(ValueError):e.evaluate(s)
        e.tokens=e.tc.total_tokens
        with self.assertRaises(ValueError):e.step()
    def test_training_cannot_use_held_out_splits(self):
        for split in ('dev','test'):
            s=FakeStream();s.split=split
            with self.assertRaises(ValueError):Engine(ModelConfig(),TrainConfig(),s)
    def test_evaluation_requires_matching_dev_corpus(self):
        e=engine();s=FakeStream();s.split='dev';s.manifest_hash='b'*64
        with self.assertRaises(ValueError):e.evaluate(s)
        s.manifest_hash=e.stream.manifest_hash;s.split='train'
        with self.assertRaises(ValueError):e.evaluate(s)
    def test_new_process_resume(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);e=engine()
            for _ in range(3):e.step()
            h=e.save(d/'mid')
            for _ in range(5):e.step()
            expected=copy.deepcopy(e.state())
            code=f'''import sys;sys.path.insert(0,{str(Path(__file__).parent)!r})\nfrom test_data_resume import engine\ne=engine();e.load(__import__('pathlib').Path({str(d/'mid')!r}),{h!r})\nfor _ in range(5):e.step()\nprint(e.save(__import__('pathlib').Path({str(d/'end')!r})))'''
            r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30,check=True)
            resumed=snapshot.load(d/'end',r.stdout.strip().splitlines()[-1]);self.assertTrue(equal(expected,resumed))

if __name__=='__main__':unittest.main()
