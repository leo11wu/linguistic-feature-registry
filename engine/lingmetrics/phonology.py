"""CMUdict neighbourhoods, preserving first pronunciation and exact edit distance."""
from collections import Counter, defaultdict
from functools import lru_cache
import re
import numpy as np

@lru_cache(maxsize=1)
def dictionary():
    from .core import pronunciation_lexicon
    return {w:ps[0] for w,ps in pronunciation_lexicon().items() if re.fullmatch('[a-z]+',w)}

@lru_cache(maxsize=1)
def spellings():return tuple(dictionary())

@lru_cache(maxsize=32)
def spelling_bucket(length):
    words=[w for w in dictionary() if len(w)==length]
    return np.frombuffer(''.join(words).encode('ascii'),dtype=np.uint8).reshape(len(words),length) if length else np.empty((0,0),dtype=np.uint8)

@lru_cache(maxsize=1)
def phone_strings():
    phones={w:tuple(p[:-1] if p[-1:].isdigit() else p for p in ps) for w,ps in dictionary().items()}
    symbols={p:chr(i+256) for i,p in enumerate(sorted({p for ps in phones.values() for p in ps}))}
    # An injective alphabet preserves phoneme edit distances and homophones.
    return {w:''.join(symbols[p] for p in ps) for w,ps in phones.items()}

@lru_cache(maxsize=1)
def biphone_counts():
    counts=Counter((a,b) for ps in dictionary().values() for a,b in zip(ps,ps[1:]))
    return counts,sum(counts.values())

@lru_cache(maxsize=32768)
def value(fid,word):
    from rapidfuzz import process
    from rapidfuzz.distance import Levenshtein
    lex=dictionary()
    if fid=='PHO03':
        bucket=spelling_bucket(len(word))
        target=np.array([ord(c) for c in word],dtype=np.uint32)
        return int(np.count_nonzero(np.count_nonzero(bucket!=target,axis=1)==1))
    if fid=='PHO04':
        matches=process.extract(word,spellings(),scorer=Levenshtein.distance,limit=21)
        distances=[distance for candidate,distance,_ in matches if candidate!=word][:20]
        return sum(distances)/20 if len(distances)==20 else None
    if word not in lex:return None
    if fid=='PHO05':
        phones=phone_strings()
        matches=process.extract(phones[word],phones,scorer=Levenshtein.distance,limit=21)
        distances=[distance for _,distance,spelling in matches if spelling!=word][:20]
        return sum(distances)/20 if len(distances)==20 else None
    pairs,total=biphone_counts();target=lex[word]
    return float(np.mean([pairs[(a,b)]/total for a,b in zip(target,target[1:])])) if len(target)>1 else None

def clear_cache():
    for fn in [value,spelling_bucket,phone_strings,biphone_counts,spellings,dictionary]:fn.cache_clear()
