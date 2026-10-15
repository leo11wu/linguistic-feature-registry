from __future__ import annotations
import math, json, itertools, subprocess
from collections import Counter, defaultdict
import numpy as np
from .util import ratio, summary, entropy, Unavailable
from .stats import association, dispersion, recurrence, finite_burstiness, graph_measures
from . import resources

IDS={'FREQ10','MWE01','MWE02','MWE03','MWE04','MWE05','MWE06','MWE07','MWE08','INF07','STY02','STY07',*[f'QL{i:02d}' for i in range(1,12)],*[f'NET{i:02d}' for i in range(1,6)]}

class Corpus:
    def __init__(self,records,options=None,selected_features=None,reference=None):
        self.selected_features=selected_features
        self.network_features=None if selected_features is None else set(selected_features)&{'NET01','NET02','NET03','NET04','NET05'}
        self.options=options or {}; self.records=records;self.counter=Counter();self.left=Counter();self.right=Counter();self.pairs=Counter();self.documents=Counter();self.ngrams={i:Counter() for i in [2,3,4]};self.ranges={i:Counter() for i in [2,3,4]};self.partitions=defaultdict(Counter)
        self.sizes=Counter();self.sequences=[];self.total_pairs=0
        for rec in records:
            keys=rec['keys'];self.counter.update(keys);self.documents.update(set(keys));self.sequences.extend(keys)
            field=self.options.get('partition_column','')
            part=str(rec['meta'][field]) if field else rec['id'];self.partitions[part].update(keys);self.sizes[part]+=len(keys)
            for order in [2,3,4]:
                grams=[tuple(s[i:i+order]) for s in rec['sentences'] for i in range(len(s)-order+1)]
                self.ngrams[order].update(grams);self.ranges[order].update(set(grams))
            for s in rec['sentences']:
                for x,y in zip(s,s[1:]): self.pairs[(x,y)]+=1;self.left[x]+=1;self.right[y]+=1;self.total_pairs+=1
        self.pair_stats={}
        for (x,y),a in self.pairs.items():
            b=self.left[x]-a;c=self.right[y]-a;d=self.total_pairs-a-b-c
            self.pair_stats[(x,y)]=dict(left=x,right=y,joint=a,left_total=self.left[x],right_total=self.right[y],event_total=self.total_pairs,**association(a,b,c,d))
        from .observations import FrozenReference
        self.reference=FrozenReference(reference) if reference is not None else self
        self.details={};self._law=None;self._graph=None;self._dispersion={};self._gram_record=None;self._grams={}

    def document_grams(self,rec,orders):
        if self._gram_record!=rec['id']:self._gram_record=rec['id'];self._grams={}
        for order in orders:
            if order not in self._grams:self._grams[order]=[tuple(s[i:i+order]) for s in rec['sentences'] for i in range(len(s)-order+1)]
        return {order:self._grams[order] for order in orders}

    def laws(self):
        if self._law is not None:return self._law
        counts=sorted(self.counter.items(),key=lambda r:(-r[1],r[0]));rank_rows=[dict(rank=i+1,word=w,frequency=f,letters=sum(c.isalpha() for c in w)) for i,(w,f) in enumerate(counts)]
        self.details['rank_frequency']=rank_rows;self.details['frequency_spectrum']=[dict(frequency=f,types=v) for f,v in sorted(Counter(self.counter.values()).items())]
        seen=set();growth=[];wanted=set(np.unique(np.geomspace(1,max(1,len(self.sequences)),min(200,max(1,len(self.sequences)))).astype(int)))
        for i,w in enumerate(self.sequences,1):
            seen.add(w)
            if i in wanted: growth.append(dict(tokens=i,types=len(seen)))
        self.details['vocabulary_growth']=growth
        rec_rows=[]
        if self.selected_features is None or set(self.selected_features)&{'QL09','QL10','QL11'}:
            positions=defaultdict(list)
            for i,w in enumerate(self.sequences):positions[w].append(i)
            for w,ps in positions.items():
                r=recurrence(ps); rec_rows.append(dict(word=w,frequency=len(ps),positions=ps,**r,finite_burstiness_periodic=finite_burstiness(ps,len(self.sequences))))
        self.details['recurrence']=rec_rows
        self._law={};return self._law

    def measure(self,fid,rec):
        keys=rec['keys'];n=len(keys);sentences=rec['sentences'];out={};rows=[]
        ref=self.reference
        if fid=='FREQ10':
            parts=sorted(ref.partitions);sizes=[ref.sizes[p] for p in parts]
            for w in set(keys):
                if w not in self._dispersion:self._dispersion[w]=dispersion([ref.partitions[p][w] for p in parts],sizes)
                dp,dn=self._dispersion[w]
                rows.append(dict(word=w,dp=dp,dpnorm_corrected=dn,reference_frequency=ref.counter[w]))
            byword={r['word']:r for r in rows};self.details['dispersion']=rows
            return {**summary([byword[w]['dp'] for w in keys],'FREQ10.dp.token'),**summary([byword[w]['dpnorm_corrected'] for w in keys],'FREQ10.dpnorm.token')}
        if fid.startswith('MWE'):
            grams=self.document_grams(rec,[2,3,4] if fid in {'MWE01','MWE04'} else [2] if fid in {'MWE02','MWE03','MWE07','MWE08'} else [])
            if fid=='MWE01':
                for order,gs in grams.items():out.update(summary([ref.ngrams[order][g] for g in gs],f'MWE01.order{order}_reference_count'))
            elif fid=='MWE04':out={f'MWE04.order{k}_ttr':ratio(len(set(gs)),len(gs)) for k,gs in grams.items()}
            elif fid=='MWE05':
                order=self.options.get('bundle_order',4);minfreq=self.options.get('bundle_min_frequency',10);mindocs=self.options.get('bundle_min_documents',3)
                covered=set();position=0
                for s in sentences:
                    for i in range(len(s)-order+1):
                        g=tuple(s[i:i+order])
                        if ref.ngrams[order][g]>=minfreq and ref.ranges[order][g]>=mindocs:covered.update(range(position+i,position+i+order))
                    position+=len(s)
                out={'MWE05.bundle_covered_token_rate':ratio(len(covered),n)}
            elif fid=='MWE06':
                profile=defaultdict(list)
                for seq in rec.get('pos_sentences',[]):
                    for (a,pa),(b,pb) in zip(seq,seq[1:]):
                        if (pa,pb) in {('ADJ','NOUN'),('VERB','NOUN')} and (a,b) in ref.pair_stats:profile[pa+'_'+pb].append(ref.pair_stats[(a,b)]['pmi'])
                for p,values in profile.items():out.update(summary(values,'MWE06.adjacent_'+p+'_pmi'))
            else:
                fields={'MWE02':['pmi'],'MWE03':['t_score'],'MWE07':['delta_p_y_given_x','delta_p_x_given_y'],'MWE08':['logdice']}[fid]
                for field in fields:out.update(summary([ref.pair_stats[g][field] for g in grams[2] if g in ref.pair_stats],fid+'.adjacent_'+field))
            self.details['collocations']=list(ref.pair_stats.values());return out
        if fid=='INF07':
            if ref is self and len(self.records)<2:raise Unavailable('JS散度需要其他参照文本')
            mine=Counter(keys);reference=self.counter-mine if ref is self else ref.counter
            if not n or not reference.total():raise Unavailable('空比较分布','undefined')
            support=set(mine)|set(reference);p=np.array([mine[w]/n for w in support]);q=np.array([reference[w]/reference.total() for w in support]);m=(p+q)/2
            def kl(a,b):keep=a>0;return float(np.sum(a[keep]*np.log2(a[keep]/b[keep])))
            name='vs_other_documents' if ref is self else 'vs_external_reference'
            return {'INF07.js_bits_'+name:(kl(p,m)+kl(q,m))/2}
        if fid=='STY02':
            order=self.options.get('character_ngram_order',3);raw=rec['text'];counts=Counter(raw[i:i+order] for i in range(len(raw)-order+1));total=counts.total()
            rec.setdefault('details',{})['character_ngrams']=[dict(ngram=g,count=c,proportion=ratio(c,total)) for g,c in counts.items()]
            return {'STY02.character_ngram_types':len(counts),'STY02.character_ngram_entropy_bits':entropy(counts.values())}
        if fid=='STY07':
            field=self.options.get('pair_column','');pair=rec['meta'].get(field) if field else None
            peers=[r for r in self.records if r['id']!=rec['id'] and r['meta'].get(field)==pair] if pair else []
            if len(peers)!=1:raise Unavailable('LSM需明确配对列，同一非空配对值恰好对应两篇文本')
            lex=resources.table('function_words');cats=defaultdict(set)
            for w,r in lex.items():cats[r.get('category','all')].add(w)
            other=Counter(peers[0]['keys']);mine=Counter(keys);other_n=sum(other.values());scores=[]
            for cat,words in cats.items():
                p=ratio(sum(mine[w] for w in words),n);q=ratio(sum(other[w] for w in words),other_n)
                value=1-abs(p-q)/(p+q+.0001) if p is not None and q is not None else None
                out['STY07.'+cat]=value
                if value is not None:scores.append(value)
            out['STY07.lsm_mean']=float(np.mean(scores)) if scores else None;return out
        if fid.startswith('NET'):
            if self._graph is None:
                if len(self.counter)>self.options.get('network_max_nodes',2000):raise Unavailable('共现图超过2000节点；请指定更小子语料或显式提高network_max_nodes')
                edges=Counter();window=1 if self.options.get('network_edge','adjacent')=='adjacent' else self.options.get('network_window',2)
                directed=self.options.get('network_directed',True)
                for record in self.records:
                    for sentence in record['sentences']:
                        for i,a in enumerate(sentence):
                            for b in sentence[i+1:i+window+1]:
                                if a!=b:edges[(a,b) if directed else tuple(sorted((a,b)))]+=1
                edges=Counter({p:c for p,c in edges.items() if c>=self.options.get('network_min_count',1)})
                graph,values=graph_measures(edges,set(self.counter),self.network_features,directed=directed)
                if not directed:
                    values={k.replace('directed_all_pairs','undirected_all_pairs'):v for k,v in values.items()}
                self._graph=(graph,values);self.details['network_nodes']=graph
                self.details['network_edges']=[dict(source=a,target=b,count=c,directed=directed) for (a,b),c in sorted(edges.items())]
            graph,values=self._graph
            fields={'NET01':['in_degree','out_degree','in_strength','out_strength'],'NET02':['clustering'],'NET05':['betweenness']}
            if fid in fields:
                return {k:v for field in fields[fid] for k,v in summary([r[field] for r in graph],fid+'.'+field).items()}
            return {k:v for k,v in values.items() if k.startswith(fid+'.')}
        if fid.startswith('QL'):
            if fid in {f'QL{i:02d}' for i in range(1,9)}:raise Unavailable('该分析已移至拟合页；请复用提取后的观测表','fit_only')
            self.laws()
            field={'QL09':'burstiness','QL10':'memory','QL11':'finite_burstiness_periodic'}[fid]
            return summary([r[field] for r in self.details['recurrence']],fid+'.'+field+'.type')
        raise Unavailable('缺少语料方法配置')
