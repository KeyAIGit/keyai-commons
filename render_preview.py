"""Render the shipped interface without network access. This is a layout preview,
not evidence of a live public coordinator or a completed browser E2E test."""
import re,json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parent;out=root/'preview';out.mkdir(exist_ok=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox']);p=b.new_page(viewport={'width':1440,'height':1040})
 for name in ['client','admin','landing']:
  html=(root/'src'/'web'/f'{name}.html').read_text();html=re.sub(r'<script>.*?</script>','',html,flags=re.S)
  html=html.replace('Research pilot · v0.1.0','Layout preview · v0.1.0')
  p.set_content(html);p.screenshot(path=str(out/f'{name}.png'),full_page=True)
  assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  p.set_viewport_size({'width':390,'height':844});p.screenshot(path=str(out/f'{name}-mobile.png'),full_page=True)
  assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  p.set_viewport_size({'width':1440,'height':1040})
 b.close()
(root/'browser-results.json').write_text(json.dumps({'layout_checks_passed':6,'scope':'static layout rendering of the three shipped interfaces at desktop/mobile widths; scripts removed; no live browser network test','live_browser_test':'NOT VERIFIED: local network navigation blocked by managed Chromium policy; separate process/API integration tests passed'},indent=2))
print('6 static layout checks passed; no horizontal overflow')
