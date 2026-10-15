from __future__ import annotations
import csv, hashlib, json, math, os, tempfile
import subprocess,time
from pathlib import Path
import numpy as np

ROOT = Path(os.environ.get("LINGMETRICS_ROOT", Path(__file__).resolve().parents[2]))
CACHE = Path(os.environ.get("LINGMETRICS_CACHE", Path.home() / "Library/Application Support/LingMetrics"))

class Unavailable(Exception):
    def __init__(self, reason, status="input_required"):
        super().__init__(reason)
        self.status = status

def sha(path):
    h = hashlib.sha256()
    count=0
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block);count+=len(block)
    if count!=Path(path).stat().st_size:return hashlib.sha256(local_bytes(path)).hexdigest()
    return h.hexdigest()

def local_bytes(path):
    path=Path(path)
    content=path.read_bytes()
    if len(content)==path.stat().st_size:return content
    if __import__('sys').platform=='darwin':
        emit('progress',message='准备云同步文件的本地内容：'+path.name)
        subprocess.run(['brctl','download',str(path)],check=True,timeout=30,capture_output=True)
        for _ in range(10):
            content=path.read_bytes()
            if len(content)==path.stat().st_size:return content
            time.sleep(.2)
    raise OSError('文件尚未完整下载到本机：'+str(path))

def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean(v) for v in x]
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x): return None
    return x

def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".partial-")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(clean(value), f, ensure_ascii=False, allow_nan=False, indent=2)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def emit(kind, **data):
    print(json.dumps(clean(dict(event=kind, **data)), ensure_ascii=False, allow_nan=False), flush=True)

def csv_write(path, rows, fields=None):
    rows = list(rows)
    fields = fields or sorted({k for r in rows for k in r})
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix(path.suffix+".partial")
    with temp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="raise")
        w.writeheader()
        for r in rows:
            r = clean(r)
            w.writerow({k: (json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in r.items()})
    os.replace(temp,path)

def ratio(a,b): return float(a)/b if b else None

def summary(values, prefix):
    v=np.asarray([x for x in values if x is not None and math.isfinite(x)],dtype=float)
    if not len(v): return {prefix+".mean":None,prefix+".valid_n":0}
    return {prefix+".mean":float(v.mean()),prefix+".sd_population":float(v.std()),
            prefix+".median":float(np.median(v)),prefix+".min":float(v.min()),
            prefix+".max":float(v.max()),prefix+".valid_n":len(v)}

def entropy(counts):
    p=np.asarray(list(counts),dtype=float)
    if p.sum()<=0: return None
    p=p[p>0]/p.sum()
    return float(-(p*np.log2(p)).sum())
