"""Explicit mathematical kernels; all randomization is local and seeded."""
import math
from collections import Counter, deque
import numpy as np
from .util import ratio, Unavailable

def mtld(words, threshold=.72):
    def direction(seq):
        factors=0.; types=set(); n=0
        for w in seq:
            types.add(w); n+=1
            if len(types)/n <= threshold:
                factors+=1; types=set(); n=0
        if n: factors+=(1-len(types)/n)/(1-threshold)
        return ratio(len(seq),factors)
    if not words: return None
    a,b=direction(words),direction(words[::-1])
    return (a+b)/2 if a is not None and b is not None else None

def diversity(words, window=50, threshold=.72, sample=42):
    n=len(words); c=Counter(words); v=len(c)
    if not n: raise Unavailable("空词序列", "undefined")
    out={"LD01.ttr":v/n,"LD02.root_ttr":v/math.sqrt(n),"LD03.cttr":v/math.sqrt(2*n),
         "LD04.herdan_c":ratio(math.log(v),math.log(n)),
         "LD05.maas_a2_ln":ratio(math.log(n)-math.log(v),math.log(n)**2),
         "LD06.msttr":None,"LD07.mattr":None,"LD08.mtld_bidirectional":mtld(words,threshold),
         "LD09.hdd":None,"LD11.yule_k":10000*(sum(f*f for f in c.values())-n)/n**2,
         "LD12.simpson_d":ratio(sum(f*(f-1) for f in c.values()),n*(n-1)),
         "LD13.hapax_proportion":sum(f==1 for f in c.values())/v,"LD13.hapax_types":sum(f==1 for f in c.values())}
    if n>=window:
        chunks=[words[i:i+window] for i in range(0,n-window+1,window)]
        out["LD06.msttr"]=sum(len(set(x))/window for x in chunks)/len(chunks)
        counts=Counter(words[:window]); total=len(counts)
        for i in range(window,n):
            old=words[i-window]; counts[old]-=1
            if not counts[old]: del counts[old]
            counts[words[i]]+=1; total+=len(counts)
        out["LD07.mattr"]=total/((n-window+1)*window)
    if n>=sample:
        def zero_prob(f):
            if n-f<sample: return 0.
            return math.exp(sum(math.log(n-f-i)-math.log(n-i) for i in range(sample)))
        out["LD09.hdd"]=sum(1-zero_prob(f) for f in c.values())/sample
    return out

def golden_min(fn, low, high, iterations=80):
    phi=(math.sqrt(5)-1)/2
    a,b=low,high; c=b-phi*(b-a); d=a+phi*(b-a); fc,fd=fn(c),fn(d)
    for _ in range(iterations):
        if fc<fd: b,d,fd=d,c,fc; c=b-phi*(b-a); fc=fn(c)
        else: a,c,fc=c,d,fd; d=a+phi*(b-a); fd=fn(d)
    return (a+b)/2

def vocd(words, seed=1729, repeats=100):
    if len(words)<50: raise Unavailable("voc-D 需要至少50词；无放回抽样35–50词", "undefined")
    rng=np.random.default_rng(seed); ns=np.arange(35,51); ds=[]
    for run in range(3):
        ttrs=np.array([np.mean([len({words[i] for i in rng.choice(len(words),int(n),replace=False)})/n for _ in range(repeats)]) for n in ns])
        def loss(logd):
            d=math.exp(logd); predicted=(d/ns)*(np.sqrt(1+2*ns/d)-1)
            return float(np.square(predicted-ttrs).sum())
        d=math.exp(golden_min(loss,math.log(.001),math.log(1e7)))
        ds.append(d)
    if max(ds)>9e6: raise Unavailable("D拟合达到搜索边界", "undefined")
    return float(np.mean(ds))

def association(a,b,c,d):
    if min(a,b,c,d)<0: raise ValueError("Negative contingency count")
    total=a+b+c+d; fx=a+b; fy=a+c
    expected=ratio(fx*fy,total)
    return {"pmi": math.log2(a*total/(fx*fy)) if a and fx and fy else None,
            "t_score":(a-expected)/math.sqrt(a) if a and expected is not None else None,
            "delta_p_y_given_x":ratio(a,a+b)-ratio(c,c+d) if a+b and c+d else None,
            "delta_p_x_given_y":ratio(a,a+c)-ratio(b,b+d) if a+c and b+d else None,
            "logdice":14+math.log2(2*a/(fx+fy)) if a and fx+fy else None}

