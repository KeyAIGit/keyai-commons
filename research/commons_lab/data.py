"""Deterministic local-only TinyStories preparation. No runtime remote URLs.
Raw sources are fixed by research/configs/dataset-selection.json; publication of
any derived data retains CDLA-Sharing-1.0, attribution and modification notices.
"""
from __future__ import annotations
import argparse, array, bisect, hashlib, json, os, sqlite3, sys, time, unicodedata
from pathlib import Path

DELIMITER = '<|endoftext|>'
SPECIAL = ['<unk>', '<bos>', '<eos>', '<pad>']
CHUNK_IDS = 1_048_576


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''): h.update(block)
    return h.hexdigest()


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode()


def write_json(path: Path, value):
    """Atomic JSON commit in an already private local directory."""
    tmp = path.with_name(path.name+'.partial')
    with tmp.open('wb') as f: f.write(canonical(value)); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def normalize(story: str) -> str:
    return unicodedata.normalize('NFC', story.replace('\r\n','\n').replace('\r','\n')).strip()


def stories(path: Path, limit_bytes: int = 1 << 20, dropped: list | None = None):
    """Delimiter must be an exact standalone line. Reject a partial final story."""
    rows, size = [], 0
    with path.open('r', encoding='utf-8', errors='strict', newline=None) as f:
        for line in f:
            if line.rstrip('\r\n') == DELIMITER:
                text = normalize(''.join(rows))
                if text: yield text
                rows, size = [], 0
            else:
                if DELIMITER in line: raise ValueError('Non-standalone delimiter')
                size += len(line.encode('utf-8'))
                if size > limit_bytes: raise ValueError('Story exceeds size limit')
                rows.append(line)
    tail=normalize(''.join(rows))
    if tail:
        if dropped is None: raise ValueError('Unterminated final story')
        # Hash-verified upstream files themselves end without a delimiter.
        # Omit the fragment rather than guessing its completeness.
        dropped.append({'reason':'unterminated_upstream_final_fragment',
                        'normalized_bytes':len(tail.encode('utf-8')),
                        'sha256':hashlib.sha256(tail.encode('utf-8')).hexdigest()})


def content_id(text: str) -> bytes:
    return hashlib.sha256(normalize(text).encode('utf-8')).digest()


def train_role(digest: bytes) -> str:
    return 'dev' if int.from_bytes(digest,'big') % 1000 < 10 else 'train'


def index_corpus(raw: Path, selection: dict, output: Path) -> dict:
    if output.exists(): raise FileExistsError('Index exists; do not overwrite an experiment')
    for meta in selection['files']:
        p = raw / meta['rfilename']
        if p.stat().st_size != meta['size'] or digest_file(p) != meta['sha256']:
            raise ValueError('Raw size/hash mismatch: '+p.name)
    stage = output.with_name(output.name+'.partial')
    if stage.exists(): raise FileExistsError('Incomplete index exists; use a fresh output')
    conn = sqlite3.connect(stage)
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('PRAGMA temp_store=FILE')
    conn.execute('CREATE TABLE stories (h BLOB PRIMARY KEY, role TEXT NOT NULL, text TEXT NOT NULL) WITHOUT ROWID')
    counts = {'source_stories': {}, 'duplicates': {}, 'train_excluded_by_final': 0, 'omitted_final_fragments': {}}
    try:
        # Inserting held-out first guarantees priority irrespective of input order.
        files = sorted(selection['files'], key=lambda m: ('valid' not in m['rfilename'],m['rfilename']))
        for meta in files:
            final = 'valid' in meta['rfilename']; total = duplicates = 0
            omitted=[]
            for text in stories(raw/meta['rfilename'], dropped=omitted):
                h=content_id(text); role='test' if final else train_role(h)
                inserted=conn.execute('INSERT OR IGNORE INTO stories VALUES (?,?,?)',(h,role,text)).rowcount
                if not inserted:
                    duplicates+=1
                    if not final and conn.execute('SELECT role FROM stories WHERE h=?',(h,)).fetchone()[0]=='test':
                        counts['train_excluded_by_final']+=1
                total+=1
                if total>5_000_000: raise ValueError('Source exceeds record budget')
                if total%10000==0: conn.commit()
                if total%250000==0: print('INDEXED',meta['rfilename'],total,flush=True)
            counts['omitted_final_fragments'][meta['rfilename']]=omitted
            counts['source_stories'][meta['rfilename']]=total
            counts['duplicates'][meta['rfilename']]=duplicates
        conn.execute('CREATE INDEX by_role ON stories(role,h)')
        counts['unique']={r:n for r,n in conn.execute('SELECT role,COUNT(*) FROM stories GROUP BY role')}
        if not all(counts['unique'].get(r,0)>0 for r in ('train','dev','test')): raise ValueError('Missing data split')
        conn.execute('CREATE TABLE metadata (value TEXT NOT NULL)')
        conn.execute('INSERT INTO metadata VALUES (?)',(canonical({'selection':selection,'counts':counts}).decode(),))
        conn.commit(); conn.close(); os.replace(stage,output)
    except BaseException:
        conn.close(); raise
    return counts


