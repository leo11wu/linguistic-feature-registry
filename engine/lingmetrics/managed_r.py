"""Relocate the official R framework under the per-user resource cache."""
import os, shutil, subprocess, hashlib, tarfile, urllib.request, ssl, json, re, shlex
from pathlib import Path
from .util import ROOT, CACHE, sha, atomic_json, emit, Unavailable

URL='https://cran.r-project.org/bin/macosx/big-sur-arm64/base/R-4.5.3-arm64.pkg'
def download(url,path):
    import certifi
    context=ssl.create_default_context(cafile=certifi.where())
    temp=Path(str(path)+'.partial');temp.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(url,context=context,timeout=120) as response,temp.open('wb') as f:shutil.copyfileobj(response,f)
    os.replace(temp,path)

def relocate(home):
    # Rewrite only framework-internal load commands; system libraries stay system libraries.
    old='/Library/Frameworks/R.framework/Versions/4.5-arm64/Resources/'
    files=[]
    for p in home.rglob('*'):
        if not p.is_file() or p.is_symlink():continue
        with p.open('rb') as f:magic=f.read(4)
        if magic!=b'\xcf\xfa\xed\xfe':continue
        listing=subprocess.run(['otool','-L',str(p)],capture_output=True,text=True,check=True).stdout
        for line in listing.splitlines()[1:]:
            library=line.strip().split(' (',1)[0]
            if library.startswith(old):
                target=home/library[len(old):]
                relative=os.path.relpath(target,p.parent)
                subprocess.run(['install_name_tool','-change',library,'@loader_path/'+relative,str(p)],check=True,capture_output=True)
        if p.suffix in {'.dylib','.so'}:
            subprocess.run(['install_name_tool','-id','@loader_path/'+p.name,str(p)],check=True,capture_output=True)
        subprocess.run(['codesign','--force','--sign','-',str(p)],check=True,capture_output=True)
        files.append(p)
    return files

def install():
    folder=CACHE/'resources/lnre';folder.mkdir(parents=True,exist_ok=True)
    package=CACHE/'download-cache/R-4.5.3-arm64.pkg'
    if not package.exists():emit('progress',message='下载兼容macOS 13的R 4.5.3运行环境');download(URL,package)
    trusted=ROOT/'native/resource-hashes.json'
    if trusted.exists():
        expected=json.loads(trusted.read_text())['R-4.5.3-arm64.pkg']
        if sha(package)!=expected:raise Unavailable('R运行包校验失败','resource_invalid')
    check=subprocess.run(['pkgutil','--check-signature',str(package)],capture_output=True,text=True)
    # A pinned SHA can independently validate the official source where trust evaluation is unavailable.
    if check.returncode!=0 and not trusted.exists():raise Unavailable('官方R包签名未通过；未执行安装包','resource_invalid')
    expanded=CACHE/'download-cache/R-expanded';shutil.rmtree(expanded,ignore_errors=True)
    subprocess.run(['pkgutil','--expand-full',str(package),str(expanded)],check=True)
    source=expanded/'R-fw.pkg/Payload/R.framework/Versions/4.5-arm64/Resources'
    stage=folder/'.runtime-stage';shutil.rmtree(stage,ignore_errors=True)
    shutil.copytree(source,stage,symlinks=True)
    for p in list(stage.rglob('*.dSYM')):shutil.rmtree(p)
    relocate(stage)
    runtime=folder/'runtime';shutil.rmtree(runtime,ignore_errors=True);os.replace(stage,runtime)
    wrapper=runtime/'bin/R'
    code=wrapper.read_text()
    code=re.sub(r'^R_HOME_DIR=.*$', 'R_HOME_DIR='+shlex.quote(str(runtime)), code, count=1, flags=re.M)
    for variable,subdir in [('R_SHARE_DIR','share'),('R_INCLUDE_DIR','include'),('R_DOC_DIR','doc')]:
        code=re.sub(r'^'+variable+r'=.*$',variable+'='+shlex.quote(str(runtime/subdir)),code,count=1,flags=re.M)
    wrapper.write_text(code)
    script=wrapper;env=dict(os.environ,R_HOME=str(runtime),R_LIBS_USER=str(runtime/'library'))
    archive=CACHE/'download-cache/zipfR_0.6-70.tar.gz'
    if not archive.exists():download('https://cran.r-project.org/src/contrib/zipfR_0.6-70.tar.gz',archive)
    # Pure R package: no local compiler is needed.
    subprocess.run([str(script),'CMD','INSTALL','--no-byte-compile','--no-test-load','--no-docs','--no-html','--no-demo',str(archive)],env=env,check=True,stdout=subprocess.DEVNULL)
    shutil.rmtree(expanded,ignore_errors=True)
    manifest=dict(resource_id='lnre',version='R-4.5.3/zipfR-0.6-70',url=URL,package_sha256=sha(package),zipfr_sha256=sha(archive),runtime=str(runtime))
    atomic_json(folder/'manifest.json',manifest)
    return manifest

def fit(spectrum,model='fzm'):
    p=CACHE/'resources/lnre/manifest.json'
    if not p.exists():raise Unavailable('请下载LNRE运行资源','resource_required')
    meta=json.loads(p.read_text());home=Path(meta['runtime']);env=dict(os.environ,R_HOME=str(home),R_LIBS_USER=str(home/'library'))
    text='m Vm\n'+'\n'.join(f"{r['frequency']} {r['types']}" for r in spectrum)+'\n'
    proc=subprocess.run([str(home/'bin/exec/R'),'--vanilla','--slave','--file='+str(ROOT/'native/lnre.R'),'--args',model],input=text,text=True,capture_output=True,env=env,check=True,timeout=300)
    return json.loads(proc.stdout)
