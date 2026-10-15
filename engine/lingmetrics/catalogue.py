import csv, json
from collections import Counter
from .util import ROOT
from .lexicons import NORM_FIELDS
from . import resources

PENDING={'DEP16':'NDD原始标点、重编号和聚合规则尚待核验',
         'SYN25':'修订D-Level完整识别规则、冲突和碎片处理尚未形成可验证执行规范',
         'DIS11':'CPIDR 3.2完整37条规则源码尚未取得；DEPID的dobj差异尚待核验'}
LEXICAL=set(NORM_FIELDS)|{'SEM08','SEM09','SEM10','FREQ01','FREQ02','FREQ03','FREQ04','FREQ05','FREQ06','FREQ07','FREQ08','FREQ09','MOR08','SEM12','DIS04','STY01','STY04','STY05','READ07','PHO03','PHO04','PHO05','PHO06','SYN22'}
SYNTAX={*[f'SYN{i:02d}' for i in range(1,18)],'SYN21','SYN23','SYN24'}
MODELS={'DIS08':'sbert','DIS09':'sbert','DIS10':'sbert','DIS12':'sbert','INF04':'causal','INF05':'causal','INF06':'causal','INF08':'causal','INF09':'causal','INF10':'mlm','DIS06':'coref','DIS07':'coref'}
DEFAULT={*[f'LEN{i:02d}' for i in range(1,10)],*[f'LD{i:02d}' for i in range(1,14) if i!=10],*[f'POS{i:02d}' for i in range(1,11)],*[f'DEP{i:02d}' for i in range(1,14)],'MOR07','DIS01','DIS02','DIS03','DIS05','INF01','INF02','INF03','READ01','READ02','READ05','READ06','READ08','READ09','STY03','QC04','QC05'}
CORPUS_SCOPE={'QL01','QL02','QL03','QL04','QL07','QL08','QL09','QL10','QL11','NET01','NET02','NET03','NET04','NET05'}
FIT_ONLY={f'QL{i:02d}' for i in range(1,9)}
PAIR_SCOPE={'STY07'}

def route(fid):
    from .corpus import IDS
    if fid in FIT_ONLY:return 'fit'
    if fid in PENDING:return 'pending'
    if fid in SYNTAX:return 'syntax'
    if fid in MODELS:return MODELS[fid]
    if fid in LEXICAL:return 'lexical'
    if fid in IDS:return 'corpus'
    if fid in {'DEP15','STY06','QC01','QC02','QC03'}:return 'configured'
    return 'base'

def required(fid,options=None):
    if fid in NORM_FIELDS:return [NORM_FIELDS[fid][0]]
    if fid in SYNTAX:return ['stanza']
    if fid in MODELS:
        backend=(options or {}).get('semantic_backend','sbert') if MODELS[fid]=='sbert' else MODELS[fid]
        return [backend]+({'DIS12':['sid'],'INF09':['unigram']}.get(fid,[]))
    mapping={'FREQ01':['subtlex'],'FREQ02':['subtlex'],'FREQ03':['wordfreq'],'FREQ04':['subtlex'],'FREQ05':['subtlex'],'FREQ06':['subtlex'],'FREQ07':['register_frequency'],'FREQ08':['academic'],'FREQ09':['subtlex'],
             'SEM08':['lancaster'],'SEM09':['phonology'],'SEM10':['phonology'],'SEM12':['semantic_categories'],'MOR08':['morpholex'],'DIS04':['connectives'],'STY01':['function_words'],'STY04':['nominalizations'],'STY05':['stance'],'STY06':['biber'],'STY07':['function_words'],'READ07':['easy_words'],'SYN22':['vac'],'QL01':['corpus'],'QL02':['corpus'],'QL03':['corpus'],'QL04':['lnre'],'QL05':['corpus'],'QL06':['corpus'],'DEP15':['lal']}
    if fid in {'PHO03','PHO04','PHO05','PHO06'}:return ['phonology']
    return mapping.get(fid,[])

def catalogue():
    specifications={}
    with (ROOT/'data/paper_measure_specifications.csv').open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):specifications.setdefault(r['feature_id'],[]).append(r)
    installed={r['id'] for r in resources.inventory() if r['installed']}
    rows=[]
    with (ROOT/'data/english_linguistic_feature_registry.csv').open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            fid=r['feature_id'];needs=required(fid);missing=[x for x in needs if x not in installed]
            state='fit_only' if fid in FIT_ONLY else 'method_pending' if fid in PENDING else 'resource_required' if missing else 'ready'
            note='已移至拟合；提取会保留可复用的观测表' if fid in FIT_ONLY else PENDING.get(fid,'需准备：'+', '.join(missing) if missing else '已实现；公式验证与目标语料效度分别记录')
            specs=specifications.get(fid,[])
            variants=[]
            for spec in specs:
                pending=spec['spec_id'] in {'P013','P010','P018','P019','P020','P021','P034','P035','P036'}
                variants.append(dict(spec_id=spec['spec_id'],state='method_pending' if pending else 'implemented',reason=spec['待核细节或变更'] if pending else '独立命名并记录参数；实际计算见运行状态'))
            rows.append(dict(id=fid,category=r['类别'],english=r['英文名称'],name=r['中文名称'],definition=r['定义或计算口径'],caution=r['建模与测量注意点'],sources=r['来源链接'],source_ids=r['来源ID'],specifications=specs,operationalization_states=variants,route=route(fid),workflow='fit' if fid in FIT_ONLY else 'extract',scope='pair' if fid in PAIR_SCOPE else 'corpus' if fid in CORPUS_SCOPE else 'document',required_resources=needs,state=state,note=note,default=fid in DEFAULT,method_id=fid.lower()+'.lingmetrics.0.2'))
    return rows
