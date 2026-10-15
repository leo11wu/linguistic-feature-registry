from __future__ import annotations
import csv, json, os, shutil, subprocess, sys, importlib.metadata, re
from pathlib import Path
from functools import lru_cache
from .util import CACHE, ROOT, atomic_json, sha, Unavailable, emit

TABLES={
 'subtlex':('SUBTLEX-US', ['frequency_pm','lg10wf','lg10cd','contextual_diversity','rank']),
 'aoa':('Kuperman AoA',['aoa']), 'concreteness':('Brysbaert Concreteness',['concreteness']),
 'mrc':('MRC',['familiarity','imageability']), 'vad':('NRC VAD',['valence','arousal','dominance']),
 'lancaster':('Lancaster sensorimotor',['visual','auditory','haptic','olfactory','gustatory','interoceptive','hand_arm','foot_leg','head','mouth','torso']),
 'semd':('Semantic diversity',['semd']),
 'morpholex':('MorphoLex',['morphemes','prefixes','suffixes','roots','family_size','family_frequency','process']),
 'academic':('Academic/domain vocabulary',['category']),
 'semantic_categories':('Semantic dictionary',['category']),
 'connectives':('Connective dictionary',['category']),
 'function_words':('Function-word dictionary',['category']),
 'stance':('Stance-marker dictionary',['category']),
 'nominalizations':('Nominalization dictionary',['category']),
 'easy_words':('Dale–Chall easy-word list',['category']),
 'register_frequency':('Register frequencies',['register','frequency_pm']),
 'vac':('Verb–argument reference',['construction','frequency_pm']),
 'unigram':('SLOR unigram reference',['probability']),
}
PACKS={
 'corpus': dict(title='拟合计算工具：SciPy（不含语料）',packages=['scipy==1.17.1'],size='约30–60 MB'),
 'wordfreq':dict(title='wordfreq 平行词频',packages=['wordfreq==3.1.1'],size='约60–100 MB'),
 'phonology':dict(title='词典邻域与 WordNet',packages=['rapidfuzz==3.14.3','nltk==3.9.2'],size='约30–80 MB'),
 'tensor':dict(title='共享模型运行环境',packages=['torch==2.7.0','transformers==4.57.1','sentence-transformers==5.1.2','stanza==1.10.1','scipy==1.17.1','peft==0.17.1'],size='约600–1000 MB'),
 'sbert':dict(title='句间语义：MPNet',model='sentence-transformers/all-mpnet-base-v2',size='约440 MB'),
 'causal':dict(title='Surprisal：Pythia 410M',model='EleutherAI/pythia-410m-deduped',size='约850 MB'),
 'mlm':dict(title='PLL：BERT uncased',model='google-bert/bert-base-uncased',size='约440 MB'),
 'stanza':dict(title='原始 PTB 成分树',stanza=True,size='约500–1500 MB'),
 'coref':dict(title='Stanza 英语共指链',coref=True,size='约1–3 GB'),
 'lnre':dict(title='LNRE：独立 R / zipfR',managed_r=True,size='约100–180 MB运行文件，另有下载缓存'),
}

def activate():
    # Add only our managed dependency layer. Base versions are pinned by the installer.
    extra=CACHE/'runtime/site-packages'
    if extra.exists() and str(extra) not in sys.path: sys.path.insert(0,str(extra))
    os.environ.setdefault('HF_HOME',str(CACHE/'huggingface'))
    os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    os.environ.setdefault('NLTK_DATA',str(CACHE/'nltk_data'))
    os.environ.setdefault('STANZA_RESOURCES_DIR',str(CACHE/'stanza'))

def marker(name): return CACHE/'resources'/name/'manifest.json'

def available(name):return marker(name).exists() or (name=='lal' and (ROOT/'tools/lal/manifest.json').exists())

def inventory():
    rows=[]
    for key,(title,fields) in TABLES.items():
        p=marker(key); rows.append(dict(id=key,title=title,kind='table',size='取决于导入文件',installed=p.exists(),fields=['word']+fields))
    for key,p in PACKS.items():
        rows.append(dict(id=key,title=p['title'],kind='download',size=p['size'],installed=marker(key).exists()))
    for key,title in [('fasttext','fastText cc.en.300.bin'),('sid','SID 训练簇配置'),('biber','Biber/MAT 维度配置'),('lal','LAL 精确优化助手')]:
        bundled=key=='lal' and (ROOT/'tools/lal/manifest.json').exists()
        rows.append(dict(id=key,title=title,kind='bundled' if bundled else 'configuration',size='随应用提供' if bundled else '需指定资源',installed=available(key)))
    return rows