def read_index(path: Path):
    conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    info=json.loads(conn.execute('SELECT value FROM metadata').fetchone()[0])
    return conn, info


def fit_tokenizer(index: Path, output: Path, examples: int = 50000, vocab: int = 8192) -> dict:
    from tokenizers import Tokenizer, models, pre_tokenizers, decoders, trainers
    import tokenizers
    if output.exists(): raise FileExistsError(output)
    if not 1<=examples<=50000 or not 260<=vocab<=65536: raise ValueError('Tokenizer limits')
    if tokenizers.__version__ != '0.22.1': raise ValueError('Expected tokenizers==0.22.1')
    conn, info = read_index(index)
    rows=conn.execute('SELECT h,text FROM stories WHERE role=? ORDER BY h LIMIT ?',('train',examples)).fetchall();conn.close()
    if len(rows)!=examples: raise ValueError('Not enough training stories')
    tok=Tokenizer(models.BPE(unk_token=SPECIAL[0]))
    tok.pre_tokenizer=pre_tokenizers.ByteLevel(add_prefix_space=False,use_regex=True)
    tok.decoder=decoders.ByteLevel()
    trainer=trainers.BpeTrainer(vocab_size=vocab,min_frequency=2,show_progress=False,
                               special_tokens=SPECIAL,initial_alphabet=sorted(pre_tokenizers.ByteLevel.alphabet()))
    tok.train_from_iterator((text for _,text in rows),trainer=trainer,length=len(rows))
    if tok.get_vocab_size()!=vocab: raise ValueError('Tokenizer did not reach exact vocabulary')
    for i,s in enumerate(SPECIAL):
        if tok.token_to_id(s)!=i: raise ValueError('Special-token mismatch')
    tmp=output.with_name(output.name+'.partial');tok.save(str(tmp));os.replace(tmp,output)
    return {'implementation':'tokenizers','version':tokenizers.__version__,'vocab_size':vocab,'special_tokens':SPECIAL,
            'train_stories':examples,'training_ids_sha256':hashlib.sha256(b''.join(h for h,_ in rows)).hexdigest(),
            'file_sha256':digest_file(output),'unicode_version':unicodedata.unidata_version}


