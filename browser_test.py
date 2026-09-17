import pathlib,subprocess,tempfile,json,time,os
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect
root=pathlib.Path(__file__).resolve().parent
out=root/'preview';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='keyai-browser-') as d:
 d=pathlib.Path(d);log=tempfile.TemporaryFile();p=subprocess.Popen([str(root/'keyai-commons'),'demo','--data',str(d),'--no-browser'],stdout=log,stderr=subprocess.STDOUT)
 try:
  op=d/'coordinator'/'operator-session-private.json';cl=d/'participant'/'local-session-private.json'
  for _ in range(100):
   if op.exists() and cl.exists():break
   time.sleep(.1)
  admin=json.loads(op.read_text())['admin_url'];client=json.loads(cl.read_text())['ui_url']
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('COMMONS_BROWSER'),args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':1440,'height':1040},device_scale_factor=1)
   errors=[];a=ctx.new_page();u=ctx.new_page()
   for page in [a,u]:page.on('pageerror',lambda e:errors.append(str(e)))
   a.goto(admin);u.goto(client);expect(u.locator('#connection')).to_have_text('Connected', timeout=30000)
   assert u.locator('#allow').is_disabled()
   u.locator('#agree').check();u.locator('#allow').click()
   expect(a.locator('#ready')).to_have_text('1', timeout=30000)
   a.locator('#start').click();expect(u.locator('#status')).to_have_text('Training an approved task', timeout=30000)
   time.sleep(.6);u.screenshot(path=str(out/'participant.png'),full_page=True)
   expect(a.locator('#modelversion')).to_have_text('Version 1', timeout=30000);a.screenshot(path=str(out/'operator.png'),full_page=True)
   u.locator('#pause').click();expect(u.locator('#status')).to_have_text('Paused. You are in control.', timeout=10000)
   u.set_viewport_size({'width':390,'height':844});u.screenshot(path=str(out/'participant-mobile.png'),full_page=True)
   assert u.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),'mobile horizontal overflow'
   assert not errors,errors
   print(json.dumps({'passed':7,'checks':['consent button gated by checkbox','participant consents via actual UI','operator launches via actual UI','real task visible in client','global checkpoint shown','pause via UI','mobile layout no overflow'],'page_errors':errors,'browser':'headless Chromium Linux'},indent=2))
   u.locator('#exit').click();u.wait_for_selector('text=Application closed.')
   browser.close()
 finally:
  if p.poll() is None:p.terminate()
  p.wait(timeout=5);log.close()
