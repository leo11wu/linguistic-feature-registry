"""Reusable, model-free measurements and frozen corpus references. No NLP or fitting imports."""
from collections import Counter, defaultdict
from pathlib import Path
import json, math
from .util import atomic_json, csv_write, sha


def choices(options, documents):
    defaults=dict(reference_mode='batch',reference_path='',corpus_group_column='',
                  partition_column='',pair_column='',network_edge='adjacent',
                  network_window=2,network_directed=True,network_min_count=1)
    for key,value in defaults.items():options.setdefault(key,value)
    if options['reference_mode'] not in {'batch','external'}:raise ValueError('参照模式须为本批或外部提取结果')
    if options['network_edge'] not in {'adjacent','window'}:raise ValueError('网络边须为相邻词或句内窗口')
    if type(options['network_directed']) is not bool:raise ValueError('网络方向需要布尔值')
    for key in ['network_window','network_min_count']:
        if type(options[key]) is not int or options[key]<1:raise ValueError(key+'需要正整数')
    if options.get('bundle_order',4) not in {2,3,4}:raise ValueError('词块长度须为2、3或4')
    for key in ['bundle_min_frequency','bundle_min_documents']:
        if key in options and (type(options[key]) is not int or options[key]<1):raise ValueError(key+'需要正整数')
    for key in ['corpus_group_column','partition_column']:
        field=options[key]
        if field and any(not str(d['meta'].get(field,'')).strip() for d in documents):
            raise ValueError('元数据列缺失或有空值：'+field)
    if options['reference_mode']=='external' and not options['reference_path']:
        raise ValueError('请选择作为参照的提取结果目录')
    return {key:options[key] for key in defaults}


def lightweight(record, text=''):
    words=[t for t in record.get('tokens',[]) if not t['is_punctuation']]
    grouped=defaultdict(list)
    for token in words:grouped[token['sentence_id']].append(token)
    sentences=[grouped[s['sentence_id']] for s in record.get('sentences',[])]
    return dict(id=record['id'],meta=record['meta'],text=text,keys=[t['lookup_key'] for t in words],
                sentence_ids=[s['sentence_id'] for s in record.get('sentences',[])],
                sentences=[[t['lookup_key'] for t in s] for s in sentences],
                token_sentences=[[t['word'] for t in s] for s in sentences],
                pos_sentences=[[(t['lookup_key'],t['pos']) for t in s] for s in sentences],details={})


def load_reference(options):
    if options['reference_mode']!='external':return None,None
    path=Path(options['reference_path']).expanduser().resolve()
    if path.is_dir():
        run=path/'run.json'
        if not run.is_file() or json.loads(run.read_text(encoding='utf-8-sig')).get('state')!='complete':
            raise ValueError('外部参照须来自完整提取结果')
        path=path/'reference.json'
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('schema_version')!=1:raise ValueError('不支持此参照格式；请选择0.2版提取结果')
    if data.get('token_unit')!=options['token_unit']:raise ValueError('参照与当前提取的词形/lemma口径不同')
    if data.get('annotation')!='spacy.en_core_web_sm.3.8.0':raise ValueError('参照的标注方案不匹配')
    # Verify a reference before it can affect measurements, including grouped/empty tables.
    FrozenReference(data)
    return data,dict(path=str(path),sha256=sha(path),source_signature=data.get('source_signature'),
                     partition_column=data.get('partition_column',''),documents=data['documents'])


class FrozenReference:
    def __init__(self,data):
        def counter(rows,width):
            out=Counter()
            for row in rows:
                if not isinstance(row,list) or len(row)!=width+1:raise ValueError('参照计数表格式错误')
                *keys,n=row
                if not all(isinstance(x,str) for x in keys) or type(n) is not int or n<1:raise ValueError('参照计数需要字符串键和正整数')
                key=keys[0] if width==1 else tuple(keys)
                if key in out:raise ValueError('参照中有重复计数键')
                out[key]=n
            return out
        self.counter=counter(data['counts'],1)
        self.ngrams={i:counter(data['ngrams'][str(i)],i) for i in [2,3,4]}
        self.ranges={i:counter(data['ranges'][str(i)],i) for i in [2,3,4]}
        self.pairs=self.ngrams[2];self.left=Counter();self.right=Counter()
        for (a,b),n in self.pairs.items():self.left[a]+=n;self.right[b]+=n
        self.total_pairs=sum(self.pairs.values())
        self.partitions={p:counter(rows,1) for p,rows in data['partitions'].items()}
        self.sizes=Counter({p:sum(c.values()) for p,c in self.partitions.items()})
        if sum(self.counter.values())!=sum(self.sizes.values()):raise ValueError('参照分块总量与词频总量不符')
        combined=Counter()
        for c in self.partitions.values():combined.update(c)
        if combined!=self.counter:raise ValueError('参照分块词频与总体不符')
        self.pair_stats={}
        from .stats import association
        for (a,b),n in self.pairs.items():
            self.pair_stats[(a,b)]=dict(left=a,right=b,joint=n,left_total=self.left[a],right_total=self.right[b],event_total=self.total_pairs,
                **association(n,self.left[a]-n,self.right[b]-n,self.total_pairs-self.left[a]-self.right[b]+n))


def freeze_reference(corpus,options,signature):
    def rows(counter):
        return [[*k,n] if isinstance(k,tuple) else [k,n] for k,n in sorted(counter.items())]
    return dict(schema_version=1,annotation='spacy.en_core_web_sm.3.8.0',token_unit=options['token_unit'],
                source_signature=signature,partition_column=options['partition_column'],documents=len(corpus.records),
                counts=rows(corpus.counter),ngrams={str(i):rows(corpus.ngrams[i]) for i in [2,3,4]},
                ranges={str(i):rows(corpus.ranges[i]) for i in [2,3,4]},
                partitions={p:rows(c) for p,c in sorted(corpus.partitions.items())})