class ChunkWriter:
    def __init__(self, folder: Path, split: str, limit: int = CHUNK_IDS, vocab: int=8192):
        if not 1<=limit<=CHUNK_IDS or split not in ('train','dev','test'): raise ValueError('Chunk limits')
        self.folder,self.split,self.limit,self.vocab=folder,split,limit,vocab
        self.buffer=array.array('H');self.entries=[];self.total=0
    def append(self, ids):
        if any(type(v) is not int or not 0<=v<self.vocab for v in ids): raise ValueError('Invalid token')
        for start in range(0,len(ids),self.limit):
            part=ids[start:start+self.limit]
            while part:
                take=min(self.limit-len(self.buffer),len(part))
                self.buffer.extend(part[:take]);part=part[take:]
                if len(self.buffer)==self.limit:self.flush()
    def flush(self):
        if not self.buffer:return
        n=len(self.buffer)
        if sys.byteorder!='little': self.buffer.byteswap()
        raw=self.buffer.tobytes(); name=f'{self.split}-{len(self.entries):05d}.u16'
        final=self.folder/name;temp=self.folder/(name+'.partial')
        with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,final)
        self.entries.append({'file':name,'ids':n,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        self.total+=n;self.buffer=array.array('H')


def tokenize_corpus(index: Path, tokenizer: Path, folder: Path, tok_info: dict, context: int=512) -> dict:
    from tokenizers import Tokenizer
    if folder.exists(): raise FileExistsError(folder)
    folder.mkdir();tok=Tokenizer.from_file(str(tokenizer));conn,info=read_index(index)
    if digest_file(tokenizer)!=tok_info['file_sha256']: raise ValueError('Tokenizer changed')
    report={'schema':1,'preparation':'commons-tinystories-v1','source':info['selection'],'index_counts':info['counts'],
            'tokenizer':tok_info,'dtype':'uint16-le','context':context,'chunk_max_ids':CHUNK_IDS,
            'normalization':'UTF-8 strict; universal LF; Unicode NFC; strip outer whitespace; omit recorded unterminated final fragments from hash-verified sources',
            'split':'Final source wins; int(SHA256(normalized UTF8),big) % 1000 < 10 => dev; otherwise train',
            'ordering':'lexicographic SHA256 bytes within each split; EOS ID=2 after each story',
            'license':'CDLA-Sharing-1.0','attribution':'Ronen Eldan and Yuanzhi Li; roneneldan/TinyStories',
            'modifications':'Exact deduplication, content-hash split, NFC normalization, BPE encoding; not upstream original files',
            'near_duplicate_audit':'NOT_PERFORMED; exact matching is not semantic contamination detection','splits':{}}
    for split in ('train','dev','test'):
        writer=ChunkWriter(folder,split,vocab=tok.get_vocab_size()); hashes=folder/(split+'-story-sha256.txt')
        count=0;cursor=conn.execute('SELECT h,text FROM stories WHERE role=? ORDER BY h',(split,))
        with hashes.open('xb') as ledger:
            while batch:=cursor.fetchmany(256):
                texts=[s for _,s in batch]
                encoded=tok.encode_batch(texts,add_special_tokens=False)
                for (h,_),item in zip(batch,encoded):
                    writer.append(item.ids+[2]);ledger.write(h.hex().encode()+b'\n');count+=1
                if count%65536==0:print('TOKENIZED',split,count,writer.total+len(writer.buffer),flush=True)
            ledger.flush();os.fsync(ledger.fileno())
        writer.flush();windows=(writer.total-1)//context
        report['splits'][split]={'stories':count,'ids':writer.total,'windows':windows,'scored_targets_per_epoch':windows*context,
                                 'unscored_first_id':1,'tail_unscored_ids':writer.total-1-windows*context,
                                 'story_hashes':{'file':hashes.name,'sha256':digest_file(hashes)},'chunks':writer.entries}
    conn.close()
    # Commit only after all chunks and story ledgers are durably written.
    write_json(folder/'manifest.json',report)
    return report


class TokenStream:
    """Read-only local corpus; verifies files before use. No per-chunk padding.
    A window may cross chunks but a target token is never counted twice.
    """
    def __init__(self, folder: Path, split: str, manifest_hash: str, context: int=512):
        import numpy as np
        if split not in ('train','dev','test'): raise ValueError('Bad split')
        if digest_file(folder/'manifest.json')!=manifest_hash: raise ValueError('Manifest hash mismatch')
        m=json.loads((folder/'manifest.json').read_text())
        if m['dtype']!='uint16-le' or m['context']!=context: raise ValueError('Corpus layout mismatch')
        self.context=context;self.maps=[];self.starts=[0];self.manifest_hash=manifest_hash;self.split=split
        for e in m['splits'][split]['chunks']:
            if Path(e['file']).name!=e['file']: raise ValueError('Unsafe chunk path')
            p=folder/e['file']
            if p.is_symlink() or e['ids']<=0 or e['bytes']!=e['ids']*2 or p.stat().st_size!=e['bytes'] or digest_file(p)!=e['sha256']:
                raise ValueError('Chunk integrity mismatch')
            a=np.memmap(p,dtype='<u2',mode='r')
            if int(a.max())>=m['tokenizer']['vocab_size']:raise ValueError('Out-of-range token')
            self.maps.append(a);self.starts.append(self.starts[-1]+len(a))
        if self.starts[-1]!=m['splits'][split]['ids']: raise ValueError('Token count mismatch')
        self.windows=(self.starts[-1]-1)//context
        if self.windows!=m['splits'][split]['windows'] or self.windows<=0:raise ValueError('Window count mismatch')
    def window(self, number: int):
        import numpy as np
        if type(number) is not int or not 0<=number<self.windows: raise IndexError('Window outside corpus')
        pos=number*self.context;end=pos+self.context+1;pieces=[]
        while pos<end:
            i=bisect.bisect_right(self.starts,pos)-1;stop=min(end,self.starts[i+1])
            pieces.append(self.maps[i][pos-self.starts[i]:stop-self.starts[i]]);pos=stop
        return np.concatenate(pieces).astype('int64')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw',type=Path,required=True);p.add_argument('--selection',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--stage',choices=['index','tokenizer','encode'],required=True)
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    if a.stage=='index':result=index_corpus(a.raw,json.loads(a.selection.read_text()),a.work/'stories.sqlite')
    elif a.stage=='tokenizer':
        result=fit_tokenizer(a.work/'stories.sqlite',a.work/'tokenizer.json')
        repeat=fit_tokenizer(a.work/'stories.sqlite',a.work/'tokenizer-repeat.json')
        if result!=repeat:raise ValueError('Tokenizer not reproducible under repeat build')
        write_json(a.work/'tokenizer-info.json',result)
    else:result=tokenize_corpus(a.work/'stories.sqlite',a.work/'tokenizer.json',a.work/'tokens',json.loads((a.work/'tokenizer-info.json').read_text()))
    print(json.dumps({k:v for k,v in result.items() if k!='splits'},indent=2),flush=True)
    if a.stage=='encode':print('PREPARED_MANIFEST_SHA256',digest_file(a.work/'tokens/manifest.json'),flush=True)
if __name__=='__main__':main()
