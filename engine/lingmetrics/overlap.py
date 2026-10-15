"""Exact all-sentence Jaccard summaries without materializing a quadratic row table."""
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path
import csv, gzip, os
import numpy as np


def all_sentence_overlap(sentences, detail_path=None, cancelled=lambda: False):
    sets=[set(s) for s in sentences]
    n=len(sets);sizes=np.asarray([len(s) for s in sets],dtype=np.int64)
    postings=defaultdict(list)
    for i,words in enumerate(sets):
        for word in words:postings[word].append(i)
    postings={w:np.asarray(ids,dtype=np.int64) for w,ids in postings.items()}
    # A bin is (intersection size, union size). Counts retain every valid pair,
    # including zero overlaps; no sampling, rounding or floating-point buckets.
    base=2*int(sizes.max(initial=0))+1;histogram=Counter()
    destination=Path(detail_path) if detail_path is not None else None
    temporary=destination.with_name(destination.name+'.partial') if destination else None
    try:
        with ExitStack() as stack:
            writer=None
            if destination:
                destination.parent.mkdir(parents=True,exist_ok=True)
                handle=stack.enter_context(gzip.open(temporary,'wt',encoding='utf-8-sig',newline='',compresslevel=1))
                writer=csv.writer(handle);writer.writerow(['left','right','jaccard'])
            for i,words in enumerate(sets[:-1]):
                if cancelled():raise InterruptedError('已取消句对计算')
                tails=[postings[w][np.searchsorted(postings[w],i+1):] for w in words]
                shared=np.bincount(np.concatenate(tails),minlength=n)[i+1:] if tails else np.zeros(n-i-1,dtype=np.int64)
                unions=sizes[i]+sizes[i+1:]-shared
                valid=unions>0
                codes,counts=np.unique(shared[valid]*base+unions[valid],return_counts=True)
                for code,count in zip(codes,counts):histogram[int(code)]+=int(count)
                if writer is not None:
                    writer.writerows((i,j,float(a)/int(b) if b else '') for j,a,b in zip(range(i+1,n),shared,unions))
        if destination:os.replace(temporary,destination)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()
    prefix='DIS03.jaccard'
    if not histogram:return {prefix+'.mean':None,prefix+'.valid_n':0}
    scores=np.asarray([(code//base)/(code%base) for code in histogram],dtype=float)
    counts=np.asarray(list(histogram.values()),dtype=np.int64);total=int(counts.sum())
    order=np.argsort(scores);ordered=scores[order];cumulative=np.cumsum(counts[order])
    median=float((ordered[np.searchsorted(cumulative,(total-1)//2,side='right')]+ordered[np.searchsorted(cumulative,total//2,side='right')])/2)
    mean=float(np.dot(scores,counts)/total)
    variance=float(np.dot((scores-mean)**2,counts)/total)
    return {prefix+'.mean':mean,prefix+'.sd_population':float(np.sqrt(variance)),
            prefix+'.median':median,prefix+'.min':float(scores.min()),prefix+'.max':float(scores.max()),prefix+'.valid_n':total}
