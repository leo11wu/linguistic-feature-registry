"""Reproducible software benchmarks, not measurements of linguistic validity.

Run in separate processes with the desired source tree on PYTHONPATH.
Optional phonology/model cases need the matching managed dependencies.
"""
import argparse,contextlib,csv,hashlib,inspect,io,json,math,resource,statistics,sys,time
from pathlib import Path
import numpy as np

def timed(fn,repeats=3):
    samples=[];value=None
    for _ in range(repeats):
        start=time.perf_counter();value=fn();samples.append(time.perf_counter()-start)
    return {'median_seconds':statistics.median(samples),'trials_seconds':samples},value

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def kernels():
    from lingmetrics import stats
    result={};words=['w'+str((i*13+i//11)%300) for i in range(6000)]
    timing,value=timed(lambda:stats.vocd(words));result['vocd']={**timing,'value':value}
    words=['w'+str(i%4000) for i in range(20000)]
    timing,value=timed(lambda:stats.diversity(words));result['diversity']={**timing,'values_sha256':digest(value)}
    n=80;edges=[(i//2,i) for i in range(1,n)]
    def permutations():
        rng=np.random.default_rng(1729)
        if hasattr(stats,'permuted_lengths'):return stats.permuted_lengths(n,edges,5000,rng).tolist()
        out=[]
        for _ in range(5000):
            p=rng.permutation(n);out.append(sum(abs(int(p[a])-int(p[b])) for a,b in edges))
        return out
    timing,value=timed(permutations);result['dependency_random_baseline']={**timing,'values_sha256':digest(value),'permutations':5000,'nodes':n}
    nodes=[str(i) for i in range(500)];edges=[(str(i),str((i+j)%500)) for i in range(500) for j in [1,7,29]]
    def degrees():
        args={'requested':{'NET01'}} if 'requested' in inspect.signature(stats.graph_measures).parameters else {}
        rows,_=stats.graph_measures(edges,nodes,**args)
        return [{k:r[k] for k in ['word','in_degree','out_degree','in_strength','out_strength']} for r in rows]
    timing,value=timed(degrees);result['network_degree_only']={**timing,'values_sha256':digest(value),'nodes':500,'edges':1500}
    return result

def phonology():
    import spacy
    from lingmetrics.core import Text
    from lingmetrics.lexicons import lexical_measure
    nlp=spacy.blank('en');nlp.add_pipe('sentencizer');result={}
    text=('The cat read a book. The dog saw a house. Language and memory shape human thought. '*8)
    for index in range(3):
        ctx=Text(text,nlp);start=time.perf_counter()
        values={fid:lexical_measure(fid,ctx) for fid in ['PHO03','PHO04','PHO05','PHO06']}
        result['cold' if not index else 'warm_'+str(index)]={'seconds':time.perf_counter()-start,'values_sha256':digest(values),'tokens':ctx.n,'types':len(ctx.counts)}
    return result

def model():
    import torch
    from transformers import BertConfig,BertForMaskedLM
    from lingmetrics import models
    torch.set_num_threads(2);torch.manual_seed(1729)
    m=BertForMaskedLM(BertConfig(vocab_size=30522,hidden_size=64,intermediate_size=128,num_hidden_layers=2,num_attention_heads=4,max_position_embeddings=128)).eval()
    ids=torch.randint(3,30522,(16,96));positions=list(range(16,32));targets=ids[torch.arange(16),positions].clone()
    for i,p in enumerate(positions):ids[i,p]=1
    def score():
        with torch.inference_mode():
            if hasattr(models,'masked_logits'):return models.masked_logits(m,ids,positions).log_softmax(-1).gather(1,targets[:,None])[:,0].tolist()
            logits=m(ids).logits.log_softmax(-1)
            return logits[torch.arange(16),positions,targets].tolist()
    score();timing,value=timed(score)
    return dict(bert_single_mask={**timing,'scores':value,'fixture':'random weights; BERT architecture, 30522 vocabulary, 2 layers, hidden 64, 16 masks, sentence length 96; CPU 2 threads','vocabulary_rows':16 if hasattr(models,'masked_logits') else 16*96})

def batch(input_path,count,output,corpus=False):
    from lingmetrics.runner import run
    with Path(input_path).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))[:count]
    input_file=Path(output).parent/('input-'+str(count)+'.csv')
    with input_file.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    job=dict(inputs=[str(input_file)],output=str(output))
    if corpus:job['features']=['FREQ10','INF07',*[f'MWE{i:02d}' for i in range(1,9)],*[f'NET{i:02d}' for i in range(1,6)],'QL09','QL10','QL11']
    with contextlib.redirect_stdout(io.StringIO()):meta=run(job)
    return {('corpus_batch' if corpus else 'default_batch'):{'seconds':meta['elapsed_seconds'],'documents':count,'features':job.get('features','default61'),'feature_matrix_sha256':hashlib.sha256((Path(output)/'features.csv').read_bytes()).hexdigest(),'peak_memory_bytes':meta['peak_memory_bytes'],'timings':meta.get('timings')}}

def main():
    p=argparse.ArgumentParser();p.add_argument('case',choices=['kernels','phonology','model','batch','corpus']);p.add_argument('--report',required=True);p.add_argument('--input');p.add_argument('--count',type=int,default=100);p.add_argument('--output');args=p.parse_args()
    values=batch(args.input,args.count,args.output,corpus=args.case=='corpus') if args.case in {'batch','corpus'} else globals()[args.case]()
    result=dict(case=args.case,results=values,peak_memory_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024))
    Path(args.report).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
