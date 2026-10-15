#!/usr/bin/env python3
"""Build a relocatable arm64 app; runtime/dependencies are isolated in the system temporary directory."""
from pathlib import Path
import argparse, hashlib, importlib.metadata, json, os, plistlib, shutil, subprocess, zipfile, tempfile

ROOT=Path(__file__).resolve().parents[1]
BUILD=Path(os.environ.get('LINGMETRICS_BUILD_DIR',Path(tempfile.gettempdir())/('lingmetrics-build-'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:12])))
DIST=ROOT/'dist'

def command(args,**kwargs):subprocess.run(list(map(str,args)),check=True,cwd=ROOT,**kwargs)

def safe_copy(source,destination):
    # Stream and verify copies rather than relying on filesystem clone/copy shortcuts.
    source,destination=Path(source),Path(destination)
    h=hashlib.sha256()
    count=0
    with source.open('rb') as f,destination.open('wb') as out:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block);out.write(block);count+=len(block)
    if count!=source.stat().st_size:
        subprocess.run(['brctl','download',str(source)],check=True,timeout=30,capture_output=True)
        data=source.read_bytes()
        if len(data)!=source.stat().st_size:raise RuntimeError('Source is not locally available: '+str(source))
        destination.write_bytes(data);h=hashlib.sha256(data)
    shutil.copystat(source,destination)
    if hashlib.sha256(destination.read_bytes()).hexdigest()!=h.hexdigest():raise RuntimeError('Copy verification failed: '+str(source))
    return str(destination)

def prepare():
    BUILD.mkdir(parents=True,exist_ok=True)
    uv=shutil.which('uv')
    if not uv:raise RuntimeError('Build requires uv; app users do not need it.')
    runtime=BUILD/'python/cpython-3.11.15-macos-aarch64-none'
    if not runtime.exists():command([uv,'python','install','3.11.15','--install-dir',BUILD/'python','--no-bin','--cache-dir',BUILD/'uv-cache','--no-config'])
    if not (BUILD/'base-site/spacy').exists():
        command([uv,'pip','install','--python',runtime/'bin/python3.11','--target',BUILD/'base-site','--link-mode','copy','--cache-dir',BUILD/'uv-cache','--no-config',
                 'spacy==3.8.14','numpy==2.4.4','cmudict==1.1.3','click==8.1.8',
                 'https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl'])
    lock=[]
    for d in importlib.metadata.distributions(path=[str(BUILD/'base-site')]):lock.append(d.metadata['Name']+'=='+d.version)
    (ROOT/'requirements-core.lock').write_text('\n'.join(sorted(set(lock),key=str.lower))+'\n')
    return runtime,uv

