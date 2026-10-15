from __future__ import annotations
import math, re
from collections import Counter, defaultdict
import numpy as np
from . import resources
from .util import Unavailable, ratio, summary

NORM_FIELDS={'SEM01':('aoa','aoa'),'SEM02':('concreteness','concreteness'),
 'SEM03':('mrc','familiarity'),'SEM04':('mrc','imageability'),
 'SEM05':('vad','valence'),'SEM06':('vad','arousal'),'SEM07':('vad','dominance'),
 'SEM11':('semd','semd'),'MOR01':('morpholex','morphemes'),'MOR02':('morpholex','prefixes'),
 'MOR03':('morpholex','suffixes'),'MOR04':('morpholex','roots'),
 'MOR05':('morpholex','family_size'),'MOR06':('morpholex','family_frequency')}

def lookup(fid,ctx,resource,field,content_only=True,require_valid=True):
    lex=resources.table(resource)
    eligible=[t for t in ctx.words if not content_only or t.pos_ in {'NOUN','VERB','ADJ'}]
    vals=[]; types={}; rows=[]
    for t in eligible:
        key=t.text.casefold(); value=lex.get(key,{}).get(field)
        vals.append(value)
        if value is not None: types[key]=value
        rows.append(dict(token_id=t.i,word=t.text,lookup_key=key,resource=resource,field=field,value=value))
    ctx.details.setdefault('lexicon_matches',[]).extend(rows)
    out=summary(vals,fid+'.'+field+'.token'); out.update(summary(types.values(),fid+'.'+field+'.type'))
    out[fid+'.eligible_n']=len(eligible)
    out[fid+'.token_coverage']=ratio(sum(v is not None for v in vals),len(vals))
    out[fid+'.'+field+'.token_coverage']=out[fid+'.token_coverage']
    out[fid+'.type_coverage']=ratio(len(types),len({t.text.casefold() for t in eligible}))
    if require_valid and not any(v is not None for v in vals): raise Unavailable('资源未覆盖任何合格词','coverage_insufficient')
    return out

def phrase_matches(ctx, name):
    lex=resources.table(name); groups=defaultdict(list)
    for phrase,row in lex.items():
        words=tuple(phrase.split())
        if words: groups[words[0]].append((words,row))
    rows=[]
    for sn,s in enumerate(ctx.sentences):
        ts=[t for t in s if not t.is_punct and not t.is_space]; keys=[t.text.casefold() for t in ts]
        for i,key in enumerate(keys):
            for phrase,row in groups.get(key,[]):
                if tuple(keys[i:i+len(phrase)])==phrase:
                    rows.append(dict(sentence_id=sn,word=' '.join(phrase),category=row.get('category','all'),token_ids=[t.i for t in ts[i:i+len(phrase)]]))
    ctx.details[name+'_matches']=rows
    return rows

