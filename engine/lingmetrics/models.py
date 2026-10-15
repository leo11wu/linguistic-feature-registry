from __future__ import annotations
import math, json, gc
from functools import lru_cache
from collections import Counter
import numpy as np
from .util import CACHE, Unavailable, ratio, summary
from .stats import uid, grid_transitions
from . import resources

_loaded=None
def release():
    global _loaded
    _loaded=None; gc.collect()
    from .fasttext_vectors import release as release_fasttext
    release_fasttext()

def load(kind):
    global _loaded
    if _loaded is not None and _loaded[0]==kind: return _loaded[1]
    release(); marker=resources.marker(kind)
    if not marker.exists(): raise Unavailable('请下载模型资源：'+kind,'resource_required')
    meta=json.loads(marker.read_text()); path=meta.get('path')
    if kind=='sbert':
        from sentence_transformers import SentenceTransformer
        result=SentenceTransformer(path,device='cpu',local_files_only=True)
    elif kind in {'causal','mlm'}:
        from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForMaskedLM
        tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True,use_fast=True)
        model=(AutoModelForCausalLM if kind=='causal' else AutoModelForMaskedLM).from_pretrained(path,local_files_only=True).eval().to('cpu')
        result=(tokenizer,model)
    elif kind=='coref':
        import stanza
        result=stanza.Pipeline('en',dir=str(CACHE/'stanza'),processors='tokenize,mwt,pos,lemma,depparse,coref',download_method=None,use_gpu=False,verbose=False)
    else: raise ValueError(kind)
    _loaded=(kind,result); return result

def embeddings(texts,backend='sbert'):
    if backend=='fasttext':
        from .fasttext_vectors import encode
        return encode(texts)
    if not texts: return np.empty((0,768))
    model=load('sbert')
    if any(len(model.tokenizer(t,add_special_tokens=True,truncation=False)['input_ids'])>model.max_seq_length for t in texts):
        raise Unavailable('文本单元超过MPNet的固定384子词上限；请使用明确分段，避免静默截断','input_required')
    return model.encode(texts,normalize_embeddings=True,show_progress_bar=False,batch_size=16)

