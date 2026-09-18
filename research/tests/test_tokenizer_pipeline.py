"""Small deterministic data pipeline tests; no network download or GPU work."""
import hashlib, json, tempfile, unittest
from pathlib import Path
from commons_lab import data

class TokenizerPipelineTests(unittest.TestCase):
    def fixture(self,folder):
        train=['A child named Mia saw '+str(i)+' bright little birds in the garden.' for i in range(1200)]
        dev=next('A development story '+str(i) for i in range(2000) if data.train_role(data.content_id('A development story '+str(i)))=='dev')
        held=['UNIQUE-HELDOUT-CONTENT-7391','Another independent held-out sentence.']
        spec={'repository':'synthetic-tests-only','files':[]}
        for name,values in [('train.txt',train+[dev,held[0]]),('valid.txt',held)]:
            p=folder/name;p.write_text(''.join(t+'\n<|endoftext|>\n' for t in values),encoding='utf8')
            spec['files'].append({'rfilename':name,'size':p.stat().st_size,'sha256':data.digest_file(p)})
        data.index_corpus(folder,spec,folder/'index')
        return folder/'index',held
    def test_training_only_and_two_builds_match(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);index,held=self.fixture(d)
            a=data.fit_tokenizer(index,d/'a.json',examples=100,vocab=300)
            b=data.fit_tokenizer(index,d/'b.json',examples=100,vocab=300)
            self.assertEqual(a,b);self.assertEqual((d/'a.json').read_bytes(),(d/'b.json').read_bytes())
            conn,_=data.read_index(index)
            rows=list(conn.execute("SELECT h FROM stories WHERE role='train' ORDER BY h LIMIT 100"));conn.close()
            ids=[h for (h,) in rows];self.assertEqual(a['training_ids_sha256'],hashlib.sha256(b''.join(ids)).hexdigest())
            self.assertTrue(all(data.content_id(t) not in ids for t in held))
    def test_full_pipeline_repeat_and_cross_split_exclusion(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);index,_=self.fixture(d);info=data.fit_tokenizer(index,d/'tok.json',100,300)
            a=data.tokenize_corpus(index,d/'tok.json',d/'tokens-a',info,context=16)
            b=data.tokenize_corpus(index,d/'tok.json',d/'tokens-b',info,context=16)
            self.assertEqual(a,b);self.assertEqual(data.digest_file(d/'tokens-a/manifest.json'),data.digest_file(d/'tokens-b/manifest.json'))
            sets=[]
            for split in ['train','dev','test']:
                sets.append(set((d/'tokens-a'/a['splits'][split]['story_hashes']['file']).read_text().splitlines()))
                s=data.TokenStream(d/'tokens-a',split,data.digest_file(d/'tokens-a/manifest.json'),16)
                self.assertEqual(len(s.window(0)),17);self.assertEqual(s.window(0).tolist(),data.TokenStream(d/'tokens-b',split,data.digest_file(d/'tokens-b/manifest.json'),16).window(0).tolist())
            self.assertFalse(sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
    def test_byte_roundtrip_and_special_ids(self):
        from tokenizers import Tokenizer
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);index,_=self.fixture(d);data.fit_tokenizer(index,d/'t',100,300);tok=Tokenizer.from_file(str(d/'t'))
            self.assertEqual([tok.token_to_id(s) for s in data.SPECIAL],list(range(4)))
            text='Привет, café! 日本語\nZero 123.'
            self.assertEqual(tok.decode(tok.encode(text,add_special_tokens=False).ids),text)
    def test_changed_tokenizer_prevents_preparation(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);index,_=self.fixture(d);info=data.fit_tokenizer(index,d/'t',100,300);info['file_sha256']='0'*64
            with self.assertRaises(ValueError):data.tokenize_corpus(index,d/'t',d/'tokens',info)
            self.assertFalse((d/'tokens/manifest.json').exists())
if __name__=='__main__':unittest.main()
