import re, json, subprocess, itertools, math
from .util import ROOT, Unavailable, ratio, summary
from . import resources

def matches(token,rule):
    for key,value in [('pos',token.pos_),('tag',token.tag_),('lemma',token.lemma_.casefold()),('word',token.text.casefold()),('dep',token.dep_)]:
        if key in rule and value not in rule[key]:return False
    for key,values in rule.get('morph',{}).items():
        if not set(values)&set(token.morph.get(key)):return False
    return True

def measure(fid,ctx):
    if fid=='DEP15':
        ctx.dependencies();rows=[];values={'gamma':[],'delta':[],'omega':[]}
        for r in ctx.details['dependency_sentences']:
            n=r['n'];edges=r['edge_list'];d=r['total_length']
            if n<=2:continue
            if n>500:raise Unavailable('精确优化助手支持最多500节点；请明确分句或选择较短句')
            if n<=8:
                dmin=min(sum(abs(p[a]-p[b]) for a,b in edges) for p in itertools.permutations(range(n)))
            else:
                conf=resources.configuration('lal')
                p=subprocess.run([conf['executable']],input=json.dumps(dict(n=n,edges=edges)),text=True,capture_output=True,check=True,timeout=300)
                result=json.loads(p.stdout)
                if result.get('exact') is not True:raise Unavailable('LAL助手未证明精确求解','resource_invalid')
                dmin=result['minimum']
            baseline=(n*n-1)/3
            vals=dict(gamma=ratio(d,dmin),delta=d-dmin,omega=ratio(baseline-d,baseline-dmin))
            rows.append(dict(sentence_id=r['sentence_id'],n=n,d=d,dmin=dmin,random_mean=baseline,**vals))
            for k,v in vals.items():values[k].append(v)
        ctx.details['dependency_optimality']=rows
        return {k:v for name,vs in values.items() for k,v in summary(vs,'DEP15.'+name).items()}
    if fid=='STY06':
        conf=resources.configuration('biber');zs={};rows=[]
        for feature in conf['features']:
            scale=feature.get('scale',1000);sequence=feature.get('sequence')
            if sequence:
                count=0
                for s in ctx.sentences:
                    ts=[t for t in s if not t.is_punct and not t.is_space]
                    count+=sum(all(matches(ts[i+j],rule) for j,rule in enumerate(sequence)) for i in range(len(ts)-len(sequence)+1))
            else:count=sum(matches(t,feature['rule']) for t in ctx.words)
            observed=ratio(scale*count,ctx.n);sd=feature['reference_sd']
            if sd<=0:raise Unavailable('Biber参照标准差必须>0','resource_invalid')
            z=(observed-feature['reference_mean'])/sd if observed is not None else None
            zs[feature['id']]=z;rows.append(dict(feature_id=feature['id'],count=count,normalized=observed,z=z))
        ctx.details['biber_features']=rows;out={}
        for dimension in conf['dimensions']:
            weights=dimension['weights']
            if any(k not in zs or zs[k] is None for k in weights):out['STY06.'+dimension['id']]=None
            else:out['STY06.'+dimension['id']]=sum(zs[k]*w for k,w in weights.items())
        return out
    if fid in {'QC01','QC02'}:
        if not hasattr(ctx,'_system_checks'):
            helper=ROOT/'tools/system-check'
            if not helper.exists():raise Unavailable('系统校对助手仅在Mac安装包中可用','resource_required')
            p=subprocess.run([str(helper)],input=json.dumps({'text':ctx.raw}),text=True,capture_output=True,timeout=30,check=True)
            ctx._system_checks=json.loads(p.stdout);ctx.details['system_checker_issues']=ctx._system_checks.get('issues',[])
        kind='grammar' if fid=='QC01' else 'spelling';rows=[r for r in ctx._system_checks['issues'] if r['kind']==kind]
        return {fid+'.apple_'+kind+'_flags_per_word':ratio(len(rows),ctx.n),fid+'.flags':len(rows)}
    if fid=='QC03':
        rules={'repeated_punctuation':r'[!?]{2,}','space_before_comma_period':r' +[,.;:]','multiple_internal_spaces':r'(?<=\S)[ \t]{2,}(?=\S)'}
        rows=[dict(rule=name,start=m.start(),end=m.end(),text=m.group()) for name,pattern in rules.items() for m in re.finditer(pattern,ctx.raw)]
        ctx.details['mechanics_flags']=rows
        return {'QC03.surface_flags_per_word':ratio(len(rows),ctx.n),'QC03.surface_flags':len(rows)}
    raise Unavailable('缺少指定配置')
