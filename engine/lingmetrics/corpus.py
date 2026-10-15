from __future__ import annotations
import math, json, itertools, subprocess
from collections import Counter, defaultdict
import numpy as np
from .util import ratio, summary, entropy, Unavailable
from .stats import association, dispersion, recurrence, finite_burstiness, graph_measures
from . import resources

IDS={'FREQ10','MWE01','MWE02','MWE03','MWE04','MWE05','MWE06','MWE07','MWE08','INF07','STY02','STY07',*[f'QL{i:02d}' for i in range(1,12)],*[f'NET{i:02d}' for i in range(1,6)]}

class Corpus:
    def __init__(self,records,options=None,selected_features=None):
        self.network_features=None if selected_features is None else set(selected_features)&{'NET01','NET02','NET03','NET04','NET05'}
        self.options=options or {}; self.records=records;self.counter=Counter();self.left=Counter();self.right=Counter();self.pairs=Counter();self.documents=Counter();self.ngrams={i:Counter() for i in [2,3,4]};self.ranges={i:Counter() for i in [2,3,4]};self.partitions=defaultdict(Counter)
        self.sizes=Counter();self.sequences=[];self.total_pairs=0
        for rec in records:
            keys=rec['keys'];self.counter.update(keys);self.documents.update(set(keys));self.sequences.extend(keys)
            part=rec['meta'].get('section_id') or rec['id'];self.partitions[part].update(keys);self.sizes[part]+=len(keys)
            for order in [2,3,4]:
                grams=[tuple(s[i:i+order]) for s in rec['sentences'] for i in range(len(s)-order+1)]
                self.ngrams[order].update(grams);self.ranges[order].update(set(grams))
            for s in rec['sentences']:
                for x,y in zip(s,s[1:]): self.pairs[(x,y)]+=1;self.left[x]+=1;self.right[y]+=1;self.total_pairs+=1
        self.pair_stats={}
        for (x,y),a in self.pairs.items():
            b=self.left[x]-a;c=self.right[y]-a;d=self.total_pairs-a-b-c
            self.pair_stats[(x,y)]=dict(left=x,right=y,joint=a,left_total=self.left[x],right_total=self.right[y],event_total=self.total_pairs,**association(a,b,c,d))
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
        positions=defaultdict(list)
        for i,w in enumerate(self.sequences):positions[w].append(i)
        rec_rows=[]
        for w,ps in positions.items():
            r=recurrence(ps); rec_rows.append(dict(word=w,frequency=len(ps),positions=ps,**r,finite_burstiness_periodic=finite_burstiness(ps,len(self.sequences))))
        self.details['recurrence']=rec_rows
        # Fits describe this rank/growth curve; this is not a power-law goodness-of-fit claim.
        fits=[];out={}
        try:
            from scipy.optimize import curve_fit
            def fit(name,fid,func,x,y,p0,bounds,params):
                if len(x)<=len(p0):return
                try:
                    values,cov=curve_fit(func,np.asarray(x,dtype=float),np.asarray(y,dtype=float),p0=p0,bounds=bounds,maxfev=20000)
                    predicted=func(np.asarray(x,dtype=float),*values);rmse=float(np.sqrt(np.mean((predicted-y)**2)))
                    for i,key in enumerate(params):out[fid+'.'+key]=float(values[i])
                    fits.append(dict(model=name,method='nonlinear_least_squares_descriptive',parameters=dict(zip(params,map(float,values))),covariance=cov.tolist(),rmse=rmse,n=len(x),success=True))
                except (ValueError,RuntimeError,FloatingPointError) as e:fits.append(dict(model=name,success=False,reason=str(e)))
            r=np.arange(1,len(counts)+1,dtype=float);f=np.array([v for w,v in counts],dtype=float)
            if len(r)>2:fit('Zipf','QL01',lambda r,c,a:c*r**(-a),r,f,[max(f),1.],([0,0],[np.inf,10]),['C','a'])
            if len(r)>3:fit('Zipf_Mandelbrot','QL02',lambda r,c,a,b:c*(r+b)**(-a),r,f,[max(f),1.,1.],([0,0,0],[np.inf,10,1e6]),['C','a','b'])
            x=np.array([g['tokens'] for g in growth]);y=np.array([g['types'] for g in growth])
            if len(x)>2:fit('Heaps','QL03',lambda x,k,b:k*x**b,x,y,[1.,.5],([0,0],[np.inf,1]),['K','beta'])
        except ImportError: pass
        self.details['curve_fits']=fits
        self._law=out;return out

    def measure(self,fid,rec):
        keys=rec['keys'];n=len(keys);sentences=rec['sentences'];out={};rows=[]
        if fid=='FREQ10':
            parts=sorted(self.partitions);sizes=[self.sizes[p] for p in parts]
            for w in set(keys):
                if w not in self._dispersion:self._dispersion[w]=dispersion([self.partitions[p][w] for p in parts],sizes)
                dp,dn=self._dispersion[w]
                rows.append(dict(word=w,dp=dp,dpnorm_corrected=dn,frequency=self.counter[w]))
            byword={r['word']:r for r in rows};self.details['dispersion']=rows
            return {**summary([byword[w]['dp'] for w in keys],'FREQ10.dp.token'),**summary([byword[w]['dpnorm_corrected'] for w in keys],'FREQ10.dpnorm.token')}
        if fid.startswith('MWE'):
            grams=self.document_grams(rec,[2,3,4] if fid in {'MWE01','MWE04'} else [2] if fid in {'MWE02','MWE03','MWE07','MWE08'} else [])
            if fid=='MWE01':
                for order,gs in grams.items():out.update(summary([self.ngrams[order][g] for g in gs],f'MWE01.order{order}_reference_count'))
            elif fid=='MWE04':out={f'MWE04.order{k}_ttr':ratio(len(set(gs)),len(gs)) for k,gs in grams.items()}
            elif fid=='MWE05':
                order=self.options.get('bundle_order',4);minfreq=self.options.get('bundle_min_frequency',10);mindocs=self.options.get('bundle_min_documents',3)
                covered=set();position=0
                for s in sentences:
                    for i in range(len(s)-order+1):
                        g=tuple(s[i:i+order])
                        if self.ngrams[order][g]>=minfreq and self.ranges[order][g]>=mindocs:covered.update(range(position+i,position+i+order))
                    position+=len(s)
                out={'MWE05.bundle_covered_token_rate':ratio(len(covered),n)}
            elif fid=='MWE06':
                profile=defaultdict(list)
                for seq in rec.get('pos_sentences',[]):
                    for (a,pa),(b,pb) in zip(seq,seq[1:]):
                        if (pa,pb) in {('ADJ','NOUN'),('VERB','NOUN')} and (a,b) in self.pair_stats:profile[pa+'_'+pb].append(self.pair_stats[(a,b)]['pmi'])
                for p,values in profile.items():out.update(summary(values,'MWE06.adjacent_'+p+'_pmi'))
            else:
                fields={'MWE02':['pmi'],'MWE03':['t_score'],'MWE07':['delta_p_y_given_x','delta_p_x_given_y'],'MWE08':['logdice']}[fid]
                for field in fields:out.update(summary([self.pair_stats[g][field] for g in grams[2] if g in self.pair_stats],fid+'.adjacent_'+field))
            self.details['collocations']=list(self.pair_stats.values());return out
        if fid=='INF07':
            if len(self.records)<2:raise Unavailable('JS散度需要其他参照文本')
            mine=Counter(keys);reference=self.counter-mine
            if not n or not reference.total():raise Unavailable('空比较分布','undefined')
            support=set(mine)|set(reference);p=np.array([mine[w]/n for w in support]);q=np.array([reference[w]/reference.total() for w in support]);m=(p+q)/2
            def kl(a,b):keep=a>0;return float(np.sum(a[keep]*np.log2(a[keep]/b[keep])))
            return {'INF07.js_bits_vs_other_documents':(kl(p,m)+kl(q,m))/2}
        if fid=='STY02':
            order=self.options.get('character_ngram_order',3);raw=rec['text'];counts=Counter(raw[i:i+order] for i in range(len(raw)-order+1));total=counts.total()
            rec.setdefault('details',{})['character_ngrams']=[dict(ngram=g,count=c,proportion=ratio(c,total)) for g,c in counts.items()]
            return {'STY02.character_ngram_types':len(counts),'STY02.character_ngram_entropy_bits':entropy(counts.values())}
        if fid=='STY07':
            pair=rec['meta'].get('pair_id')
            peers=[r for r in self.records if r['id']!=rec['id'] and r['meta'].get('pair_id')==pair] if pair else []
            if len(peers)!=1:raise Unavailable('LSM需要pair_id恰好匹配两篇文本')
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
                graph,values=graph_measures(self.pairs,set(self.counter),self.network_features)
                self._graph=(graph,values);self.details['network_nodes']=graph
            graph,values=self._graph
            fields={'NET01':['in_degree','out_degree','in_strength','out_strength'],'NET02':['clustering'],'NET05':['betweenness']}
            if fid in fields:
                return {k:v for field in fields[fid] for k,v in summary([r[field] for r in graph],fid+'.'+field).items()}
            return {k:v for k,v in values.items() if k.startswith(fid+'.')}
        if fid.startswith('QL'):
            values=self.laws()
            if fid in {'QL01','QL02','QL03'}:
                out={k:v for k,v in values.items() if k.startswith(fid+'.')}
                if not out:raise Unavailable('需下载规律拟合包，或数据不足','resource_required')
                return out
            if fid=='QL04':
                from .managed_r import fit
                result=fit(self.details['frequency_spectrum'],self.options.get('lnre_model','fzm'));self.details['lnre_fit']=[result]
                return {'QL04.'+k:v for k,v in result.get('parameters',{}).items()}
            if fid=='QL05':
                try:from scipy.optimize import minimize_scalar
                except ImportError:raise Unavailable('请下载规律拟合包','resource_required')
                lengths=np.array([sum(c.isalpha() for c in w) for w in keys]);lengths=lengths[lengths>0]
                if not len(lengths):raise Unavailable('无正整数字母长度','undefined')
                def loss(lam):return float(len(lengths)*(lam+math.log1p(-math.exp(-lam)))-lengths.sum()*math.log(lam)+sum(math.lgamma(int(x)+1) for x in lengths))
                result=minimize_scalar(loss,bounds=(.0001,max(2,float(lengths.mean())*2)),method='bounded')
                rows=[dict(letters=k,count=v) for k,v in sorted(Counter(lengths.tolist()).items())];rec.setdefault('details',{})['length_distribution']=rows
                return {'QL05.zero_truncated_poisson_lambda':float(result.x),'QL05.nll':float(result.fun),'QL05.aic':2+2*float(result.fun)}
            if fid=='QL06':
                try:from scipy.optimize import curve_fit
                except ImportError:raise Unavailable('请下载规律拟合包','resource_required')
                rows=[]
                for s in rec.get('token_sentences',[]):
                    if s:rows.append(dict(sentence_words=len(s),mean_word_letters=float(np.mean([sum(c.isalpha() for c in w) for w in s]))))
                if len(rows)<4 or len({r['sentence_words'] for r in rows})<4:raise Unavailable('Menzerath拟合需要至少4个不同构体长度','undefined')
                x=np.array([r['sentence_words'] for r in rows]);y=np.array([r['mean_word_letters'] for r in rows]);f=lambda x,a,b,c:a*x**b*np.exp(c*x)
                params,cov=curve_fit(f,x,y,p0=[4.,-.1,0.],bounds=([0,-5,-1],[100,5,1]),maxfev=10000)
                rec.setdefault('details',{})['menzerath_units']=rows
                return {'QL06.'+k:float(v) for k,v in zip(['a','b','c'],params)}
            if fid=='QL07':
                rows=[dict(word=w,frequency=f,letters=sum(c.isalpha() for c in w)) for w,f in self.counter.items()];self.details['abbreviation_pairs']=rows
                x=np.array([r['frequency'] for r in rows]);y=np.array([r['letters'] for r in rows])
                return {'QL07.type_pearson_frequency_letters':float(np.corrcoef(x,y)[0,1]) if len(x)>2 and x.std() and y.std() else None}
            if fid=='QL08':
                window=self.options.get('taylor_window',50);chunks=[Counter(self.sequences[i:i+window]) for i in range(0,len(self.sequences)-window+1,window)]
                if len(chunks)<3:raise Unavailable('Taylor需要至少3个完整窗口','undefined')
                rows=[]
                for w in self.counter:
                    vs=np.array([c[w] for c in chunks]);mu=float(vs.mean());sd=float(vs.std())
                    rows.append(dict(word=w,mean=mu,sd_population=sd))
                self.details['taylor_windows']=rows;valid=[r for r in rows if r['mean']>0 and r['sd_population']>0]
                x=np.log([r['mean'] for r in valid]);y=np.log([r['sd_population'] for r in valid])
                if len(x)<3 or not x.std():raise Unavailable('Taylor回归需要变化的均值与标准差','undefined')
                a,b=np.polyfit(x,y,1);return {'QL08.sd_mu_exponent':float(a),'QL08.log_intercept':float(b)}
            field={'QL09':'burstiness','QL10':'memory','QL11':'finite_burstiness_periodic'}[fid]
            return summary([r[field] for r in self.details['recurrence']],fid+'.'+field+'.type')
        raise Unavailable('缺少语料方法配置')