def score_stream(text):
    import torch
    tokenizer,model=load('causal'); maxlen=int(model.config.max_position_embeddings)
    enc=tokenizer(text,add_special_tokens=False,return_offsets_mapping=True)
    ids=enc['input_ids']; offsets=enc['offset_mapping']; bos=tokenizer.bos_token_id
    if bos is None: bos=tokenizer.eos_token_id
    if bos is None: raise Unavailable('模型缺少明确的初始上下文token','resource_invalid')
    all_ids=[bos]+ids; scores=[]; stride=min(256,maxlen//2)
    # Each target scored once; start index supplies as much left context as fits.
    with torch.inference_mode():
        for target_start in range(1,len(all_ids),stride):
            target_end=min(len(all_ids),target_start+stride)
            begin=max(0,target_end-maxlen)
            chunk=torch.tensor([all_ids[begin:target_end]],dtype=torch.long)
            logp=model(chunk).logits[0].log_softmax(-1)
            for j in range(target_start,target_end):
                scores.append(-float(logp[j-begin-1,all_ids[j]]))
    return ids,offsets,scores

def causal_scores(ctx):
    if hasattr(ctx,'_causal'): return ctx._causal
    ids,offsets,scores=score_stream(ctx.raw)
    rows=[dict(subword_index=i,subword_id=ids[i],start=a,end=b,surprisal_nats=scores[i]) for i,(a,b) in enumerate(offsets)]
    # Sum subword surprisals assigned by character overlap to fixed linguistic tokens.
    word_scores=[]; uncovered=0
    for t in ctx.words:
        matching=[r for r in rows if r['end']>t.idx and r['start']<t.idx+len(t.text)]
        value=sum(r['surprisal_nats'] for r in matching) if matching else None
        if value is None: uncovered+=1
        word_scores.append(dict(token_id=t.i,word=t.text,start=t.idx,end=t.idx+len(t.text),surprisal_nats=value))
    # A subword crossing two linguistic tokens would double count; expose and block word aggregates.
    overlaps=[sum(r['end']>t.idx and r['start']<t.idx+len(t.text) for t in ctx.words) for r in rows]
    ambiguity=any(k>1 for k in overlaps)
    ctx.details['lm_subwords']=rows;ctx.details['lm_words']=word_scores
    ctx._causal=dict(scores=scores,words=word_scores,ambiguous=ambiguity,uncovered=uncovered)
    return ctx._causal

def measure(fid,ctx):
    if fid in {'DIS08','DIS09','DIS10'}:
        if fid=='DIS10': texts=[p[2] for p in ctx.paragraphs]; gap=1
        else: texts=[s.text for s in ctx.sentences]; gap=1 if fid=='DIS08' else 2
        backend=ctx.options.get('semantic_backend','sbert')
        if backend=='fasttext':texts=[' '.join(t.text for t in ctx.words if (s.start_char<=t.idx<s.end_char)) for s in ctx.sentences] if fid!='DIS10' else [' '.join(t.text for t in ctx.words if a<=t.idx<b) for a,b,_ in ctx.paragraphs]
        vec=embeddings(texts,backend); rows=[dict(left=i,right=i+gap,cosine=float(np.dot(vec[i],vec[i+gap])),backend=backend) for i in range(len(vec)-gap)]
        ctx.details[fid.lower()+'_similarity']=rows
        return summary([r['cosine'] for r in rows],fid+('.fasttext_mean_cosine' if backend=='fasttext' else '.mpnet_cosine'))
    if fid=='INF09':
        uni=resources.table('unigram');values=[];rows=[]
        for sn,s in enumerate(ctx.sentences):
            words=[t.text.casefold() for t in s if not t.is_space and not t.is_punct]
            probabilities=[uni.get(w,{}).get('probability') for w in words]
            if not words or any(p is None or p<=0 or p>1 for p in probabilities):value=None
            else:
                text=' '.join(words);_,_,scores=score_stream(text)
                value=(-sum(scores)-sum(math.log(p) for p in probabilities))/len(words)
            values.append(value);rows.append(dict(sentence_id=sn,slor=value,scored_word_sequence=' '.join(words),normalization='lowercase wordforms, punctuation removed'))
        ctx.details['slor_sentences']=rows
        return summary(values,'INF09.slor_lowercase_word_sequence')
    if fid in {'INF04','INF05','INF06','INF08'}:
        result=causal_scores(ctx); scores=result['scores']; out={}
        if fid=='INF04': return {**summary(scores,'INF04.subword_surprisal_nats'),'INF04.word_alignment_ambiguous':int(result['ambiguous']),'INF04.uncovered_words':result['uncovered']}
        if fid=='INF05': return {'INF05.mean_subword_nll_nats':float(np.mean(scores)) if scores else None}
        if fid=='INF06': return {'INF06.subword_perplexity':math.exp(float(np.mean(scores))) if scores and np.mean(scores)<700 else None}
        if result['ambiguous'] or result['uncovered']: raise Unavailable('词与子词边界无法无歧义对齐','alignment_failed')
        if fid=='INF08':
            rows=[]
            for sn,s in enumerate(ctx.sentences):
                values=[r['surprisal_nats'] for r in result['words'] if s.start_char<=r['start']<s.end_char]
                rows.append(dict(sentence_id=sn,**uid(values,ctx.options.get('uid_power',1.25),ctx.options.get('uid_reference_mean'))))
            ctx.details['uid_sentences']=rows
            for key in {k for r in rows for k in r if k!='sentence_id'}: out.update(summary([r.get(key) for r in rows],key+'.sentence'))
            return out
    if fid=='INF10':
        import torch
        tokenizer,model=load('mlm'); total=0.; count=0; rows=[]
        for sn,sentence in enumerate(ctx.sentences):
            ids=tokenizer(sentence.text,add_special_tokens=True)['input_ids']
            if len(ids)>model.config.max_position_embeddings: raise Unavailable('句子超过BERT上下文上限，需明确切窗口径','input_required')
            positions=[i for i,x in enumerate(ids) if x not in tokenizer.all_special_ids]
            with torch.inference_mode():
                for start in range(0,len(positions),16):
                    ps=positions[start:start+16]; batch=torch.tensor([ids]*len(ps))
                    for j,pos in enumerate(ps): batch[j,pos]=tokenizer.mask_token_id
                    logits=model(batch).logits.log_softmax(-1)
                    for j,pos in enumerate(ps):
                        lp=float(logits[j,pos,ids[pos]]); total+=lp;count+=1
                        rows.append(dict(sentence_id=sn,subword_position=pos,log_probability=lp,method='pll_single_token'))
        ctx.details['mlm_scores']=rows
        return {'INF10.pll_single_token':total if count else None,'INF10.pppl_subword':math.exp(-total/count) if count and -total/count<700 else None,'INF10.scored_subwords':count}
    if fid in {'DIS06','DIS07'}:
        if not hasattr(ctx,'_coref'):
            doc=load('coref')(ctx.raw); chains=getattr(doc,'coref',[]) or []; grid=[]; details=[]
            for index,chain in enumerate(chains):
                roles=['-']*len(doc.sentences)
                for mention in chain.mentions:
                    sn=mention.sentence
                    words=doc.sentences[sn].words[mention.start_word:mention.end_word]
                    inside={w.id for w in words}
                    heads=[w for w in words if w.head not in inside]
                    head=heads[0] if heads else (words[0] if words else None)
                    role='S' if head and head.deprel.startswith(('nsubj','csubj')) else 'O' if head and head.deprel in {'obj','iobj'} else 'X'
                    if 'SOX-'.index(role)<'SOX-'.index(roles[sn]):roles[sn]=role
                    details.append(dict(entity_id=index,sentence_id=sn,start_word=mention.start_word,end_word=mention.end_word,role=role))
                grid.append(roles)
            ctx._coref=(grid,details);ctx.details['coref_mentions']=details
            ctx.details['coref_grid']=[dict(entity_id=i,sentence_id=j,role=r) for i,entity in enumerate(grid) for j,r in enumerate(entity)]
        grid,details=ctx._coref
        if fid=='DIS06':
            out={f'DIS06.width{width}.{k}':v for width in [2,3] for k,v in grid_transitions(grid,width).items()}
            mentions=Counter(r['entity_id'] for r in details);threshold=ctx.options.get('entity_salience_mentions',2)
            for label,salient in [('salient',True),('nonsalient',False)]:
                subset=[entity for i,entity in enumerate(grid) if (mentions[i]>=threshold)==salient]
                out.update({f'DIS06.{label}.width{width}.{k}':v for width in [2,3] for k,v in grid_transitions(subset,width).items()})
            out['DIS06.salience_mentions_threshold']=threshold
            return out
        spans=[];gaps=[]
        for entity in grid:
            positions=[i for i,r in enumerate(entity) if r!='-']
            if positions:spans.append(positions[-1]-positions[0])
            gaps.extend(np.diff(positions).tolist())
        return {**summary([sum(r!='-' for r in entity) for entity in grid],'DIS07.coref_sentences_per_entity'),**summary(spans,'DIS07.sentence_span'),**summary(gaps,'DIS07.sentence_recurrence_gap')}
    if fid=='DIS12':
        conf=resources.configuration('sid'); embeddings_conf=conf['embedding_id']
        backend=ctx.options.get('semantic_backend','sbert')
        meta=json.loads(resources.marker(backend).read_text()) if resources.marker(backend).exists() else {}
        identity=meta.get('model_id') if backend=='sbert' else 'fasttext.bin.'+resources.configuration('fasttext')['sha256']
        if embeddings_conf!=identity or (backend=='sbert' and conf.get('embedding_revision')!=meta.get('revision')): raise Unavailable('SID簇与当前embedding模型或修订不匹配','resource_invalid')
        words=[t for t in ctx.words if t.pos_ in {'NOUN','VERB'}]; vec=embeddings([t.text for t in words],backend); centers=np.array(conf['centroids']); means=np.array(conf['distance_means']);sds=np.array(conf['distance_sds'])
        if np.any(sds<=0): raise Unavailable('SID簇标准差必须大于0','resource_invalid')
        distances=np.linalg.norm(vec[:,None,:]-centers[None,:,:],axis=2); idx=distances.argmin(axis=1); z=(distances[np.arange(len(vec)),idx]-means[idx])/sds[idx]
        return {'DIS12.sid_train_clusters':ratio(int((z<3).sum()),ctx.n),'DIS12.eligible_tokens':len(words)}
    raise Unavailable('模型方法待配置')
