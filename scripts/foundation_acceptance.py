"""Real loopback browser/process acceptance. No Internet worker, GPU or training.
Run in a normal developer/CI browser; does not change browser security policy.
"""
import functools,hashlib,http.server,json,os,pathlib,subprocess,sys,tempfile,threading,time,urllib.request
from playwright.sync_api import sync_playwright,expect
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'preview/foundation';OUT.mkdir(parents=True,exist_ok=True)
BINARY=pathlib.Path(os.environ.get('COMMONS_COMMUNITY_BINARY',str(ROOT/('KeyAI-Community.exe' if sys.platform=='win32' else 'keyai-community'))))
checks=[]
def ck(name,condition=True):
    assert condition,name
    checks.append(name)
def get_session(d):
    path=d/'community-session-private.json'
    for _ in range(100):
        if path.exists():
            try:return json.loads(path.read_text())['ui_url']
            except json.JSONDecodeError:pass
        time.sleep(.1)
    raise AssertionError('Community session not available')
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def contrast(a,b):
    def lum(c):
        rgb=[int(c[i:i+2],16)/255 for i in [1,3,5]]
        v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
        return sum(x*y for x,y in zip(v,[.2126,.7152,.0722]))
    x,y=sorted([lum(a),lum(b)]);return (y+.05)/(x+.05)

def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'src/web')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    if not BINARY.exists():subprocess.run(['go','build','-trimpath','-o',str(BINARY),'./cmd/community'],cwd=ROOT/'src',check=True)
    processes=[];errors=[];network=[]
    try:
        with tempfile.TemporaryDirectory(prefix='commons-community-test-') as td,sync_playwright() as pw:
            data=pathlib.Path(td); log=tempfile.TemporaryFile()
            def launch():
                p=subprocess.Popen([str(BINARY),'--data',str(data),'--no-browser'],stdout=log,stderr=log);processes.append(p);return p
            p=launch();ui=get_session(data)
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('COMMONS_BROWSER'),args=['--no-sandbox'])
            ctx=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:network.append(r.url))
            page.goto(f'http://127.0.0.1:{server.server_port}/landing.html')
            for lang in ['en','ru']:
                if page.locator('html').get_attribute('lang')!=lang:page.locator('#lang').click()
                for width in [320,390,768,1024,1440]:
                    page.set_viewport_size({'width':width,'height':1000})
                    ck(f'landing {lang} {width}: reflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    ck(f'landing {lang} {width}: text size',page.evaluate('parseFloat(getComputedStyle(document.body).fontSize)>=20'))
                page.screenshot(path=str(OUT/f'website-{lang}.png'),full_page=True)
            ck('white background',page.evaluate('getComputedStyle(document.body).backgroundColor')=='rgb(255, 255, 255)')
            ck('primary text contrast',contrast('#122338','#ffffff')>=4.5)
            ck('secondary text contrast',contrast('#465971','#ffffff')>=4.5)
            ck('no public download CTA',page.locator('a[href*="releases/download"]').count()==0)
            page.locator('#notification-preview').click();expect(page.locator('#notification')).to_be_visible();ck('notification preview opens')
            page.keyboard.press('Escape');expect(page.locator('#notification')).to_be_hidden();ck('notification preview escape closes')
            page.locator('#globe').scroll_into_view_if_needed()
            yaw=float(page.locator('#globe').get_attribute('data-yaw'));page.wait_for_timeout(250)
            ck('reduced motion stationary',float(page.locator('#globe').get_attribute('data-yaw'))==yaw)
            page.emulate_media(reduced_motion='no-preference');page.wait_for_timeout(500)
            yaw2=float(page.locator('#globe').get_attribute('data-yaw'));ck('automatic rotation advances',yaw2>yaw)
            box=page.locator('#globe').bounding_box();x,y=box['x']+box['width']/2,box['y']+box['height']/2
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+80,y+70,steps=6);page.mouse.up()
            tilted=float(page.locator('#globe').get_attribute('data-pitch'));page.wait_for_timeout(2200)
            returned=float(page.locator('#globe').get_attribute('data-pitch'))
            ck('spring returns pitch',abs(returned-.16)<abs(tilted-.16))
            page.locator('#motion').click();yaw3=float(page.locator('#globe').get_attribute('data-yaw'));page.wait_for_timeout(200)
            ck('manual pause holds',yaw3==float(page.locator('#globe').get_attribute('data-yaw')))
            app=ctx.new_page();app.on('pageerror',lambda e:errors.append(str(e)));app.on('request',lambda r:network.append(r.url));app.goto(ui)
            expect(app.locator('#saved')).to_contain_text('Computing is off')
            ck('no training controls',app.locator('select,#allow,#start,#discover').count()==0)
            for lang in ['en','ru']:
                if app.locator('html').get_attribute('lang')!=lang:app.locator('#lang').click()
                for width in [320,390,768,1024,1440]:
                    app.set_viewport_size({'width':width,'height':1000})
                    ck(f'community {lang} {width}: reflow',app.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                app.screenshot(path=str(OUT/f'community-{lang}.png'),full_page=True)
            app.locator('#interest').check();app.locator('#save').click();expect(app.locator('#saved')).to_contain_text('только')
            ck('local preference true',json.loads((data/'community-preference.json').read_text())=={'interested':True})
            app.locator('#exit').click();p.wait(timeout=4);ck('exit terminates process',p.returncode==0)
            p=launch();ui2=get_session(data);ck('new local credential',ui2!=ui)
            app.goto(ui2);expect(app.locator('#interest')).to_be_checked();ck('interest survives restart without training')
            token=ui2.split('#')[1];base=ui2.split('/#')[0]
            req=urllib.request.Request(base+'/api/status',headers={'X-Session-Token':token})
            state=json.loads(urllib.request.urlopen(req,timeout=5).read())
            ck('no permissions after restart',state['training_enabled'] is False and state['campaign_consent'] is False and state['registered'] is False)
            app.locator('#reset').click();expect(app.locator('#interest')).not_to_be_checked();ck('clear removes preference',not(data/'community-preference.json').exists())
            app.locator('#exit').click();p.wait(timeout=4)
            ck('only local network requests',all(u.startswith('http://127.0.0.1:') for u in network))
            ck('no JS errors',not errors);browser.close();log.close()
    finally:
        for p in processes:
            if p.poll() is None:p.terminate();p.wait(timeout=4)
        server.shutdown()
    report={'passed':len(checks),'checks':checks,'page_errors':errors,'scope':'real loopback HTTP, one community process restarted, no remote training or native notification tests','source_sha256':hashlib.sha256((ROOT/'src/web/landing.html').read_bytes()).hexdigest()}
    (OUT/'acceptance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
