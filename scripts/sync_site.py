"""Copy the canonical embedded landing page to static hosting directories."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for name in ('site','docs'):
 d=root/name;d.mkdir(exist_ok=True)
 (d/'index.html').write_bytes((root/'src/web/landing.html').read_bytes())
 (d/'.nojekyll').write_text('')
