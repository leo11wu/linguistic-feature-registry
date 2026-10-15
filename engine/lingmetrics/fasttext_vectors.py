import subprocess,json
import numpy as np
from . import resources
from .util import ROOT,Unavailable

_process=None
def release():
    global _process
    if _process is not None:
        if _process.poll() is None:
            _process.stdin.close()
            try:_process.wait(timeout=5)
            except subprocess.TimeoutExpired:_process.kill();_process.wait()
        _process=None

def encode(texts):
    global _process
    if _process is None:
        conf=resources.configuration('fasttext');helper=ROOT/'tools/fasttext'
        if not helper.exists():raise Unavailable('缺少fastText原生助手，请使用完整安装包','resource_required')
        _process=subprocess.Popen([str(helper),'print-word-vectors',conf['path']],text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=1)
    rows=[]
    for text in texts:
        words=text.casefold().split();vectors=[]
        for word in words:
            _process.stdin.write(word+'\n');_process.stdin.flush();line=_process.stdout.readline()
            if not line:raise Unavailable('fastText模型加载失败或助手提前结束','resource_invalid')
            fields=line.split();vec=np.array([float(x) for x in fields[1:]],dtype=float)
            if len(vec)!=300:raise Unavailable('当前资源不是300维fastText词向量','resource_invalid')
            vectors.append(vec)
        vec=np.mean(vectors,axis=0) if vectors else np.zeros(300);norm=np.linalg.norm(vec)
        rows.append(vec/norm if norm else np.full(300,np.nan))
    return np.array(rows)
