from __future__ import annotations
import csv, json, hashlib, importlib.metadata, os, platform, signal, sqlite3, sys, time, traceback, io, resource
from pathlib import Path
from collections import Counter
from . import __version__, resources, catalogue
from .util import ROOT, CACHE, emit, atomic_json, clean, sha, csv_write, Unavailable,local_bytes
from .core import Text, base_measure

cancelled=False
def cancel(signum=None,frame=None):
    global cancelled
    cancelled=True

def input_documents(job):
    paths=[]
    for value in job['inputs']:
        path=Path(value).expanduser().resolve()
        if path.is_dir():paths.extend(sorted(p for p in path.rglob('*') if p.is_file() and p.suffix.lower()=='.txt'))
        else:paths.append(path)
    paths=list(dict.fromkeys(paths));documents=[];identifiers=set();file_hashes=[]
    for path in paths:
        if not path.is_file():raise ValueError('输入文件不存在：'+str(path))
        content=local_bytes(path)
        file_hashes.append({'path':str(path),'sha256':hashlib.sha256(content).hexdigest()})
        if path.suffix.lower()=='.txt':
            text=content.decode(job.get('encoding','utf-8-sig'))
            rows=[{'text':text,'source_file':str(path)}]
        elif path.suffix.lower()=='.csv':
            with io.StringIO(content.decode(job.get('encoding','utf-8-sig')),newline='') as f:
                reader=csv.DictReader(f);column=job.get('text_column','text')
                if column not in (reader.fieldnames or []):raise ValueError('CSV缺少文本列：'+column)
                rows=[]
                for index,row in enumerate(reader,2):
                    rows.append(dict(text=row.pop(column) or '',source_file=str(path),source_row=index,**row))
        else:raise ValueError('仅支持TXT和CSV：'+str(path))
        for row in rows:
            text=row.pop('text');identifier=str(row.pop('doc_id','') or f'doc_{len(documents)+1:06d}')
            if identifier in identifiers:raise ValueError('重复doc_id：'+identifier)
            identifiers.add(identifier)
            documents.append(dict(id=identifier,text=text,meta=row,sha256=hashlib.sha256(text.encode()).hexdigest()))
    if not documents:raise ValueError('没有找到TXT文件或CSV文本行')
    return documents,file_hashes

def versions():
    out={'lingmetrics':__version__,'python':platform.python_version(),'machine':platform.machine(),'macos':platform.mac_ver()[0]}
    for name in ['spacy','en-core-web-sm','numpy','cmudict','scipy','wordfreq','torch','transformers','sentence-transformers','stanza','nltk','rapidfuzz']:
        try:out[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    return out

def calculate(fid,ctx,route):
    if fid!='DEP15':
        missing=[name for name in catalogue.required(fid,ctx.options) if not resources.available(name)]
        if missing:raise Unavailable('需准备资源：'+', '.join(missing),'resource_required')
    if route=='base':return base_measure(fid,ctx)
    if route=='lexical':
        from .lexicons import lexical_measure
        return lexical_measure(fid,ctx)
    if route=='syntax':
        from .syntax import measure
        return measure(fid,ctx)
    if route=='configured':
        from .configured import measure
        return measure(fid,ctx)
    if route in set(catalogue.MODELS.values()):
        from .models import measure
        return measure(fid,ctx)
    raise Unavailable(catalogue.PENDING.get(fid,'方法尚待核实'),'method_pending')

def result(fid,fn):
    try:
        values=clean(fn())
        if not values:raise Unavailable('该输入未产生可用测量列','undefined')
        numeric=[v for k,v in values.items() if not k.endswith(('.valid_n','.eligible_n'))]
        missing=[k for k,v in values.items() if v is None]
        state='undefined' if numeric and all(v is None for v in numeric) else 'partial' if missing else 'computed'
        return values,dict(feature_id=fid,status=state,reason='' if state=='computed' else '部分列未满足数值定义条件' if state=='partial' else '未满足数值定义条件',missing_columns=missing)
    except Unavailable as error:return {fid+'.value':None},dict(feature_id=fid,status=error.status,reason=str(error))
    except Exception as error:
        return {fid+'.value':None},dict(feature_id=fid,status='error',reason=f'{type(error).__name__}: {error}')

def serializable(ctx,rec):
    sids={t.i:sn for sn,s in enumerate(ctx.sentences) for t in s}
    rec['tokens']=[dict(token_id=t.i,sentence_id=sids[t.i],word=t.text,lemma=t.lemma_,pos=t.pos_,tag=t.tag_,morph=str(t.morph),dep=t.dep_,head=t.head.i,start=t.idx,end=t.idx+len(t.text),is_punctuation=t.is_punct,lookup_key=ctx.key(t)) for t in ctx.tokens]
    positions={t.i:i for i,t in enumerate(ctx.words)}
    for row in rec['tokens']:
        row['letters']=sum(c.isalpha() for c in row['word'])
        if ctx.syllables is not None and row['token_id'] in positions:
            index=positions[row['token_id']];phones=ctx.pronunciations[index]
            row.update(syllables=ctx.syllables[index],cmudict_lookup_key=row['word'].casefold(),phonemes=phones,stress=''.join(p[-1] for p in phones if p[-1].isdigit()) if phones else None)
    rec['sentences']=[dict(sentence_id=sn,start=s.start_char,end=s.end_char,text=s.text,word_count=sum(not t.is_punct and not t.is_space for t in s)) for sn,s in enumerate(ctx.sentences)]
    rec['details'].update(ctx.details)

def stream_table(path,records,extract,extra_fields=('doc_id',)):
    fields=set(extra_fields)
    for record in records():
        for row in extract(record):fields.update(row)
    temp=path.with_suffix('.csv.partial');path.parent.mkdir(parents=True,exist_ok=True)
    with temp.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(extra_fields)+sorted(fields-set(extra_fields)));writer.writeheader()
        for rec in records():
            for row in extract(rec):
                row=clean(row)
                writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    os.replace(temp,path)

