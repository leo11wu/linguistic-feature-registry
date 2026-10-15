from __future__ import annotations
import re
from collections import Counter
from functools import lru_cache
from .util import CACHE, Unavailable, summary, ratio

@lru_cache(maxsize=1)
def pipeline():
    from .resources import marker
    if not marker('stanza').exists(): raise Unavailable('请下载原始PTB成分树资源','resource_required')
    import stanza
    return stanza.Pipeline('en',dir=str(CACHE/'stanza'),processors='tokenize,mwt,pos,constituency',package={'constituency':'ptb3_charlm'},download_method=None,use_gpu=False,verbose=False)

def tree_results(forest):
    from neosca.ns_tregex.tree import Tree
    from neosca.ns_sca import l2sca
    trees=list(Tree.fromstring(forest)); counts=Counter(); heights=[]; yngve=[]; frazier=[]; frazier_windows=[]; np_sizes=[]; adjectives=[]; phrase_counts=Counter(); rows=[]; adverbials=0
    names=['S','VP1','VP2','C1','C2','T1','T2','CN1','CN2','CN3','DC','CT','CP']
    for sn,tree in enumerate(trees):
        for name in names:
            last=None
            for node in getattr(l2sca,name).searchNodeIterator(tree):
                if node is not last: counts[name]+=1
                last=node
        w=len(re.findall(r'\([A-Z]+\$? [^()—–-]+\)',str(tree)))
        counts['W']+=w
        sentence_y=[]
        def walk(node, depth=0, score=0):
            if node.label=='EDITED': return
            if not node.children:
                sentence_y.append(score); return
            if node.children and node.children[0].children:
                phrase_counts[node.label]+=1
            for i,child in enumerate(node.children): walk(child,depth+1,score+len(node.children)-i-1)
        def height(node): return 0 if not node.children else 1+max(height(c) for c in node.children)
        def leaves(node): return [node] if not node.children else [x for c in node.children for x in leaves(c)]
        score_tree=next(Tree.fromstring(str(tree)))
        def prune(node):
            node.children=[c for c in node.children if c.label!='EDITED']
            for c in node.children:prune(c)
        prune(score_tree)
        walk(score_tree); heights.append(height(tree)); yngve.extend(sentence_y)
        sentence_f=[]
        for leaf in leaves(score_tree):
            cur=leaf.parent; score=0.; last_sentence=False
            if cur is None or cur.label=='-NONE-': continue
            if any(a.label=='EDITED' for a in ancestors(leaf)): continue
            while cur.parent is not None:
                parent=cur.parent
                if parent.children[0] is not cur:
                    preceding=parent.children[:parent.children.index(cur)]
                    empty_np=cur.label=='VP' and len(preceding)==1 and preceding[0].label=='NP' and all(x.parent and x.parent.label=='-NONE-' for x in leaves(preceding[0]))
                    if empty_np: score+=1
                    else: break
                cur=parent
                if cur.label=='ROOT': break
                is_sentence=cur.label in {'S','SBAR','SINV','SQ','SBARQ'}
                if is_sentence:
                    if not last_sentence:score+=1.5
                else:score+=1
                last_sentence=is_sentence
            sentence_f.append(score)
        frazier.extend(sentence_f)
        frazier_windows.append(max((sum(sentence_f[i:i+3]) for i in range(len(sentence_f)-2)),default=None))
        for node in tree.preorder_iter():
            if node.label=='NP' and not any(x.label=='NP' for x in node.children):
                ls=leaves(node); np_sizes.append(len(ls))
                adjectives.append(sum((x.parent.label or '').startswith('JJ') for x in ls))
            if node.label in {'ADVP','PP'} and node.parent and node.parent.label in {'VP','S','SINV','SQ'}:adverbials+=1
        rows.append(dict(sentence_id=sn,tree=str(tree),yngve_scores=sentence_y,frazier_scores=sentence_f,word_count_l2sca=w))
    counts['VP']=counts['VP1']+counts['VP2']; counts['C']=counts['C1']+counts['C2']; counts['T']=counts['T1']+counts['T2']; counts['CN']=sum(counts[k] for k in ['CN1','CN2','CN3'])
    ratios=[('W','T'),('W','C'),('C','S'),('VP','T'),('C','T'),('DC','C'),('DC','T'),('T','S'),('CT','T'),('CP','T'),('CP','C'),('CN','T'),('CN','C')]
    out={f'SYN{i:02d}.l2sca_{a}_per_{b}':ratio(counts[a],counts[b]) for i,(a,b) in enumerate(ratios,1)}
    out.update(summary(heights,'SYN14.tree_height')); out.update(summary(np_sizes,'SYN16.minimal_np_words'));out.update(summary(adjectives,'SYN17.adjectives_per_minimal_np')); out.update(summary(yngve,'SYN23.yngve'))
    out.update(summary(frazier,'SYN24.frazier'));out.update(summary(frazier_windows,'SYN24.max_three_word_sum_sentence'))
    out['SYN21.direct_ADVP_PP_per_clause']=ratio(adverbials,counts['C'])
    out.update({'SYN15.'+p+'_per_sentence':ratio(v,len(trees)) for p,v in phrase_counts.items()})
    return out,rows,dict(counts)

def ancestors(node):
    while node.parent is not None:
        node=node.parent;yield node

def measure(fid,ctx):
    if not hasattr(ctx,'_constituency'):
        doc=pipeline()(ctx.raw); forest='\n'.join(str(s.constituency) for s in doc.sentences)
        values,rows,counts=tree_results(forest)
        ctx._constituency=values; ctx.details['constituency']=rows; ctx.details['l2sca_counts']=[counts]
    return {k:v for k,v in ctx._constituency.items() if k.startswith(fid+'.')}
