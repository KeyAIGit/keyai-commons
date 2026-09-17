"""Prepare an unsigned Store submission package with explicit identity.
Never signs, installs, disables protection, uploads, or creates an account.
A --validation-only package deliberately has no reserved Store identity.
"""
import argparse,hashlib,json,pathlib,re,shutil,struct,subprocess,tempfile,zlib,sys
from xml.sax.saxutils import escape

def icon(path,size):
    rows=[]
    for y in range(size):
        row=bytearray()
        for x in range(size):
            dx=(x-size/2)/(size*.37);dy=(y-size/2)/(size*.37)
            a=(dx+dy)/2**.5;b=(dx-dy)/2**.5
            ring=abs(a*a+b*b/.16-1)<.12 or abs(b*b+a*a/.16-1)<.12
            ink=ring or dx*dx+dy*dy<.024
            row.extend((22,89,199,255) if ink else (255,255,255,255))
        rows.append(b'\0'+row)
    def chunk(name,data):return struct.pack('!I',len(data))+name+data+struct.pack('!I',zlib.crc32(name+data)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',required=True);p.add_argument('--output',required=True);p.add_argument('--makeappx',required=True)
    p.add_argument('--identity');p.add_argument('--publisher');p.add_argument('--publisher-display-name')
    p.add_argument('--arch',choices=['x64','arm64'],default='x64');p.add_argument('--validation-only',action='store_true')
    a=p.parse_args();binary=pathlib.Path(a.binary).resolve();out=pathlib.Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if not binary.is_file():raise SystemExit('Reviewed community binary missing')
    if a.validation_only:
        identity='KeyAI.Commons.LocalValidationOnly';publisher='CN=LOCAL-VALIDATION-ONLY';display='Local validation only'
    else:
        if not all([a.identity,a.publisher,a.publisher_display_name]):raise SystemExit('Copy the real identity and publisher fields from Partner Center. No guessed defaults.')
        identity,publisher,display=a.identity,a.publisher,a.publisher_display_name
    if not re.fullmatch(r'[A-Za-z0-9.-]{3,50}',identity):raise SystemExit('Invalid package identity')
    if not publisher.startswith('CN='):raise SystemExit('Publisher must be the exact Partner Center distinguished name')
    values=[escape(x, {'"': '&quot;', "'": '&apos;'}) for x in [identity,publisher,display]]
    with tempfile.TemporaryDirectory(prefix='commons-msix-',dir=out) as td:
        root=pathlib.Path(td);(root/'Assets').mkdir();shutil.copyfile(binary,root/'KeyAI-Community.exe')
        for name,size in [('Square44x44Logo.png',44),('Square150x150Logo.png',150),('StoreLogo.png',50)]:icon(root/'Assets'/name,size)
        manifest=f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap rescap">
<Identity Name="{values[0]}" Publisher="{values[1]}" Version="0.4.0.0" ProcessorArchitecture="{a.arch}"/>
<Properties><DisplayName>KeyAI Commons Community Preview</DisplayName><PublisherDisplayName>{values[2]}</PublisherDisplayName><Logo>Assets\\StoreLogo.png</Logo></Properties>
<Resources><Resource Language="en-us"/><Resource Language="ru-ru"/></Resources>
<Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26100.0"/></Dependencies>
<Applications><Application Id="Community" Executable="KeyAI-Community.exe" EntryPoint="Windows.FullTrustApplication"><uap:VisualElements DisplayName="KeyAI Commons Community Preview" Description="Community-first AI research preview. No training capability." BackgroundColor="transparent" Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png"/></Application></Applications>
<Capabilities><rescap:Capability Name="runFullTrust"/></Capabilities></Package>'''
        (root/'AppxManifest.xml').write_text(manifest,encoding='utf-8')
        name=('LOCAL-VALIDATION-ONLY' if a.validation_only else 'KeyAI-Commons-Community')+'.msix'
        target=out/name
        def sdkpath(value):
            if sys.platform!='win32' and a.makeappx.lower().endswith('.exe'):
                return subprocess.check_output(['wslpath','-w',str(value)],text=True).strip()
            return str(value)
        subprocess.run([a.makeappx,'pack','/d',sdkpath(root),'/p',sdkpath(target),'/o'],check=True)
        report={'package':name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'identity':identity,'local_validation_only':a.validation_only,'publisher_signed':False,'store_uploaded':False,'account_verified':False,'purpose':'Pack structure validation only; not a trust bypass, Store approval or installation test.'}
        (out/'PACKAGING-REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
