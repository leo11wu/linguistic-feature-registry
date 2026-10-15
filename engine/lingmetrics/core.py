from __future__ import annotations
import math, re, itertools
from collections import Counter, defaultdict, deque
from functools import lru_cache
import numpy as np
from .stats import diversity, vocd, graph_measures, permuted_lengths
from .util import ratio, summary, entropy, Unavailable

@lru_cache(maxsize=1)
def pronunciation_lexicon():
    import cmudict
    return cmudict.dict()

class Text:
    def __init__(self, text, nlp, options=None):
        self.raw=text; self.options=options or {}; self.doc=nlp(text)
        self.tokens=[t for t in self.doc if not t.is_space]
        self.words=[t for t in self.tokens if not t.is_punct]
        self.keys=[self.key(t) for t in self.words]; self.counts=Counter(self.keys)
        self.sentences=[s for s in self.doc.sents if any(not t.is_space for t in s)]
        self.paragraphs=[(m.start(),m.end(),m.group()) for m in re.finditer(r"\S.*?(?=\n[ \t]*\n|\Z)",text,re.S)]
        self.sentence_keys=[[self.key(t) for t in s if not t.is_punct and not t.is_space] for s in self.sentences]
        self.n=len(self.words); self.s=len(self.sentences)
        self._diversity=None; self._dependency=None; self.details={}
        self.syllables=None; self.pronunciations=None

    def key(self,t):
        return (t.lemma_ if self.options.get("token_unit","wordform")=="lemma" else t.text).casefold()

    def diversity(self):
        if self._diversity is None:
            self._diversity=diversity(self.keys,self.options.get("window",50),self.options.get("mtld_threshold",.72),self.options.get("hdd_sample",42))
        return self._diversity

    def pronunciation(self):
        if self.syllables is None:
            lex=pronunciation_lexicon()
            self.pronunciations=[lex.get(t.text.casefold(),[None])[0] for t in self.words]
            self.syllables=[sum(p[-1:].isdigit() for p in phones) if phones else None for phones in self.pronunciations]
        return self.pronunciations

    def dependencies(self):
        if self._dependency is not None: return self._dependency
        rows=[]; sent_rows=[]; all_depth=[]; pair_dist=[]; maximum_out=[]; maximum_und=[]; crossing=0; comparable=0; nonprojective=0
        for sn,s in enumerate(self.sentences):
            ts=[t for t in s if not t.is_space]; pos={t.i:j for j,t in enumerate(ts)}
            edges=[(pos[t.head.i],pos[t.i]) for t in ts if t.head.i!=t.i and t.head.i in pos]
            lengths=[abs(a-b) for a,b in edges]; root=next((pos[t.i] for t in ts if t.head.i==t.i),0)
            adj={i:set() for i in range(len(ts))}; out=Counter(a for a,b in edges)
            for a,b in edges: adj[a].add(b); adj[b].add(a)
            depth={root:0}; q=deque([root])
            while q:
                a=q.popleft()
                for b in adj[a]:
                    if b not in depth: depth[b]=depth[a]+1; q.append(b)
            all_depth.extend(depth.values()); maximum_out.append(max(out.values(),default=0)); maximum_und.append(max(map(len,adj.values()),default=0))
            local_cross=0; local_comp=0
            for (a,b),(c,d) in itertools.combinations(edges,2):
                if len({a,b,c,d})<4: continue
                local_comp+=1; a,b=sorted((a,b)); c,d=sorted((c,d))
                local_cross+=int(a<c<b<d or c<a<d<b)
            # Rooted projectivity also checks that the interval is dominated by the edge head.
            projective=True
            for a,b in edges:
                for k in range(min(a,b)+1,max(a,b)):
                    cur=ts[k]; visited=set()
                    while cur.i!=ts[a].i and cur.head.i!=cur.i and cur.i not in visited:
                        visited.add(cur.i); cur=cur.head
                    if cur.i!=ts[a].i: projective=False; break
                if not projective: break
            nonprojective+=not projective; crossing+=local_cross; comparable+=local_comp
            for start in range(len(ts)):
                ds={start:0}; q=deque([start])
                while q:
                    u=q.popleft()
                    for v in adj[u]:
                        if v not in ds: ds[v]=ds[u]+1; q.append(v)
                pair_dist.extend(d for end,d in ds.items() if end>start)
            for t in ts:
                if t.head.i==t.i or t.head.i not in pos: continue
                a,b=pos[t.head.i],pos[t.i]
                rows.append(dict(sentence_id=sn,head_position=a,dependent_position=b,distance=abs(a-b),relation=t.dep_,head_left=int(a<b),head_token=t.head.i,dependent_token=t.i))
            sent_rows.append(dict(sentence_id=sn,n=len(ts),root_position=root+1,total_length=sum(lengths),edges=len(edges),mdd=ratio(sum(lengths),len(edges)),height=max(depth.values(),default=0),crossings=local_cross,projective=projective,edge_list=edges))
        ds=[r['distance'] for r in rows]; direction=Counter(r['head_left'] for r in rows); relations=Counter(r['relation'] for r in rows)
        values={"DEP01.total_length":sum(ds),"DEP02.mdd_position":ratio(sum(ds),len(ds)),"DEP02.mdd_intervening":ratio(sum(ds)-len(ds),len(ds)),
                "DEP04.adjacent_proportion":ratio(sum(d==1 for d in ds),len(ds)),"DEP05.head_left":ratio(direction[1],len(ds)),"DEP05.head_right":ratio(direction[0],len(ds)),
                "DEP08.mean_root_depth":float(np.mean(all_depth)) if all_depth else None,"DEP09.mean_hierarchical_distance":float(np.mean(pair_dist)) if pair_dist else None,
                "DEP10.max_out_degree":max(maximum_out,default=None),"DEP10.max_undirected_degree":max(maximum_und,default=None),
                "DEP11.crossings":crossing,"DEP12.crossing_rate":ratio(crossing,comparable),"DEP13.nonprojective_sentence_proportion":ratio(nonprojective,self.s)}
        values.update(summary(ds,"DEP03.distance")); values.update(summary([x['height'] for x in sent_rows],"DEP07.tree_height"))
        values.update({"DEP06."+k:ratio(v,len(ds)) for k,v in relations.items()})
        self.details['dependencies']=rows; self.details['dependency_sentences']=sent_rows
        self._dependency=values
        return values

