from __future__ import annotations
import csv, json, hashlib, importlib.metadata, os, platform, signal, sqlite3, sys, time, traceback, io, resource
from contextlib import ExitStack
from pathlib import Path
from collections import Counter
from . import __version__, resources, catalogue
from .util import ROOT, CACHE, emit, atomic_json, clean, sha, csv_write, Unavailable,local_bytes
from .core import Text, base_measure
from .observations import choices, lightweight, load_reference, freeze_reference, export_observations

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

def export_documents(output,records):
    """Two sequential checkpoint scans for every table; keep one document in memory."""
    schemas={name:{'doc_id'} for name in ['features','feature_status','tokens','sentences','word_frequency']}
    schemas['word_frequency'].update({'word','frequency'})
    def content(rec):
        yield 'features',[dict(doc_id=rec['id'],**{'meta.'+k:v for k,v in rec['meta'].items()},**rec['features'])]
        yield 'feature_status',rec['statuses']
        yield 'tokens',rec.get('tokens',[])
        yield 'sentences',rec.get('sentences',[])
        for name,rows in rec['details'].items():yield 'details/'+name,rows
    for rec in records():
        for name,rows in content(rec):
            fields=schemas.setdefault(name,{'doc_id'})
            for row in rows:fields.update(row)
    headers={name:['doc_id']+sorted(fields-{'doc_id'}) for name,fields in schemas.items()}
    counts=Counter();destinations=[]
    with ExitStack() as stack:
        writers={}
        for name,fields in headers.items():
            path=output/(name+'.csv');path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_suffix('.csv.partial');destinations.append((temp,path))
            handle=stack.enter_context(temp.open('w',encoding='utf-8-sig',newline=''))
            writers[name]=csv.DictWriter(handle,fieldnames=fields);writers[name].writeheader()
        def write(name,doc_id,row):
            # Checkpoints have already passed clean() and strict JSON encoding.
            writers[name].writerow(dict(doc_id=doc_id,**{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items() if k!='doc_id'}))
        for rec in records():
            for name,rows in content(rec):
                for row in rows:write(name,rec['id'],row)
            for word,frequency in Counter(t['lookup_key'] for t in rec.get('tokens',[]) if not t['is_punctuation']).items():
                write('word_frequency',rec['id'],dict(word=word,frequency=frequency))
            counts.update(s['status'] for s in rec['statuses'])
    for temp,path in destinations:os.replace(temp,path)
    return headers['features'],counts

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
    if set(selected)&catalogue.FIT_ONLY:raise ValueError('以下项目已移至拟合页，提取时会保留所需观测表：'+', '.join(sorted(set(selected)&catalogue.FIT_ONLY)))
    selected=sorted(set(selected));options=dict(job.get('options',{}));options.setdefault('seed',1729)
    options.setdefault('window',50);options.setdefault('hdd_sample',42);options.setdefault('mtld_threshold',.72);options.setdefault('token_unit','wordform')
    for key in ['window','hdd_sample','random_permutations','network_max_nodes','taylor_window','character_ngram_order']:
        if key in options and (type(options[key]) is not int or options[key]<1):raise ValueError(key+'需要正整数')
    if type(options['seed']) is not int or options['seed']<0:raise ValueError('seed需要非负整数')
    if not 0<options['mtld_threshold']<1:raise ValueError('MTLD阈值须在0与1之间')
    if options.get('semantic_backend','sbert') not in {'sbert','fasttext'}:raise ValueError('语义后端须为sbert或fasttext')
    analysis_choices=choices(options,documents)
    reference_data,reference_info=load_reference(options)
    code_hashes={str(p.relative_to(ROOT)):sha(p) for directory in ['engine','data','native'] for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in {'.py','.csv','.json','.R','.cpp'} and '__pycache__' not in p.parts}
    identity=dict(version=__version__,code_hashes=code_hashes,inputs=file_hashes,features=selected,options=options,reference=reference_info,text_column=job.get('text_column','text'),encoding=job.get('encoding','utf-8-sig'),resources=resources.snapshot(),versions=versions())
    signature=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    previous=output/'run.json'
    if previous.exists():
        prior=json.loads(previous.read_text())
        if prior.get('signature')!=signature:raise ValueError('此输出目录属于另一输入、参数或资源版本，请选择新目录')
    runmeta=dict(signature=signature,identity=identity,workflow='extract',analysis_choices=analysis_choices,state='running',started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),offset_unit='Unicode codepoints; Apple checker ranges are UTF-16',dependency_nodes='spaCy tokens including punctuation; ROOT self-loop excluded',corpus_order='input order; TXT folder lexicographic path order',resources=resources.snapshot())
    started=time.perf_counter()
    atomic_json(previous,runmeta)
    checkpoint=output/'.checkpoint';checkpoint.mkdir(exist_ok=True)
    database=sqlite3.connect(checkpoint/'state.sqlite3');database.execute('CREATE TABLE IF NOT EXISTS stages (doc_id TEXT, stage TEXT, PRIMARY KEY(doc_id,stage))')
    stages=['base']+[k for k in ['syntax','sbert','causal','mlm','coref'] if any(catalogue.route(fid)==k for fid in selected)]
    total=len(documents)*len(stages);done=0;feature_timings={};phase_timings={}
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
            phase_started=time.perf_counter()
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
                        feature_started=time.perf_counter()
                        if not ctx.n and fid not in {'LEN01','LEN02','LEN03','LEN04','LEN05','QC05'}:
                            values,state=result(fid,lambda:(_ for _ in ()).throw(Unavailable('空文本','undefined')))
                        else:values,state=result(fid,lambda fid=fid:calculate(fid,ctx,catalogue.route(fid)))
                        timing=feature_timings.setdefault(fid,dict(seconds=0.,calls=0))
                        timing['seconds']+=time.perf_counter()-feature_started;timing['calls']+=1
                        rec['features']={k:v for k,v in rec['features'].items() if not k.startswith(fid+'.')}
                        rec['features'].update(values);rec['statuses'].append(state)
                    if cancelled:break
                    serializable(ctx,rec)
                    atomic_json(path,rec,compact=True)
                    database.execute('INSERT OR REPLACE INTO stages VALUES (?,?)',(doc['id'],stage));database.commit()
                except Exception as error:
                    rec['statuses'].append(dict(feature_id='document',status='error',reason=f'{type(error).__name__}: {error}'));atomic_json(path,rec,compact=True)
                emit('progress',completed=done,total=total,document_id=doc['id'],stage=stage,message='已完成 '+doc['id'])
            phase_timings[stage]=time.perf_counter()-phase_started
            if stage in {'sbert','causal','mlm','coref'}:
                from .models import release
                release()
            if stage=='syntax':
                from .syntax import pipeline
                pipeline.cache_clear()
        corpus_fids=[f for f in selected if catalogue.route(f)=='corpus'];corpus_rows=[];corpus_status=[];corpus_details={};corpora={};pair_rows=[];pair_status=[]
        if not cancelled:
            corpus_started=time.perf_counter()
            from .corpus import Corpus
            light=[]
            for r in record_iter():
                light.append(lightweight(r,source[r['id']]['text']))
            global_corpus=Corpus(light,options,selected_features=corpus_fids,reference=reference_data)
            grouped={}
            for r in light:
                group=str(r['meta'][options['corpus_group_column']]) if options['corpus_group_column'] else 'all_inputs'
                grouped.setdefault(group,[]).append(r)
            corpora={key:Corpus(rows,options,selected_features=corpus_fids,reference=reference_data) if options['corpus_group_column'] else global_corpus for key,rows in grouped.items()}
            atomic_json(output/'reference.json',freeze_reference(global_corpus,options,signature))
            if reference_data is not None:atomic_json(output/'reference_applied.json',reference_data)
            def corpus_calculate(corpus,fid,rec):
                missing=[name for name in catalogue.required(fid,options) if not resources.available(name)]
                if missing:raise Unavailable('需准备资源：'+', '.join(missing),'resource_required')
                return corpus.measure(fid,rec)
            per_document=[f for f in corpus_fids if f not in catalogue.CORPUS_SCOPE and f not in catalogue.PAIR_SCOPE]
            for scope_id,corpus in corpora.items():
                values_row=dict(corpus_id=scope_id)
                for fid in [f for f in corpus_fids if f in catalogue.CORPUS_SCOPE]:
                    if cancelled:break
                    emit('progress',completed=done,total=total,message='计算语料层 '+scope_id+' '+fid,stage='corpus')
                    feature_started=time.perf_counter()
                    values,state=result(fid,lambda fid=fid:corpus_calculate(corpus,fid,corpus.records[0]));values_row.update(values);corpus_status.append(dict(corpus_id=scope_id,**state))
                    timing=feature_timings.setdefault(fid,dict(seconds=0.,calls=0));timing['seconds']+=time.perf_counter()-feature_started;timing['calls']+=1
                if len(values_row)>1:corpus_rows.append(values_row)
            for r in light if per_document else []:
                if cancelled:break
                group=str(r['meta'][options['corpus_group_column']]) if options['corpus_group_column'] else 'all_inputs';corpus=corpora[group]
                p=paths[r['id']];rec=json.loads(p.read_text())
                for fid in per_document:
                    if cancelled:break
                    feature_started=time.perf_counter()
                    values,state=result(fid,lambda fid=fid,r=r:corpus_calculate(corpus,fid,r));rec['features'].update(values);rec['statuses']=[s for s in rec['statuses'] if s['feature_id']!=fid]+[state]
                    timing=feature_timings.setdefault(fid,dict(seconds=0.,calls=0));timing['seconds']+=time.perf_counter()-feature_started;timing['calls']+=1
                rec['details'].update(r['details']);atomic_json(p,rec,compact=True)
                emit('progress',completed=done,total=total,message='计算语料参照指标 '+r['id'],stage='corpus')
            if 'STY07' in corpus_fids:
                pairs={};field=options['pair_column']
                for r in light:pairs.setdefault(str(r['meta'].get(field,'')) if field else '',[]).append(r)
                for pair_id,members in pairs.items():
                    if not pair_id or len(members)!=2:
                        pair_status.append(dict(pair_id=pair_id,feature_id='STY07',status='input_required',reason='配对列须有非空值，每个配对值恰好两篇文本',doc_ids=[r['id'] for r in members]));continue
                    values,state=result('STY07',lambda:corpus_calculate(global_corpus,'STY07',members[0]))
                    pair_rows.append(dict(pair_id=pair_id,doc_id_left=members[0]['id'],doc_id_right=members[1]['id'],**values));pair_status.append(dict(pair_id=pair_id,**state))
            for scope_id,corpus in corpora.items():
                for name,rows in corpus.details.items():corpus_details.setdefault(name,[]).extend(dict(corpus_id=scope_id,**row) for row in rows)
            phase_timings['corpus']=time.perf_counter()-corpus_started
        emit('progress',message='整理研究资料',stage='export',completed=done,total=total)
        export_started=time.perf_counter()
        headers,counts=export_documents(output,record_iter)
        if corpus_rows:csv_write(output/'corpus_features.csv',corpus_rows)
        if corpus_status:csv_write(output/'corpus_status.csv',corpus_status)
        if pair_rows:csv_write(output/'pair_features.csv',pair_rows)
        if pair_status:csv_write(output/'pair_status.csv',pair_status)
        for name,rows in corpus_details.items():csv_write(output/'corpus'/(name+'.csv'),rows)
        if not cancelled:export_observations(output,record_iter,corpora,options,signature,reference_info,light=light)
        recipes={r['id']:r for r in catalogue.catalogue()}
        fields=[]
        extra_headers=sorted({k for row in corpus_rows+pair_rows for k in row})
        for h in headers+extra_headers:
            fid=h.split('.',1)[0];recipe=recipes.get(fid)
            if recipe:fields.append(dict(column=h,feature_id=fid,method_id=recipe['method_id'],scope=recipe['scope'],definition=recipe['definition'],source_ids=recipe['source_ids'],parameters=options))
        csv_write(output/'field_dictionary.csv',fields)
        atomic_json(output/'execution_manifest.json',[recipes[f] for f in selected])
        counts.update(s['status'] for s in corpus_status)
        counts.update(s['status'] for s in pair_status)
        phase_timings['export']=time.perf_counter()-export_started
        runmeta['timings']={'phases_seconds':phase_timings,'features':feature_timings,'scope':'current invocation; reused checkpoints excluded; shared work and resource/model loading attributed to first requesting feature'}
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