def export_observations(output, records, corpora, options, signature, reference_info, light=None):
    """Long tables retain identifiers and units, and never fit a model during extraction."""
    output=Path(output);folder=output/'observations';folder.mkdir(exist_ok=True)
    tables=[]
    light=light if light is not None else [lightweight(r) for r in records()]
    def write(name,label,unit,rows,fields,x='',y='',weight='',group='',models=None,kind='relation'):
        path=folder/(name+'.csv');csv_write(path,rows,fields)
        tables.append(dict(id=name,label=label,path=str(path.relative_to(output)),unit=unit,x=x,y=y,
                           weight=weight,group=group,models=models or ['linear','power'],kind=kind,positive_only=name=='taylor_points',sha256=sha(path)))
    def sentence_rows():
        for rec in light:
            for sid,sentence in zip(rec['sentence_ids'],rec['token_sentences']):
                n=len(sentence);letters=sum(c.isalpha() for word in sentence for c in word)
                yield dict(doc_id=rec['id'],sentence_id=sid,sentence_words=n,
                           mean_word_letters=letters/n if n else None,total_word_letters=letters)
    write('sentence_measures','句长与句内词长','sentence',sentence_rows(),
          ['doc_id','sentence_id','sentence_words','mean_word_letters','total_word_letters'],
          'sentence_words','mean_word_letters',group='doc_id',models=['linear','power','menzerath_altmann'])
    def length_rows():
        for rec in light:
            c=Counter(sum(c.isalpha() for c in word) for sentence in rec['token_sentences'] for word in sentence)
            c.pop(0,None)
            for letters,count in sorted(c.items()):yield dict(doc_id=rec['id'],letters=letters,count=count)
    write('word_lengths','词长分布（原词字母数）','word token, frequency compressed',length_rows(),
          ['doc_id','letters','count'],'letters',weight='count',group='doc_id',kind='distribution',
          models=['zero_truncated_poisson','geometric'])
    def corpus_rows(name):
        for scope_id,corpus in corpora.items():
            corpus.laws()
            for row in corpus.details[name]:yield dict(corpus_id=scope_id,**row)
    write('rank_frequency','词频与排名','word type',corpus_rows('rank_frequency'),
          ['corpus_id','rank','word','frequency','letters'],'rank','frequency',group='corpus_id',models=['zipf','zipf_mandelbrot'])
    write('frequency_spectrum','词频谱','word type, frequency compressed',corpus_rows('frequency_spectrum'),
          ['corpus_id','frequency','types'],'frequency',weight='types',group='corpus_id',kind='distribution',
          models=['geometric','zero_truncated_poisson','lnre_fzm','lnre_zm','lnre_gigp'])
    write('vocabulary_growth','累计词数与词型增长','prefix of input sequence',corpus_rows('vocabulary_growth'),
          ['corpus_id','tokens','types'],'tokens','types',group='corpus_id',models=['heaps','linear'])
    write('abbreviation','词型频率与词长','word type',corpus_rows('rank_frequency'),
          ['corpus_id','rank','word','frequency','letters'],'frequency','letters',group='corpus_id',models=['pearson','spearman','linear','power'])
    def taylor_rows():
        size=options.get('taylor_window',50)
        for scope_id,corpus in corpora.items():
            count=len(corpus.sequences)//size
            if count<1:continue
            sums=Counter();squares=Counter()
            for start in range(0,count*size,size):
                c=Counter(corpus.sequences[start:start+size]);sums.update(c)
                squares.update({w:n*n for w,n in c.items()})
            for word,total in sorted(sums.items()):
                mu=total/count;variance=max(0,squares[word]/count-mu*mu)
                yield dict(corpus_id=scope_id,word=word,mean=mu,sd_population=math.sqrt(variance),
                           window_tokens=size,complete_windows=count,discarded_tokens=len(corpus.sequences)%size)
    write('taylor_points','固定窗口词频的均值与标准差','word type across complete token windows',taylor_rows(),
          ['corpus_id','word','mean','sd_population','window_tokens','complete_windows','discarded_tokens'],
          'mean','sd_population',group='corpus_id',models=['power_log','power'])
    csv_write(output/'document_metadata.csv',({'doc_id':r['id'],**{'meta.'+k:v for k,v in r['meta'].items()}} for r in light))
    for name,label,unit in [('features','文档特征矩阵','document'),('tokens','词级测量','token'),('sentences','句子记录','sentence'),('pair_features','文本对特征','text pair'),('corpus_features','语料层特征','corpus')]:
        path=output/(name+'.csv')
        if not path.is_file():continue
        tables.append(dict(id=name,label=label,path=path.name,unit=unit,x='',y='',weight='',group='',models=['linear'],kind='relation',sha256=sha(path)))
    atomic_json(output/'analysis_tables.json',dict(schema_version=1,source_signature=signature,tables=tables,
                choices={**{k:options[k] for k in ['token_unit','corpus_group_column','partition_column','pair_column','reference_mode','network_edge','network_window','network_directed','network_min_count']},'reference':reference_info},
                order='input order; TXT folder lexicographic path order; prefixes are not independent samples',
                length_unit='alphabetic characters of original token; word frequency keys may be lemma',
                note='Model-free observations. Correlations, fitted parameters and model comparisons belong to fitting.'))