ALIASES={
 'word':['word','words','spelling','stimulus'], 'frequency_pm':['frequency_pm','subtlwf','frequencyperMillion','freq_pm'],
 'lg10wf':['lg10wf'], 'lg10cd':['lg10cd'], 'contextual_diversity':['contextual_diversity','subtlcd'],
 'aoa':['aoa','aoa_kup','rating.mean'], 'concreteness':['concreteness','conc.m'],
 'familiarity':['familiarity','fam'], 'imageability':['imageability','imag'],
 'valence':['valence','v.mean.sum'], 'arousal':['arousal','a.mean.sum'], 'dominance':['dominance','d.mean.sum'],
 'semd':['semd','sem_d'], 'morphemes':['morphemes','n_morphemes'], 'roots':['roots','n_roots'],
 'prefixes':['prefixes','n_prefixes'],'suffixes':['suffixes','n_suffixes']}

def import_resource(name,source,word_column=None,mapping=None):
    source=Path(source).resolve(); dest=CACHE/'resources'/name; dest.mkdir(parents=True,exist_ok=True)
    if name not in TABLES:
        if name=='fasttext' and source.suffix.lower()=='.bin':data={'path':str(source)}
        elif source.suffix.lower()=='.json':data=json.loads(source.read_text(encoding='utf-8-sig'))
        else:raise ValueError('配置资源需要JSON描述文件；fastText可直接导入.bin')
        if name=='fasttext':
            p=Path(data['path']).expanduser().resolve()
            if not p.is_file() or p.suffix!='.bin': raise ValueError('fastText需要现存的.bin文件')
            import struct
            with p.open('rb') as f:header=f.read(12)
            if len(header)!=12 or struct.unpack('<iii',header)[0]!=793712314 or struct.unpack('<iii',header)[2]!=300:raise ValueError('资源不是有效的300维fastText .bin')
            data['path']=str(p); data['sha256']=sha(p)
        elif name in {'lal','lnre'}:
            p=Path(data['executable']).expanduser().resolve()
            if not p.is_file() or not os.access(p,os.X_OK): raise ValueError('助手必须是可执行文件')
            data['executable']=str(p); data['sha256']=sha(p)
        elif name=='sid':
            for key in ['centroids','distance_means','distance_sds','embedding_id','training_hash']: 
                if key not in data: raise ValueError('SID缺少'+key)
        elif name=='biber':
            if not data.get('features') or not data.get('dimensions'): raise ValueError('Biber需要原特征规则、参照均值/SD及维度权重')
        else: raise ValueError('未知资源')
        atomic_json(dest/'config.json',data)
    else:
        with source.open(encoding='utf-8-sig',newline='') as f:
            sample=f.read(8192); f.seek(0)
            try: dialect=csv.Sniffer().sniff(sample,delimiters=',\t;')
            except csv.Error: dialect=csv.excel
            reader=csv.DictReader(f,dialect=dialect); headers=reader.fieldnames or []
            lower={x.casefold():x for x in headers}; mapping=dict(mapping or {})
            for key in ['word']+TABLES[name][1]:
                if key not in mapping:
                    for alias in ALIASES.get(key,[key]):
                        if alias.casefold() in lower: mapping[key]=lower[alias.casefold()]; break
            if word_column: mapping['word']=word_column
            if 'word' not in mapping: raise ValueError('没有找到word列；请使用标准模板或指定词列')
            if not any(k in mapping for k in TABLES[name][1]): raise ValueError('没有找到资源数值/类别列；请使用标准模板')
            rows=[]
            for row in reader:
                word=row.get(mapping['word'],'').strip().casefold()
                if not word: continue
                out={'word':word}
                for key,field in mapping.items():
                    if key=='word': continue
                    v=row.get(field,'').strip()
                    if not v: continue
                    if key in {'category','process','construction','register'}: out[key]=v
                    else:
                        try:
                            value=float(v)
                            if not __import__('math').isfinite(value):raise ValueError()
                            if name=='mrc' and key in {'familiarity','imageability'} and value==0:continue
                            out[key]=value
                        except ValueError: raise ValueError(f'{word}: {field} 不是有效数字')
                rows.append(out)
        if not rows: raise ValueError('资源中没有有效词项')
        atomic_json(dest/'table.json',rows)
        shutil.copy2(source,dest/('original'+source.suffix))
    atomic_json(marker(name),dict(resource_id=name,source_path=str(source),sha256=sha(source),mapping=mapping or {},imported=True))
    table.cache_clear(); configuration.cache_clear()

@lru_cache(maxsize=24)
def table(name):
    p=CACHE/'resources'/name/'table.json'
    if not p.exists(): raise Unavailable('需导入资源：'+name,'resource_required')
    rows=json.loads(p.read_text()); result={}
    for row in rows:
        word=row['word']
        if word in result and result[word]!=row: raise Unavailable('词表存在重复词项且数值不同；需明确合并口径','resource_invalid')
        result[word]=row
    return result

@lru_cache(maxsize=8)
def configuration(name):
    p=CACHE/'resources'/name/'config.json'
    if name=='lal' and not p.exists() and (ROOT/'tools/lal/manifest.json').exists():
        return dict(executable=str(ROOT/'tools/lal/lal-helper'),version='LAL-v24.10')
    if not p.exists(): raise Unavailable('需导入配置：'+name,'resource_required')
    return json.loads(p.read_text())