def dispersion(counts,sizes):
    sizes=np.asarray(sizes,dtype=float); counts=np.asarray(counts,dtype=float)
    keep=sizes>0; sizes=sizes[keep]; counts=counts[keep]
    if not counts.sum() or len(sizes)<2: return None,None
    s=sizes/sizes.sum(); dp=float(np.abs(counts/counts.sum()-s).sum()/2)
    return dp,dp/(1-float(s.min()))

def uid(values, power=1.25, reference=None):
    s=np.asarray(values,dtype=float)
    if not len(s): return {}
    out={"INF08.superlinear_moment":float(np.mean(s**power)),
         "INF08.within_sentence_variance":float(np.var(s)),
         "INF08.local_squared_difference":float(np.mean(np.diff(s)**2)) if len(s)>1 else None,
         "INF08.max":float(s.max())}
    if reference is not None: out["INF08.reference_squared_deviation"]=float(np.mean((s-reference)**2))
    return out

def recurrence(positions):
    gaps=np.diff(positions); out={"intervals":gaps.tolist(),"burstiness":None,"memory":None}
    if len(gaps)>=2:
        mu=float(gaps.mean()); sd=float(gaps.std())
        out["burstiness"]=ratio(sd-mu,sd+mu)
    if len(gaps)>=3 and gaps[:-1].std()>0 and gaps[1:].std()>0:
        out["memory"]=float(np.corrcoef(gaps[:-1],gaps[1:])[0,1])
    return out

def finite_burstiness(positions, length):
    n=len(positions)
    if n<3 or length<=0: return None
    gaps=np.diff(list(positions)+[positions[0]+length]); r=float(gaps.std()/gaps.mean())
    return ratio(math.sqrt(n+1)*r-math.sqrt(n-1),(math.sqrt(n+1)-2)*r+math.sqrt(n-1))

def grid_transitions(grid, width=2):
    from itertools import product
    out={"".join(t):0 for t in product("SOX-",repeat=width)}
    e=len(grid); s=len(grid[0]) if e else 0
    if not e or s<width: return {k:None for k in out}
    for entity in grid:
        for j in range(s-width+1): out["".join(entity[j:j+width])]+=1
    return {k:v/(e*(s-width+1)) for k,v in out.items()}

def graph_measures(edges, nodes):
    """Directed, binary, ordered pairs; k<2 clustering=0 is our declared convention."""
    nodes=sorted(nodes); adj={x:set() for x in nodes}; incoming={x:set() for x in nodes}
    for a,b in edges:
        if a!=b: adj[a].add(b); incoming[b].add(a)
    weights=Counter(edges); bet={x:0. for x in nodes}; dist_total=0; inv_total=0.; unreachable=0
    for source in nodes:
        stack=[]; pred={v:[] for v in nodes}; sigma={v:0. for v in nodes}; sigma[source]=1.
        d={source:0}; q=deque([source])
        while q:
            v=q.popleft(); stack.append(v)
            for w in adj[v]:
                if w not in d: d[w]=d[v]+1; q.append(w)
                if d[w]==d[v]+1: sigma[w]+=sigma[v]; pred[w].append(v)
        for dest in nodes:
            if dest==source: continue
            if dest not in d: unreachable+=1
            else: dist_total+=d[dest]; inv_total+=1/d[dest]
        delta={v:0. for v in nodes}
        for w in reversed(stack):
            for v in pred[w]: delta[v]+=sigma[v]/sigma[w]*(1+delta[w])
            if w!=source: bet[w]+=delta[w]
    rows=[]
    for v in nodes:
        ns=adj[v]; k=len(ns); between=sum(b in ns for a in ns for b in adj[a])
        rows.append(dict(word=v,in_degree=len(incoming[v]),out_degree=k,
                         in_strength=sum(weights[(a,v)] for a in incoming[v]),
                         out_strength=sum(weights[(v,b)] for b in ns),
                         clustering=between/(k*(k-1)) if k>=2 else 0.,betweenness=bet[v]))
    denom=len(nodes)*(len(nodes)-1)
    return rows,{"NET03.mean_geodesic_directed_all_pairs":ratio(dist_total,denom) if not unreachable else None,
                 "NET03.unreachable_pairs":unreachable,"NET04.global_efficiency":ratio(inv_total,denom)}
