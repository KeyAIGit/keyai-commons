"""Browser acceptance for the public site. API fixtures are not live-network evidence.
Run after installing Playwright/Chromium. --local-render uses set_content for
managed browsers that cannot navigate to fixture URLs; network fixtures are skipped.
"""
import argparse, hashlib, json, os, pathlib
from playwright.sync_api import sync_playwright, expect
parser=argparse.ArgumentParser();parser.add_argument('--local-render',action='store_true');parser.add_argument('--html');parser.add_argument('--output');args=parser.parse_args()
ROOT=pathlib.Path(__file__).resolve().parents[1]
HTML=pathlib.Path(args.html) if args.html else ROOT/'src/web/landing.html'
OUT=pathlib.Path(args.output) if args.output else ROOT/'preview/site-next'
OUT.mkdir(parents=True,exist_ok=True)
text=HTML.read_text(encoding='utf-8'); checks=[]; errors=[]; requests=[]
def check(name, value):
    assert value, name
    checks.append(name)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('COMMONS_BROWSER'),args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1)
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda request:requests.append(request.url))
    if args.local_render: page.set_content(text)
    else:
        page.route('https://keyaigit.github.io/keyai-commons/',lambda r:r.fulfill(status=200,content_type='text/html',body=text))
        page.goto('https://keyaigit.github.io/keyai-commons/')
    expect(page.locator('h1')).to_contain_text('One planet.')
    check('Hero is present; no fake counts shown',page.locator('#online').text_content()=='N/A')
    check('Static page does not poll coordinator APIs',not any('/v1/' in url for url in requests))
    check('No script, font or rendering CDN dependency',not any('fonts.' in u or 'cdn.' in u for u in requests))
    page.wait_for_timeout(200)
    first=page.locator('#network-canvas').evaluate('(c)=>c.toDataURL()');page.wait_for_timeout(200)
    second=page.locator('#network-canvas').evaluate('(c)=>c.toDataURL()')
    check('Concept network actually animates',first!=second)
    page.locator('#motion').click();page.wait_for_timeout(150)
    first=page.locator('#network-canvas').evaluate('(c)=>c.toDataURL()');page.wait_for_timeout(200)
    check('User can freeze network animation',first==page.locator('#network-canvas').evaluate('(c)=>c.toDataURL()'))
    page.locator('#spread').click();page.wait_for_timeout(150)
    check('Expand control changes paused geometry',first!=page.locator('#network-canvas').evaluate('(c)=>c.toDataURL()'))
    page.locator('#spread').click()
    page.screenshot(path=str(OUT/'desktop-hero.png'))
    # Every breakpoint is checked in both languages. Decorative canvas is clipped by its parent.
    for lang in ['en','ru']:
        if lang=='ru':page.locator('#language').click()
        for width in [320,375,390,768,1024,1440,1920]:
            page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(70)
            check(f'No page overflow: {lang} {width}px',page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
            check(f'All text fits hero: {lang} {width}px',page.locator('h1').evaluate('(e)=>e.scrollWidth <= e.clientWidth+1'))
        check(f'Semantic main, title and download landmark: {lang}',page.locator('main').count()==1 and page.locator('h1').count()==1 and page.locator('#download').count()==1)
    page.set_viewport_size({'width':390,'height':844});page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'mobile-ru.png'))
    page.locator('#language').click();page.screenshot(path=str(OUT/'mobile-en.png'))
    page.set_viewport_size({'width':1440,'height':1000})
    # Walkthrough has only local illustrative state. Both participant and organizer actions required.
    expect(page.locator('#demo-start')).to_be_disabled()
    page.locator('#demo-consent').click();expect(page.locator('#demo-start')).to_be_enabled()
    check('Consent alone leaves demonstration idle',page.locator('#walkthrough').get_attribute('data-state')=='ready')
    page.locator('#demo-start').click();expect(page.locator('#walkthrough')).to_have_attribute('data-state','running')
    check('Organizer command advances consenting demo',True)
    page.locator('#demo-pause').click();page.wait_for_timeout(2800)
    check('Pause revokes demo permission and cancels completion',page.locator('#walkthrough').get_attribute('data-state')=='paused' and page.locator('#demo-consent').get_attribute('aria-checked')=='false')
    page.locator('#demo-consent').click();page.locator('#demo-start').click();expect(page.locator('#walkthrough')).to_have_attribute('data-state','complete',timeout=8000)
    check('Both actions complete only a labeled simulation',page.locator('.demo-disclaimer').text_content().startswith('Interactive illustration only.'))
    check('Walkthrough never calls a remote API',not any('/v1/' in url for url in requests))
    for osname,primary,secondary in [('windows','Windows-x64','Windows-arm64'),('macos','macOS-arm64','macOS-x64'),('linux','Linux-x64','Linux-arm64')]:
        page.locator('#tab-'+osname).click()
        check(f'{osname} primary release link',page.locator('#download-primary').get_attribute('href').endswith('KeyAI-Commons-'+primary+'.zip'))
        check(f'{osname} alternate architecture link',page.locator('#download-secondary').get_attribute('href').endswith('KeyAI-Commons-'+secondary+'.zip'))
    page.locator('#tab-windows').focus();page.keyboard.press('ArrowRight');expect(page.locator('#tab-macos')).to_have_attribute('aria-selected','true')
    check('Download tabs support keyboard navigation',page.locator('#tab-macos').evaluate('(e)=>document.activeElement===e'))
    page.locator('.faq-item summary').first.click();check('FAQ expands through native controls',page.locator('.faq-item').first.get_attribute('open') is not None)
    page.locator('#telemetry summary').click();check('Static telemetry exposes unknown state and disables joining',page.locator('#roundstate').text_content()=='N/A' and page.locator('#copy').is_disabled())
    page.locator('#tab-windows').click();page.locator('#telemetry summary').click();page.locator('.faq-item summary').first.click();page.locator('#demo-pause').click()
    page.evaluate("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('visible'));scrollTo(0,0)");page.wait_for_timeout(850);page.screenshot(path=str(OUT/'desktop-full.png'),full_page=True)
    # Reduced-motion preference is honored immediately, independently of saved locale.
    reduced=browser.new_context(viewport={'width':1100,'height':900},reduced_motion='reduce');r=reduced.new_page();r.on('pageerror',lambda e:errors.append(str(e)));r.set_content(text);r.wait_for_timeout(150)
    first=r.locator('#network-canvas').evaluate('(c)=>c.toDataURL()');r.wait_for_timeout(250)
    check('System reduced motion starts with stationary scene',first==r.locator('#network-canvas').evaluate('(c)=>c.toDataURL()') and r.locator('#motion').get_attribute('aria-pressed')=='true')
    check('Reduced motion does not hide content',r.locator('.reveal').first.evaluate('(e)=>getComputedStyle(e).opacity')=='1');reduced.close()
    nojs=browser.new_context(java_script_enabled=False,viewport={'width':390,'height':844});n=nojs.new_page();n.set_content(text)
    check('No-JavaScript fallback keeps content and real downloads',n.locator('#download-primary').get_attribute('href').endswith('Windows-x64.zip') and n.locator('h1').is_visible() and n.locator('noscript a').count()==1);nojs.close()
    # Hosted CI can navigate fixture origins; controlled API responses exercise the real same-origin branch.
    if not args.local_render:
        live=browser.new_context(viewport={'width':1280,'height':900});q=live.new_page();q.on('pageerror',lambda e:errors.append(str(e)))
        fixture={'name':'KeyAI Commons','online':3,'ready':2,'model_version':1,'round':{'running':False},'loss':0.2,'accuracy':0.91,'persistence':'fixture','history':[{'loss':.7},{'loss':.2}],'public_enrollment':True}
        def route_request(route):
            url=route.request.url
            if url.endswith('/v1/status'):route.fulfill(status=200,content_type='application/json',body=json.dumps(fixture))
            elif url.endswith('/v1/connect'):route.fulfill(status=200,content_type='application/json',body=json.dumps({'connection_code':'TEST-ONLY-NOT-A-REAL-INVITE'}))
            elif url=='https://commons-site-test.example/':route.fulfill(status=200,content_type='text/html',body=text)
            else:route.abort()
        q.route('**/*',route_request);q.goto('https://commons-site-test.example/');expect(q.locator('#online')).to_have_text('3');expect(q.locator('#copy')).to_be_enabled()
        check('Same-origin API fixture populates actual telemetry fields',q.locator('#ready').text_content()=='2' and q.locator('#roundstate').text_content()=='Idle')
        fixture['public_enrollment']=False;q.reload();expect(q.locator('#copy')).to_be_disabled();expect(q.locator('#enrollment')).to_contain_text('closed')
        check('Closed-enrollment fixture disables copying',True)
        fixture.clear();q.reload();expect(q.locator('#telemetry-badge')).to_have_text('COORDINATOR UNAVAILABLE')
        check('Invalid API fixture clears stale counts',q.locator('#online').text_content()=='N/A' and q.locator('#copy').is_disabled());live.close()
    check('No uncaught JavaScript errors',not errors)
    browser.close()
report={'passed':len(checks),'checks':checks,'page_errors':errors,'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'api_scope':'skipped (managed local renderer)' if args.local_render else 'synthetic same-origin fixtures; NOT a live coordinator test','breakpoints':[320,375,390,768,1024,1440,1920],'languages':['en','ru']}
(OUT/'site-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