def overlap(a,b):
    a,b=set(a),set(b)
    return ratio(len(a&b),len(a|b))

def base_measure(fid,ctx):
    n,s=ctx.n,ctx.s
    if fid.startswith('LD') and fid!='LD14':
        if fid=='LD10': return {"LD10.vocd_sample_fit":vocd(ctx.keys,ctx.options.get('seed',1729))}
        return {k:v for k,v in ctx.diversity().items() if k.startswith(fid+'.')}
    if fid=='LD14':
        out={}
        for pos in ['NOUN','VERB','ADJ','ADV']:
            words=[ctx.key(t) for t in ctx.words if t.pos_==pos]
            if words:
                out.update({f'LD14.{pos}.{k.split(".",1)[1]}':v for k,v in diversity(words,ctx.options.get('window',50),ctx.options.get('mtld_threshold',.72),ctx.options.get('hdd_sample',42)).items()})
        if not out: raise Unavailable('无合格词性词次','undefined')
        return out
    if fid=='LEN01': return {'LEN01.tokens':n}
    if fid=='LEN02': return {'LEN02.types':len(ctx.counts)}
    if fid=='LEN03': return {'LEN03.sentences':s}
    if fid=='LEN04': return {'LEN04.paragraphs':len(ctx.paragraphs)}
    if fid=='LEN05': return {'LEN05.characters':len(ctx.raw),'LEN05.nonspace':sum(not c.isspace() for c in ctx.raw),'LEN05.letters':sum(c.isalpha() for c in ctx.raw)}
    if fid=='LEN06': return summary([sum(c.isalpha() for c in t.text) for t in ctx.words],'LEN06.letters')
    if fid=='LEN07':
        ctx.pronunciation(); out=summary(ctx.syllables,'LEN07.syllables'); out['LEN07.coverage']=ratio(out['LEN07.syllables.valid_n'],n); return out
    if fid=='LEN08': return {'LEN08.mean_sentence_words':ratio(n,s)}
    if fid=='LEN09':
        return {**summary([sum(a<=t.idx<b for t in ctx.words) for a,b,_ in ctx.paragraphs],'LEN09.paragraph_words'),
                **summary([sum(a<=sent.start_char<b for sent in ctx.sentences) for a,b,_ in ctx.paragraphs],'LEN09.paragraph_sentences')}
    if fid.startswith('DEP') and fid not in {'DEP14','DEP15','DEP16'}:
        return {k:v for k,v in ctx.dependencies().items() if k.startswith(fid+'.')}
    if fid=='DEP14':
        ctx.dependencies(); rng=np.random.default_rng(ctx.options.get('seed',1729)); values=[]; rows=[]
        repetitions=ctx.options.get('random_permutations',1000)
        for row in ctx.details['dependency_sentences']:
            k=row['n']; edges=row['edge_list']
            if k<3: continue
            sims=permuted_lengths(k,edges,repetitions,rng)
            sd=float(np.std(sims)); z=ratio(row['total_length']-float(np.mean(sims)),sd)
            rows.append(dict(sentence_id=row['sentence_id'],z_mc=z,baseline_mean=float(np.mean(sims)),baseline_sd=sd,mean_mc_se=sd/math.sqrt(repetitions),repetitions=repetitions))
            values.append(z)
        ctx.details['dependency_random_baseline']=rows
        return summary(values,'DEP14.z_monte_carlo')
    if fid=='MOR07':
        groups=defaultdict(set)
        for t in ctx.words:
            if t.pos_ in {'NOUN','VERB','ADJ','ADV'}: groups[t.lemma_.casefold()].add(t.text.casefold())
        return summary([len(x) for x in groups.values()],'MOR07.observed_inflectional_forms')
    if fid.startswith('POS'):
        c=Counter(t.pos_ for t in ctx.words)
        if fid=='POS01': return {'POS01.'+p:ratio(c[p],n) for p in ['ADJ','ADP','ADV','AUX','CCONJ','DET','INTJ','NOUN','NUM','PART','PRON','PROPN','SCONJ','SYM','VERB','X']}
        if fid=='POS02': return {'POS02.lexical_density':ratio(sum(c[p] for p in ['NOUN','VERB','ADJ','ADV']),n)}
        if fid=='POS03': return {'POS03.noun_verb_ratio':ratio(c['NOUN']+c['PROPN'],c['VERB'])}
        if fid=='POS04':
            out={}
            for person in ['1','2','3']:
                for number in ['Sing','Plur']:
                    out[f'POS04.person{person}_{number}']=ratio(sum(t.pos_=='PRON' and person in t.morph.get('Person') and number in t.morph.get('Number') for t in ctx.words),n)
            return out
        if fid in {'POS05','POS08'}:
            key='Tense' if fid=='POS05' else 'VerbForm'; verbs=[t for t in ctx.words if t.pos_ in {'VERB','AUX'}]; labels=['Past','Pres'] if key=='Tense' else ['Fin','Inf','Part','Ger']
            return {fid+'.'+v:ratio(sum(v in t.morph.get(key) for t in verbs),len(verbs)) for v in labels}
        if fid=='POS06':
            predicates=[t for t in ctx.words if t.pos_=='VERB']
            return {'POS06.perfect_aux_have':ratio(sum(any(c.dep_=='aux' and c.lemma_=='have' for c in t.children) for t in predicates),len(predicates)),
                    'POS06.progressive_aux_be':ratio(sum(t.tag_=='VBG' and any(c.dep_ in {'aux','auxpass'} and c.lemma_=='be' for c in t.children) for t in predicates),len(predicates))}
        if fid=='POS07':
            return {'POS07.modal_aux_per_word':ratio(sum(t.tag_=='MD' for t in ctx.words),n),**{f'POS07.mood_{v}':ratio(sum(v in t.morph.get('Mood') for t in ctx.words),n) for v in ['Ind','Imp','Sub']}}
        if fid=='POS09':
            predicates=[t for t in ctx.words if t.pos_=='VERB']
            return {'POS09.passive_predicate_rate':ratio(sum(any(c.dep_ in {'auxpass','nsubjpass','csubjpass'} for c in t.children) for t in predicates),len(predicates))}
        if fid=='POS10': return {'POS10.negation_dependency_per_word':ratio(sum(t.dep_=='neg' for t in ctx.words),n)}
    if fid in {'SYN18','SYN19','SYN20'}:
        nouns=[t for t in ctx.words if t.pos_ in {'NOUN','PROPN'}]
        if fid=='SYN18': return {'SYN18.nominal_premodifiers_per_head':ratio(sum(c.dep_=='compound' and c.i<t.i and c.pos_ in {'NOUN','PROPN'} for t in nouns for c in t.children),len(nouns))}
        if fid=='SYN19': return {'SYN19.prepositional_postmodifiers_per_head':ratio(sum(c.dep_=='prep' and c.i>t.i for t in nouns for c in t.children),len(nouns))}
        return {'SYN20.relative_modified_head_proportion':ratio(sum(any(c.dep_=='relcl' for c in t.children) for t in nouns),len(nouns))}
    if fid in {'DIS01','DIS02','DIS03'}:
        seq=ctx.sentence_keys
        if fid=='DIS02': seq=[[ctx.key(t) for t in ctx.words if a<=t.idx<b] for a,b,_ in ctx.paragraphs]
        pairs=itertools.combinations(range(len(seq)),2) if fid=='DIS03' else ((i,i+1) for i in range(len(seq)-1))
        data=[dict(left=i,right=j,jaccard=overlap(seq[i],seq[j])) for i,j in pairs]
        ctx.details[fid.lower()+'_overlap']=data
        return summary([r['jaccard'] for r in data],fid+'.jaccard')
    if fid=='DIS05': return {'DIS05.named_entity_mentions_per_word':ratio(len(ctx.doc.ents),n)}
    if fid=='INF01': return {'INF01.unigram_entropy_bits':entropy(ctx.counts.values())}
    if fid=='INF02': return {'INF02.pos_entropy_bits':entropy(Counter(t.pos_ for t in ctx.words).values())}
    if fid=='INF03':
        out={}
        for order in [2,3,4]:
            grams=Counter(tuple(seq[i:i+order]) for seq in ctx.sentence_keys for i in range(len(seq)-order+1))
            contexts=Counter()
            for g,v in grams.items(): contexts[g[:-1]]+=v
            total=sum(grams.values())
            out[f'INF03.order{order}_conditional_bits']=sum(-(v/total)*math.log2(v/contexts[g[:-1]]) for g,v in grams.items()) if total else None
        return out
    if fid.startswith('READ'):
        if not n or not s: raise Unavailable('需要非空词和句','undefined')
        letters=sum(sum(c.isalpha() for c in t.text) for t in ctx.words); long=sum(sum(c.isalpha() for c in t.text)>6 for t in ctx.words)
        if fid=='READ05': return {'READ05.ari':4.71*letters/n+.5*n/s-21.43}
        if fid=='READ06': return {'READ06.coleman_liau':.0588*100*letters/n-.296*100*s/n-15.8}
        if fid=='READ08': return {'READ08.lix':n/s+100*long/n}
        if fid=='READ09': return {'READ09.rix':long/s}
        ctx.pronunciation()
        if any(x is None for x in ctx.syllables): raise Unavailable('CMUdict未覆盖全部词，严格模式不估补音节','coverage_insufficient')
        syll=sum(ctx.syllables); polysyll=sum(x>=3 for x in ctx.syllables)
        if fid=='READ01': return {'READ01.flesch_reading_ease':206.835-1.015*n/s-84.6*syll/n}
        if fid=='READ02': return {'READ02.flesch_kincaid_grade':.39*n/s+11.8*syll/n-15.59}
        if fid=='READ03': return {'READ03.fog_dictionary_polysyllables':.4*(n/s+100*sum(x>=3 and t.pos_!='PROPN' for t,x in zip(ctx.words,ctx.syllables))/n)}
        if fid=='READ04':
            if s<30: raise Unavailable('SMOG标准使用需要至少30句','undefined')
            return {'READ04.smog':1.043*math.sqrt(polysyll*30/s)+3.1291}
    if fid=='STY03':
        p=Counter(t.text for t in ctx.tokens if t.is_punct)
        return {'STY03.'+k:ratio(v,n) for k,v in p.items()}
    if fid=='QC04':
        lines=[x.strip() for x in ctx.raw.splitlines() if x.strip()]; grams=[tuple(seq[i:i+3]) for seq in ctx.sentence_keys for i in range(len(seq)-2)]
        return {'QC04.duplicate_line_ratio':ratio(len(lines)-len(set(lines)),len(lines)),
                'QC04.repeated_trigram_excess_ratio':ratio(len(grams)-len(set(grams)),len(grams))}
    if fid=='QC05':
        length=len(ctx.raw)
        return {'QC05.'+name:ratio(sum(fn(c) for c in ctx.raw),length) for name,fn in [('letters',str.isalpha),('digits',str.isdigit),('whitespace',str.isspace),('replacement_character',lambda c:c=='\ufffd'),('control',lambda c:ord(c)<32 and c not in '\t\n\r')]}
    if fid in {'PHO01','PHO02'}:
        phones=ctx.pronunciation()
        if fid=='PHO01': return {**summary([len(p) if p else None for p in phones],'PHO01.phonemes'),'PHO01.coverage':ratio(sum(p is not None for p in phones),n)}
        patterns=Counter(''.join(p[-1] for p in ps if p[-1].isdigit()) for ps in phones if ps)
        return {'PHO02.stress_'+k:ratio(v,sum(patterns.values())) for k,v in patterns.items()}
    raise Unavailable('该指标需要额外方法或资源')