def run(job):
    global cancelled
    cancelled=False;signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
    resources.activate()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    documents,file_hashes=input_documents(job)
    output=Path(job['output']).expanduser().resolve()
    if output.exists() and any(output.iterdir()) and not (output/'run.json').exists():raise ValueError('输出目录已有其他文件，请选择专属的新目录')
    output.mkdir(parents=True,exist_ok=True)
    selected=job.get('features',sorted(catalogue.DEFAULT));known={r['id'] for r in catalogue.catalogue()}
    unknown=set(selected)-known
    if unknown:raise ValueError('未知指标ID：'+', '.join(sorted(unknown)))
    selected=sorted(set(selected));options=dict(job.get('options',{}));options.setdefault('seed',1729)
    options.setdefault('window',50);options.setdefault('hdd_sample',42);options.setdefault('mtld_threshold',.72);options.setdefault('token_unit','wordform')
    for key in ['window','hdd_sample','random_permutations','network_max_nodes','taylor_window','character_ngram_order']:
        if key in options and (type(options[key]) is not int or options[key]<1):raise ValueError(key+'需要正整数')
    if type(options['seed']) is not int or options['seed']<0:raise ValueError('seed需要非负整数')
    if not 0<options['mtld_threshold']<1:raise ValueError('MTLD阈值须在0与1之间')
    if options.get('semantic_backend','sbert') not in {'sbert','fasttext'}:raise ValueError('语义后端须为sbert或fasttext')
    code_hashes={str(p.relative_to(ROOT)):sha(p) for directory in ['engine','data','native'] for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in {'.py','.csv','.json','.R','.cpp'} and '__pycache__' not in p.parts}
    identity=dict(version=__version__,code_hashes=code_hashes,inputs=file_hashes,features=selected,options=options,text_column=job.get('text_column','text'),encoding=job.get('encoding','utf-8-sig'),resources=resources.snapshot(),versions=versions())
    signature=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    previous=output/'run.json'
    if previous.exists():
        prior=json.loads(previous.read_text())
        if prior.get('signature')!=signature:raise ValueError('此输出目录属于另一输入、参数或资源版本，请选择新目录')
    runmeta=dict(signature=signature,identity=identity,state='running',started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),offset_unit='Unicode codepoints; Apple checker ranges are UTF-16',dependency_nodes='spaCy tokens including punctuation; ROOT self-loop excluded',corpus_order='input order; TXT folder lexicographic path order',resources=resources.snapshot())
    started=time.perf_counter()
    atomic_json(previous,runmeta)
    checkpoint=output/'.checkpoint';checkpoint.mkdir(exist_ok=True)
    database=sqlite3.connect(checkpoint/'state.sqlite3');database.execute('CREATE TABLE IF NOT EXISTS stages (doc_id TEXT, stage TEXT, PRIMARY KEY(doc_id,stage))')
    stages=['base']+[k for k in ['syntax','sbert','causal','mlm','coref'] if any(catalogue.route(fid)==k for fid in selected)]
    total=len(documents)*len(stages);done=0
    emit('started',total=total,documents=len(documents),output=str(output),stages=stages)
    import spacy
    nlp=spacy.load('en_core_web_sm');nlp.max_length=max(nlp.max_length,max(map(lambda r:len(r['text']),documents))+1)
    paths={doc['id']:checkpoint/(hashlib.sha256(doc['id'].encode()).hexdigest()+'.json') for doc in documents}
    source={d['id']:d for d in documents}
    def record_iter():
        for d in documents:
            p=paths[d['id']]
            if p.exists():yield json.loads(p.read_text())
    try:
        for stage in stages:
            if cancelled:break
            fids=[f for f in selected if (catalogue.route(f) in {'base','lexical','configured','pending'} if stage=='base' else catalogue.route(f)==stage)]
            for doc in documents:
                if cancelled:break
                done+=1;path=paths[doc['id']]
                completed=database.execute('SELECT 1 FROM stages WHERE doc_id=? AND stage=?',(doc['id'],stage)).fetchone()
                failed=False
                if completed and job.get('retry_failed',False) and path.exists():
                    failed=any(s['feature_id'] in fids and s['status']=='error' for s in json.loads(path.read_text())['statuses'])
                if completed and not failed:
                    emit('progress',completed=done,total=total,document_id=doc['id'],stage=stage,message='复用已完成阶段');continue
                rec=json.loads(path.read_text()) if path.exists() else dict(id=doc['id'],meta=doc['meta'],sha256=doc['sha256'],features={},statuses=[],details={})
                try:
                    bytepath=path.with_suffix('.spacy')
                    if bytepath.exists():
                        from spacy.tokens import Doc
                        parsed=Doc(nlp.vocab).from_bytes(bytepath.read_bytes());ctx=Text(doc['text'],lambda _:parsed,options)
                    else:
                        ctx=Text(doc['text'],nlp,options);bytepath.write_bytes(ctx.doc.to_bytes())
                    rec['statuses']=[s for s in rec['statuses'] if s['feature_id'] not in fids]
                    for fid in fids:
                        if cancelled:break
                        if not ctx.n and fid not in {'LEN01','LEN02','LEN03','LEN04','LEN05','QC05'}:
                            values,state=result(fid,lambda:(_ for _ in ()).throw(Unavailable('空文本','undefined')))
                        else:values,state=result(fid,lambda fid=fid:calculate(fid,ctx,catalogue.route(fid)))
                        rec['features']={k:v for k,v in rec['features'].items() if not k.startswith(fid+'.')}
                        rec['features'].update(values);rec['statuses'].append(state)
                    if cancelled:break
                    serializable(ctx,rec)
                    atomic_json(path,rec)
                    database.execute('INSERT OR REPLACE INTO stages VALUES (?,?)',(doc['id'],stage));database.commit()
                except Exception as error:
                    rec['statuses'].append(dict(feature_id='document',status='error',reason=f'{type(error).__name__}: {error}'));atomic_json(path,rec)
                emit('progress',completed=done,total=total,document_id=doc['id'],stage=stage,message='已完成 '+doc['id'])
            if stage in {'sbert','causal','mlm','coref'}:
                from .models import release
                release()
            if stage=='syntax':
                from .syntax import pipeline
                pipeline.cache_clear()
        corpus_fids=[f for f in selected if catalogue.route(f)=='corpus'];corpus_values={};corpus_status=[];corpus_details={}
        if not cancelled and corpus_fids:
            from .corpus import Corpus
            lightweight=[]
            for r in record_iter():
                words=[t for t in r.get('tokens',[]) if not t['is_punctuation']];sentences=[[t['lookup_key'] for t in words if t['sentence_id']==s['sentence_id']] for s in r.get('sentences',[])]
                lightweight.append(dict(id=r['id'],meta=r['meta'],text=source[r['id']]['text'],keys=[t['lookup_key'] for t in words],sentences=sentences,token_sentences=[[t['word'] for t in words if t['sentence_id']==s['sentence_id']] for s in r.get('sentences',[])],pos_sentences=[[(t['lookup_key'],t['pos']) for t in words if t['sentence_id']==s['sentence_id']] for s in r.get('sentences',[])],details={}))
            corpus=Corpus(lightweight,options)
            for fid in corpus_fids:
                if cancelled:break
                emit('progress',completed=done,total=total,message='计算语料层 '+fid,stage='corpus')
                if fid in catalogue.CORPUS_SCOPE:
                    values,state=result(fid,lambda fid=fid:corpus.measure(fid,lightweight[0]));corpus_values.update(values);corpus_status.append(state)
                else:
                    for r in lightweight:
                        p=paths[r['id']];rec=json.loads(p.read_text());values,state=result(fid,lambda fid=fid,r=r:corpus.measure(fid,r));rec['features'].update(values);rec['statuses']=[s for s in rec['statuses'] if s['feature_id']!=fid]+[state];rec['details'].update(r['details']);atomic_json(p,rec)
            corpus_details=corpus.details
        emit('progress',message='整理研究资料',stage='export',completed=done,total=total)
        stream_table(output/'features.csv',record_iter,lambda r:[dict(doc_id=r['id'],**{'meta.'+k:v for k,v in r['meta'].items()},**r['features'])])
        stream_table(output/'feature_status.csv',record_iter,lambda r:[dict(doc_id=r['id'],**s) for s in r['statuses']])
        stream_table(output/'tokens.csv',record_iter,lambda r:[dict(doc_id=r['id'],**t) for t in r.get('tokens',[])])
        stream_table(output/'sentences.csv',record_iter,lambda r:[dict(doc_id=r['id'],**s) for s in r.get('sentences',[])])
        stream_table(output/'word_frequency.csv',record_iter,lambda r:[dict(doc_id=r['id'],word=w,frequency=v) for w,v in Counter(t['lookup_key'] for t in r.get('tokens',[]) if not t['is_punctuation']).items()])
        detail_names={k for r in record_iter() for k in r['details']}
        for name in sorted(detail_names):stream_table(output/'details'/(name+'.csv'),record_iter,lambda r,name=name:[dict(doc_id=r['id'],**x) for x in r['details'].get(name,[])])
        if corpus_values:csv_write(output/'corpus_features.csv',[dict(corpus_id='all_inputs',**corpus_values)])
        if corpus_status:csv_write(output/'corpus_status.csv',corpus_status)
        for name,rows in corpus_details.items():csv_write(output/'corpus'/(name+'.csv'),rows)
        headers=[]
        with (output/'features.csv').open(encoding='utf-8-sig',newline='') as f:headers=next(csv.reader(f))
        recipes={r['id']:r for r in catalogue.catalogue()}
        fields=[]
        for h in headers+list(corpus_values):
            fid=h.split('.',1)[0];recipe=recipes.get(fid)
            if recipe:fields.append(dict(column=h,feature_id=fid,method_id=recipe['method_id'],scope=recipe['scope'],definition=recipe['definition'],source_ids=recipe['source_ids'],parameters=options))
        csv_write(output/'field_dictionary.csv',fields)
        atomic_json(output/'execution_manifest.json',[recipes[f] for f in selected])
        counts=Counter(s['status'] for r in record_iter() for s in r['statuses']);counts.update(s['status'] for s in corpus_status)
        runmeta.update(state='cancelled' if cancelled else 'complete',finished_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),status_counts=dict(counts),documents=len(documents),versions=versions(),outputs={str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file() and '.checkpoint' not in p.parts and p.name!='run.json'})
        runmeta['elapsed_seconds']=time.perf_counter()-started
        runmeta['peak_memory_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        atomic_json(previous,runmeta);emit('finished',state=runmeta['state'],output=str(output),status_counts=dict(counts),documents=len(documents))
    except Exception as error:
        runmeta.update(state='failed',error=f'{type(error).__name__}: {error}',finished_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
        atomic_json(previous,runmeta)
        raise
    finally:database.close()
    return runmeta