def build(app_name='LingMetrics.app'):
    if Path(app_name).name!=app_name or not app_name.endswith('.app'):raise ValueError('app_name must be an app bundle basename')
    runtime,uv=prepare();DIST.mkdir(exist_ok=True)
    app=Path(tempfile.mkdtemp(prefix='LingMetrics-build-'))/'LingMetrics.app'
    contents=app/'Contents';res=contents/'Resources';mac=contents/'MacOS';mac.mkdir(parents=True);res.mkdir()
    for source,name in [(runtime,'python'),(BUILD/'base-site','base-site'),(ROOT/'engine','engine'),(ROOT/'data','data'),(ROOT/'docs','docs'),(ROOT/'native','native')]:
        shutil.copytree(source,res/name,symlinks=True,copy_function=safe_copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store'))
    for file in ['requirements-core.lock','THIRD_PARTY.md']:
        if (ROOT/file).exists():shutil.copy2(ROOT/file,res/file)
    # Ship measurement/benchmark records; archive checksums stay outside the bundle.
    (res/'metadata').mkdir()
    for file in ['execution_manifest.json','performance.json','ui_validation.json','lightweight_validation.json','fitting_validation.json']:
        if (ROOT/'metadata'/file).exists():safe_copy(ROOT/'metadata'/file,res/'metadata'/file)
    icon_metadata=json.loads((ROOT/'metadata/icon.json').read_text())
    for item in icon_metadata['files']:
        content=(ROOT/item['path']).read_bytes()
        if hashlib.sha256(content).hexdigest()!=item['sha256']:raise RuntimeError('Icon asset hash mismatch: '+item['path'])
    safe_copy(ROOT/'app/Assets/AppIcon.icns',res/'AppIcon.icns')
    safe_copy(ROOT/'app/Assets/AppIcon.svg',res/'AppIcon.svg')
    tools=res/'tools';tools.mkdir();shutil.copy2(uv,tools/'uv')
    native=BUILD/'helpers/lal'
    archive=ROOT/'downloads/native-lal-arm64.tar.gz'
    if archive.exists():
        import tarfile
        native.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive) as t:
            for member in t.getmembers():
                if not member.isfile():continue
                name=Path(member.name)
                if len(name.parts)!=1:raise RuntimeError('Unexpected native archive path')
                path=native/name
                path.write_bytes(t.extractfile(member).read());path.chmod(member.mode)
    if native.exists():shutil.copytree(native,tools/'lal',copy_function=safe_copy)
    fasttext=BUILD/'fasttext'
    archive_fasttext=ROOT/'downloads/native-fasttext-arm64.tar.gz'
    if not fasttext.exists() and archive_fasttext.exists():
        import tarfile
        with tarfile.open(archive_fasttext) as t:
            member=t.getmember('fasttext');fasttext.write_bytes(t.extractfile(member).read());fasttext.chmod(0o755)
    if fasttext.exists():safe_copy(fasttext,tools/'fasttext')
    if archive_fasttext.exists():
        import tarfile
        folder=tools/'fasttext-source';folder.mkdir()
        with tarfile.open(archive_fasttext) as t:
            for member in t.getmembers():
                if member.isfile() and member.name!='fasttext':(folder/member.name).write_bytes(t.extractfile(member).read())
    if (ROOT/'examples').exists():shutil.copytree(ROOT/'examples',res/'examples',copy_function=safe_copy)
    env=dict(os.environ,CLANG_MODULE_CACHE_PATH=str(BUILD/'ModuleCache'))
    command(['xcrun','swiftc','-O','-parse-as-library','-target','arm64-apple-macos13.0','-module-cache-path',BUILD/'ModuleCache',ROOT/'app/LingMetrics.swift',ROOT/'app/FittingView.swift',ROOT/'app/AnalysisChoicesView.swift',ROOT/'app/ReportPreview.swift','-o',mac/'LingMetrics'],env=env)
    command(['xcrun','swiftc','-O','-target','arm64-apple-macos13.0','-module-cache-path',BUILD/'ModuleCache',ROOT/'app/SystemCheck.swift','-o',tools/'system-check'],env=env)
    info={'CFBundleName':'LingMetrics','CFBundleDisplayName':'LingMetrics','CFBundleIdentifier':'org.leo11wu.LingMetrics','CFBundleVersion':'7','CFBundleShortVersionString':'0.2.3','CFBundleExecutable':'LingMetrics','CFBundleIconFile':'AppIcon.icns','CFBundlePackageType':'APPL','LSMinimumSystemVersion':'13.0','NSHighResolutionCapable':True,'NSPrincipalClass':'NSApplication','LSApplicationCategoryType':'public.app-category.education'}
    with (contents/'Info.plist').open('wb') as f:plistlib.dump(info,f)
    # Sign individual Mach-O files before signing the bundle, including dylibs and extensions.
    for p in contents.rglob('*'):
        if p.is_file() and not p.is_symlink():
            # Clear only Finder/resource-fork metadata on generated distribution files.
            # Never remove quarantine or alter system Gatekeeper settings.
            attributes=subprocess.run(['xattr',p],capture_output=True,text=True,check=True).stdout.splitlines()
            for attribute in ['com.apple.FinderInfo','com.apple.ResourceFork','com.apple.provenance']:
                if attribute in attributes:command(['xattr','-d',attribute,p])
            with p.open('rb') as f:magic=f.read(4)
            if magic in [b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca']:
                command(['codesign','--force','--sign','-',p],stdout=subprocess.DEVNULL)
    command(['codesign','--force','--sign','-',app]);command(['codesign','--verify','--deep','--strict',app])
    destination=DIST/app_name;shutil.rmtree(destination,ignore_errors=True);shutil.copytree(app,destination,symlinks=True,copy_function=safe_copy)
    archive=DIST/'LingMetrics-0.2.3-arm64.zip'
    if archive.exists():archive.unlink()
    # Archive the verified temporary bundle; Desktop file providers can add Finder metadata to the convenience copy.
    command(['ditto','-c','-k','--sequesterRsrc','--keepParent',app,archive])
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    checksums=DIST/'SHA256SUMS.txt'
    previous=checksums.read_text().splitlines() if checksums.exists() else []
    checksums.write_text('\n'.join([line for line in previous if line.split()[-1:]!=[archive.name]]+[digest+'  '+archive.name])+'\n')
    size=sum(p.stat().st_size for p in destination.rglob('*') if p.is_file() and not p.is_symlink())
    report={'version':'0.2.3','target':'arm64-macos13+','signing':'ad-hoc','notarized':False,'archive_bytes':archive.stat().st_size,'expanded_bytes':size,'sha256':digest,'budget_archive_pass':archive.stat().st_size<=100*1024**2,'budget_expanded_pass':size<=250*1024**2}
    (DIST/'build-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--app-name',default='LingMetrics.app')
    build(parser.parse_args().app_name)