def lexical_measure(fid,ctx):
    if fid in NORM_FIELDS: return lookup(fid,ctx,*NORM_FIELDS[fid])
    if fid=='SEM08':
        fields=resources.TABLES['lancaster'][1]; out={}
        for f in fields: out.update(lookup(fid,ctx,'lancaster',f,require_valid=False))
        return out
    if fid=='FREQ01': return lookup(fid,ctx,'subtlex','frequency_pm',False)
    if fid=='FREQ02': return lookup(fid,ctx,'subtlex','lg10wf',False)
    if fid=='FREQ06':
        lex=resources.table('subtlex'); field='lg10cd' if any('lg10cd' in x for x in lex.values()) else 'contextual_diversity'
        return lookup(fid,ctx,'subtlex',field,False)
    if fid=='FREQ03':
        try: from wordfreq import zipf_frequency
        except ImportError: raise Unavailable('请下载wordfreq资源包','resource_required')
        vals=[zipf_frequency(t.text,'en',wordlist='large') for t in ctx.words]
        return {**summary(vals,'FREQ03.wordfreq_zipf'),'FREQ03.zero_frequency_rate':ratio(sum(v==0 for v in vals),ctx.n)}
    if fid in {'FREQ04','FREQ05','FREQ09'}:
        lex=resources.table('subtlex'); matched=[lex.get(t.text.casefold()) for t in ctx.words]
        valid=[r for r in matched if r and r.get('frequency_pm') is not None]
        if fid=='FREQ09': return {'FREQ09.subtlex_token_coverage':ratio(sum(r is not None for r in matched),ctx.n),'FREQ09.subtlex_type_coverage':ratio(sum(w in lex for w in {t.text.casefold() for t in ctx.words}),len(set(t.text.casefold() for t in ctx.words)))}
        if not valid: raise Unavailable('没有匹配的参考词频','coverage_insufficient')
        if fid=='FREQ04':
            count=sum(r['frequency_pm']<ctx.options.get('low_frequency_pm',1.) for r in valid)
            return {'FREQ04.low_frequency_pm_threshold':ctx.options.get('low_frequency_pm',1.),'FREQ04.low_frequency_among_covered':ratio(count,len(valid)),'FREQ04.identified_low_per_all_tokens':ratio(count,ctx.n),'FREQ04.coverage':ratio(len(valid),ctx.n)}
        if not any(r and 'rank' in r for r in matched): raise Unavailable('SUBTLEX导入资源缺少明确rank字段','resource_required')
        bands=ctx.options.get('frequency_bands',[1000,2000,5000,10000]); out={}; low=0
        for high in bands:
            out[f'FREQ05.rank_{low+1}_{high}']=ratio(sum(r is not None and low<r.get('rank',math.inf)<=high for r in matched),ctx.n); low=high
        out['FREQ05.unmatched']=ratio(sum(r is None for r in matched),ctx.n); return out
    if fid=='FREQ07':
        path=resources.CACHE/'resources/register_frequency/table.json'
        if not path.exists(): raise Unavailable('需导入register_frequency资源','resource_required')
        import json
        tables=defaultdict(dict)
        for r in json.loads(path.read_text()): tables[r.get('register','unspecified')][r['word']]=r.get('frequency_pm')
        out={}
        for register,lex in tables.items():
            values=[lex.get(t.text.casefold()) for t in ctx.words]
            out.update(summary(values,'FREQ07.'+register)); out['FREQ07.'+register+'.coverage']=ratio(sum(v is not None for v in values),ctx.n)
        return out
    if fid in {'FREQ08','SEM12','DIS04','STY01','STY04','STY05','READ07'}:
        name={'FREQ08':'academic','SEM12':'semantic_categories','DIS04':'connectives','STY01':'function_words','STY04':'nominalizations','STY05':'stance','READ07':'easy_words'}[fid]
        rows=phrase_matches(ctx,name); covered=set(i for row in rows for i in row['token_ids'])
        if fid=='READ07':
            if not ctx.n or not ctx.s: raise Unavailable('空文本','undefined')
            difficult=100*(ctx.n-len(covered))/ctx.n
            return {'READ07.dale_chall':.1579*difficult+.0496*ctx.n/ctx.s+(3.6365 if difficult>5 else 0),'READ07.difficult_percent':difficult}
        groups=defaultdict(set)
        for r in rows: groups[r['category']].update(r['token_ids'])
        out={fid+'.'+cat+'.covered_token_rate':ratio(len(ids),ctx.n) for cat,ids in groups.items()}
        out[fid+'.all_covered_token_rate']=ratio(len(covered),ctx.n)
        if fid=='STY01':
            counts=Counter(r['word'] for r in rows)
            out.update({'STY01.word_'+w:ratio(v,ctx.n) for w,v in counts.items()})
        return out
    if fid=='MOR08':
        lex=resources.table('morpholex'); process=ctx.options.get('morphological_process')
        if not process: raise Unavailable('请在参数中指定morphological_process')
        members={w for w,row in lex.items() if row.get('process')==process}; counts=Counter(t.text.casefold() for t in ctx.words if t.text.casefold() in members)
        return {'MOR08.productivity':ratio(sum(v==1 for v in counts.values()),sum(counts.values())),'MOR08.process_tokens':sum(counts.values())}
    if fid in {'SEM09','SEM10'}:
        try:
            from nltk.corpus import wordnet as wn
            wn.ensure_loaded()
        except (ImportError,LookupError): raise Unavailable('需要WordNet资源包','resource_required')
        mapping={'NOUN':'n','VERB':'v','ADJ':'a','ADV':'r'}; values=[]
        senses=ctx.options.get('wordnet_senses',{})
        if fid=='SEM10' and not senses: raise Unavailable('Hypernym depth需要明确的synset选择；参数wordnet_senses提供lemma→synset映射')
        for t in ctx.words:
            if t.pos_ not in mapping: continue
            synsets=wn.synsets(t.lemma_,pos=mapping[t.pos_])
            if fid=='SEM09': values.append(len(synsets) if synsets else None)
            else:
                name=senses.get(t.lemma_.casefold())
                values.append(wn.synset(name).max_depth() if name else None)
        return summary(values,fid+('.synset_count' if fid=='SEM09' else '.selected_synset_max_depth'))
    if fid in {'PHO03','PHO04','PHO05','PHO06'}:
        try: from rapidfuzz.distance import Levenshtein
        except ImportError: raise Unavailable('请下载词典邻域资源包','resource_required')
        from .core import pronunciation_lexicon
        lex={w:ps[0] for w,ps in pronunciation_lexicon().items() if re.fullmatch('[a-z]+',w)}
        # Cache unique target words, not repeated tokens.
        values={}
        phones={w:tuple(p[:-1] if p[-1:].isdigit() else p for p in ps) for w,ps in lex.items()}
        single=Counter(p for ps in lex.values() for p in ps); pairs=Counter((a,b) for ps in lex.values() for a,b in zip(ps,ps[1:]))
        for t in ctx.words:
            word=t.text.casefold()
            if word in values: continue
            if fid=='PHO03': values[word]=sum(len(w)==len(word) and sum(a!=b for a,b in zip(w,word))==1 for w in lex)
            elif fid=='PHO04':
                ds=sorted(Levenshtein.distance(word,w) for w in lex if w!=word); values[word]=sum(ds[:20])/20 if len(ds)>=20 else None
            elif word not in lex: values[word]=None
            elif fid=='PHO05':
                target=phones[word]; ds=sorted(Levenshtein.distance(target,p) for w,p in phones.items() if w!=word); values[word]=sum(ds[:20])/20 if len(ds)>=20 else None
            else:
                target=lex[word]; values[word]=float(np.mean([pairs[(a,b)]/sum(pairs.values()) for a,b in zip(target,target[1:])])) if len(target)>1 else None
        ctx.details.setdefault('phonological_neighbors',[]).extend(dict(word=w,value=v,feature=fid) for w,v in values.items())
        return summary([values[t.text.casefold()] for t in ctx.words],fid+'.cmudict_dictionary')
    if fid=='SYN22':
        lex=resources.table('vac'); values=[]
        for t in ctx.words:
            if t.pos_!='VERB': continue
            construction='+'.join(sorted(c.dep_ for c in t.children if c.dep_ in {'dobj','iobj','nsubj','ccomp','xcomp','prep'}))
            key=t.lemma_.casefold()+'|'+construction; row=lex.get(key,{})
            values.append(row.get('frequency_pm'))
        return summary(values,'SYN22.lemma_dependency_frame_reference_pm')
    raise Unavailable('需要具体外部资源或参数')
