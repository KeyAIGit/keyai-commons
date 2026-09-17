"""Starts real separate OS processes. Never grants consent outside test data dirs."""
import json, pathlib, subprocess, time, urllib.request, urllib.error, tempfile, sys
from urllib.parse import urlsplit
ROOT=pathlib.Path(__file__).resolve().parent
BIN=ROOT/('KeyAI-Commons.exe' if sys.platform=='win32' else 'keyai-commons')
logs=[]; procs=[]; checks=[]
def wait_file(p,seconds=10):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if p.exists():
            try:return json.loads(p.read_text())
            except (OSError,json.JSONDecodeError):pass
        time.sleep(.1)
    raise AssertionError('missing session file: '+str(p))
def request(url,path,body=None):
    u=urlsplit(url); base=f'{u.scheme}://{u.netloc}';headers={'Content-Type':'application/json'}
    if u.fragment:headers['X-Session-Token']=u.fragment
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(base+path,data=data,headers=headers)
    with urllib.request.urlopen(req,timeout=12) as r:return json.load(r)
def wait(fn,seconds=20):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if fn():return
        time.sleep(.15)
    raise AssertionError('condition timed out')
def check(name,condition):
    assert condition,name
    checks.append({'name':name,'pass':True});print('PASS',name,flush=True)
def start(args):
    f=tempfile.TemporaryFile();logs.append(f)
    p=subprocess.Popen([str(BIN),*args],stdout=f,stderr=subprocess.STDOUT);procs.append(p);return p
try:
    with tempfile.TemporaryDirectory(prefix='keyai-integration-') as d:
        d=pathlib.Path(d);co=d/'coordinator'
        p=start(['coordinator','--listen','127.0.0.1:0','--data',str(co),'--no-browser'])
        op=wait_file(co/'operator-session-private.json');admin=op['admin_url'];clients=[]
        for i in range(3):
            cd=d/f'client{i}';start(['client','--data',str(cd),'--no-browser']);ui=wait_file(cd/'local-session-private.json')['ui_url'];clients.append(ui)
            request(ui,'/api/connect',{'code':op['connection_code']})
        wait(lambda:request(admin,'/api/status')['online']==3)
        check('Three separate participant processes register',request(admin,'/api/status')['registered']==3)
        check('Launch does not grant consent',all(not request(u,'/api/status')['consent'] for u in clients))
        request(admin,'/api/start',{'steps':800,'nodes':3,'seconds':60});time.sleep(2.3)
        check('Operator command alone cannot start clients',request(admin,'/api/status')['round']['assigned']==0)
        request(admin,'/api/stop',{})
        for u in clients:request(u,'/api/consent',{'allow':True,'minutes':5,'acknowledged':True})
        wait(lambda:request(admin,'/api/status')['ready']==3)
        check('Ready clients remain idle without a campaign',all(not request(u,'/api/status')['busy'] for u in clients))
        before=request(admin,'/api/status');request(admin,'/api/start',{'steps':800,'nodes':3,'seconds':60})
        wait(lambda:all(request(u,'/api/status')['busy'] for u in clients))
        check('Signed campaign starts all three clients',True)
        wait(lambda:request(admin,'/api/status')['model_version']==1)
        after=request(admin,'/api/status')
        check('Three real processes produce one aggregate',after['history'][-1]['participants']==3)
        check('Global model loss decreases',after['loss']<before['loss'])
        check('Global model hash changes',after['model_hash']!=before['model_hash'])
        check('No double contribution',after['verified_contributions']==3)
        request(admin,'/api/start',{'steps':1200,'nodes':3,'seconds':60})
        wait(lambda:all(request(u,'/api/status')['busy'] for u in clients))
        t=time.monotonic();request(clients[0],'/api/pause',{});wait(lambda:not request(clients[0],'/api/status')['busy'],2)
        pause_ms=round((time.monotonic()-t)*1000,1);check('Local pause cancels an in-flight job',not request(clients[0],'/api/status')['consent'])
        request(admin,'/api/stop',{});wait(lambda:all(not request(u,'/api/status')['busy'] for u in clients),10)
        check('Operator stop reaches remaining processes',True)
        check('Stopped round does not mutate the model',request(admin,'/api/status')['model_version']==1)
        for u in clients:request(u,'/api/exit',{})
        wait(lambda:all(p.poll() is not None for p in procs[1:]))
        check('Exit shuts down participant processes',True)
        report={'passed':len(checks),'checks':checks,'before':{'loss':before['loss'],'accuracy':before['accuracy']},'after':{'loss':after['loss'],'accuracy':after['accuracy'],'model_version':after['model_version'],'participants':3},'pause_observed_ms':pause_ms,'scope':'3 processes on one Linux host; not 3 physical computers; CPU synthetic workload'}
        (ROOT/'integration-results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
finally:
    for p in procs:
        if p.poll() is None:p.terminate()
    for p in procs:
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill()
    for f in logs:f.close()