def install(name):
    activate()
    if name not in PACKS: raise ValueError('该资源需要导入，不能自动下载')
    p=PACKS[name]; CACHE.mkdir(parents=True,exist_ok=True)
    if p.get('managed_r'):
        from .managed_r import install as install_r
        manifest=install_r()
    elif 'packages' in p:
        uv=ROOT/'tools/uv'
        if not uv.exists():
            found=shutil.which('uv')
            if not found: raise ValueError('缺少应用自带安装器，请重新构建应用')
            uv=Path(found)
        target=CACHE/'runtime/site-packages'; stage=CACHE/'runtime/.staging'
        # Resolve against the base constraints; commit only a successful installation.
        shutil.rmtree(stage,ignore_errors=True)
        if target.exists(): shutil.copytree(target,stage)
        base=ROOT/'requirements-core.lock'
        command=[str(uv),'pip','install','--python',sys.executable,'--target',str(stage),'--cache-dir',str(CACHE/'download-cache'),'--no-config']
        if base.exists(): command+=['--constraint',str(base)]
        command+=p['packages']
        emit('progress',message='下载共享依赖 '+name)
        subprocess.run(command,check=True,stdout=sys.stderr,stderr=sys.stderr)
        old=target.with_name('.previous'); shutil.rmtree(old,ignore_errors=True)
        if target.exists(): os.replace(target,old)
        os.replace(stage,target); shutil.rmtree(old,ignore_errors=True)
        manifest={'resource_id':name,'packages':p['packages']}
        if name=='phonology':
            activate();import nltk
            nltk.download('wordnet',download_dir=str(CACHE/'nltk_data'),quiet=True,raise_on_error=True)
            manifest['wordnet_sha256']=sha(CACHE/'nltk_data/corpora/wordnet.zip')
    elif 'model' in p:
        if not marker('tensor').exists(): install('tensor')
        activate()
        from huggingface_hub import HfApi, snapshot_download
        revision='step143000' if name=='causal' else 'main'
        info=HfApi().model_info(p['model'],revision=revision)
        emit('progress',message='下载模型 '+p['model'])
        files=[s.rfilename for s in info.siblings]
        weights='*.safetensors' if any(f.endswith('.safetensors') for f in files) else '*.bin'
        location=snapshot_download(p['model'],revision=info.sha,allow_patterns=['*.json','*.txt','*.model','README.md','LICENSE*',weights],ignore_patterns=['onnx/*','openvino/*'])
        manifest={'resource_id':name,'model_id':p['model'],'revision':info.sha,'path':location,'files':{str(f.relative_to(location)):sha(f) for f in Path(location).rglob('*') if f.is_file()}}
    else:
        if not marker('tensor').exists(): install('tensor')
        activate(); import stanza
        processors='tokenize,mwt,pos,lemma,depparse,coref' if name=='coref' else 'tokenize,mwt,pos,constituency'
        package={'constituency':'ptb3_charlm'} if name=='stanza' else 'default'
        # Stanza packages are validated against resources.json by the library.
        stanza.download('en',model_dir=str(CACHE/'stanza'),processors=processors,package=package,verbose=False)
        manifest={'resource_id':name,'stanza_version':importlib.metadata.version('stanza'),'processors':processors,'package':package,'files':{str(f.relative_to(CACHE/'stanza')):sha(f) for f in (CACHE/'stanza').rglob('*') if f.is_file()}}
        if name=='coref':
            import torch
            from huggingface_hub import HfApi,snapshot_download
            checkpoint=next((CACHE/'stanza/en/coref').glob('*.pt'))
            payload=torch.load(checkpoint,map_location='cpu',weights_only=False)
            config=payload.get('config',{})
            model_id=config.get('bert_model') or config.get('transformer_model')
            if not model_id:raise ValueError('共指checkpoint未声明transformer模型')
            info=HfApi().model_info(model_id)
            files=[s.rfilename for s in info.siblings];weights='*.safetensors' if any(f.endswith('.safetensors') for f in files) else '*.bin'
            location=snapshot_download(model_id,revision=info.sha,allow_patterns=['*.json','*.txt','*.model',weights],ignore_patterns=['onnx/*','openvino/*'])
            ref=Path(location).parent.parent/'refs/main';ref.parent.mkdir(exist_ok=True);ref.write_text(info.sha)
            manifest['hf_dependencies']=[dict(model_id=model_id,revision=info.sha,files={str(f.relative_to(location)):sha(f) for f in Path(location).rglob('*') if f.is_file()})]
    atomic_json(marker(name),manifest)
    if name=='tensor':atomic_json(marker('corpus'),dict(resource_id='corpus',packages=['scipy==1.17.1'],shared_with='tensor'))
    emit('resource_installed',resource_id=name)

def snapshot():
    receipts={p.parent.name:json.loads(p.read_text()) for p in (CACHE/'resources').glob('*/manifest.json')} if (CACHE/'resources').exists() else {}
    if (ROOT/'tools/lal/manifest.json').exists():receipts.setdefault('lal',json.loads((ROOT/'tools/lal/manifest.json').read_text()))
    return receipts
