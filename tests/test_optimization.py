"""Independent equivalence checks for the 0.1.1 performance paths."""
import csv,importlib.util,json,math,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from lingmetrics.stats import permuted_lengths,vocd,graph_measures
from lingmetrics.runner import export_documents,stream_table

class OptimizationTests(unittest.TestCase):
    def test_permutations_preserve_draws_and_rng_state(self):
        a=np.random.default_rng(1729);b=np.random.default_rng(1729)
        for n,edges in [(3,[(0,1),(0,2)]),(37,[(i//2,i) for i in range(1,37)]),(5,[])]:
            reference=[]
            for _ in range(513):
                p=a.permutation(n);reference.append(sum(abs(int(p[x])-int(p[y])) for x,y in edges))
            actual=permuted_lengths(n,edges,513,b,max_cells=57)
            np.testing.assert_array_equal(actual,reference)
            self.assertEqual(a.bit_generator.state,b.bit_generator.state)

    def test_vocd_matches_previous_seeded_fit(self):
        self.assertEqual(vocd(['a','b','c','d','a','a','b','e']*30),0.3398313158594064)

    def test_degree_only_skips_shortest_paths(self):
        edges=[('a','b'),('a','b'),('b','c'),('c','a'),('c','d')]
        full,_=graph_measures(edges,['a','b','c','d','e'])
        with patch('lingmetrics.stats.deque',side_effect=AssertionError('unrequested BFS')):
            selected,values=graph_measures(edges,['a','b','c','d','e'],{'NET01'})
        self.assertEqual(values,{})
        for a,b in zip(full,selected):
            for key,value in b.items():self.assertEqual(a[key],value)
        for fid in ['NET02','NET03','NET04','NET05']:
            rows,values=graph_measures(edges,['a','b','c','d','e'],{fid})
            for a,b in zip(full,rows):
                for key,value in b.items():self.assertEqual(a[key],value)
            _,all_values=graph_measures(edges,['a','b','c','d','e'])
            for k,v in values.items():self.assertEqual(v,all_values[k])

    def test_export_two_scans_matches_old_tables(self):
        records=[dict(id='甲',meta={'label':'a,"b"\nc'},features={'LEN01.tokens':2.,'LD01.ttr':None},statuses=[dict(feature_id='LEN01',status='computed',reason='')],tokens=[dict(word='cat',lookup_key='cat',is_punctuation=False,phonemes=['K','AE1','T']),dict(word='.',lookup_key='.',is_punctuation=True)],sentences=[dict(sentence_id=0,text='cat.')],details={'tree':[dict(children=['x','y'],weight=.25)]}),dict(id='乙',meta={},features={'LEN01.tokens':0},statuses=[dict(feature_id='LEN01',status='computed',reason='')],tokens=[],sentences=[],details={'empty':[]})]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'old';new=root/'new';old.mkdir();new.mkdir();scans=[]
            def source():scans.append(1);yield from records
            export_documents(new,source)
            self.assertEqual(len(scans),2)
            extracts={'features':lambda r:[dict(doc_id=r['id'],**{'meta.'+k:v for k,v in r['meta'].items()},**r['features'])],'feature_status':lambda r:[dict(doc_id=r['id'],**x) for x in r['statuses']],'tokens':lambda r:[dict(doc_id=r['id'],**x) for x in r['tokens']],'sentences':lambda r:[dict(doc_id=r['id'],**x) for x in r['sentences']],'word_frequency':lambda r:[dict(doc_id='甲',word='cat',frequency=1)] if r['id']=='甲' else []}
            for name,fn in extracts.items():stream_table(old/(name+'.csv'),lambda:iter(records),fn)
            for name in ['tree','empty']:stream_table(old/'details'/(name+'.csv'),lambda:iter(records),lambda r,name=name:[dict(doc_id=r['id'],**x) for x in r['details'].get(name,[])])
            for path in old.rglob('*.csv'):self.assertEqual(path.read_bytes(),(new/path.relative_to(old)).read_bytes(),str(path))

    def test_sentence_embeddings_reused_within_document_only(self):
        import spacy
        from lingmetrics.core import Text
        from lingmetrics import models
        nlp=spacy.blank('en');nlp.add_pipe('sentencizer')
        ctx=Text('One. Two. Three.\n\nFour.',nlp)
        def encode(texts,backend):return np.ones((len(texts),3),dtype=float)/math.sqrt(3)
        with patch.object(models,'embeddings',side_effect=encode) as mocked:
            models.measure('DIS08',ctx);models.measure('DIS09',ctx)
            self.assertEqual(mocked.call_count,1)
            models.measure('DIS10',ctx);self.assertEqual(mocked.call_count,2)
            models.measure('DIS08',Text('One. Two. Three.',nlp));self.assertEqual(mocked.call_count,3)

    def test_fast_alignment_keeps_ambiguous_and_uncovered_flags(self):
        import spacy
        from lingmetrics.core import Text
        from lingmetrics import models
        nlp=spacy.blank('en');nlp.add_pipe('sentencizer')
        for offsets in [[(0,3),(4,6),(6,9),(10,13)],[(0,9),(10,13)],[(10,13),(0,3)],[(0,3)]]:
            ctx=Text('cat walks dog',nlp);scores=[i+.25 for i in range(len(offsets))]
            with patch.object(models,'score_stream',return_value=(list(range(len(offsets))),offsets,scores)):
                actual=models.causal_scores(ctx)
            for token,row in zip(ctx.words,actual['words']):
                matches=[scores[i] for i,(a,b) in enumerate(offsets) if b>token.idx and a<token.idx+len(token.text)]
                self.assertEqual(row['surprisal_nats'],sum(matches) if matches else None)
            ambiguous=any(sum(b>t.idx and a<t.idx+len(t.text) for t in ctx.words)>1 for a,b in offsets)
            self.assertEqual(actual['ambiguous'],ambiguous)
            self.assertEqual(actual['uncovered'],sum(r['surprisal_nats'] is None for r in actual['words']))

@unittest.skipUnless(importlib.util.find_spec('rapidfuzz'),'optional rapidfuzz test dependency')
class PhonologyOptimizationTests(unittest.TestCase):
    def test_exact_neighbors_and_homophones(self):
        from lingmetrics import phonology
        from rapidfuzz.distance import Levenshtein
        from collections import Counter
        words=['cat','bat','cot','cut','hat','mat','rat','sat','pat','fat','dog','fog','log','hog','dig','bug','bag','beg','big','bog','book','look','cook','took','reed','read']
        lex={w:[['R','IY1','D']] if w in {'reed','read'} else [[*w.upper()]] for w in words}
        phonology.clear_cache()
        with patch('lingmetrics.core.pronunciation_lexicon',return_value=lex):
            phones={w:tuple(p[:-1] if p[-1:].isdigit() else p for p in ps[0]) for w,ps in lex.items()}
            pairs=Counter((a,b) for ps in lex.values() for a,b in zip(ps[0],ps[0][1:]));total=sum(pairs.values())
            for word in ['cat','read','reed','missing','cät','c_t','']:
                self.assertEqual(phonology.value('PHO03',word),sum(len(w)==len(word) and sum(a!=b for a,b in zip(w,word))==1 for w in lex))
                distances=sorted(Levenshtein.distance(word,w) for w in lex if w!=word)
                self.assertEqual(phonology.value('PHO04',word),sum(distances[:20])/20)
                distances=sorted(Levenshtein.distance(phones[word],p) for w,p in phones.items() if w!=word) if word in phones else []
                self.assertEqual(phonology.value('PHO05',word),sum(distances[:20])/20 if len(distances)>=20 else None)
                expected=float(np.mean([pairs[(a,b)]/total for a,b in zip(lex[word][0],lex[word][0][1:])])) if word in lex and len(lex[word][0])>1 else None
                self.assertEqual(phonology.value('PHO06',word),expected)
        phonology.clear_cache()

@unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('transformers'),'optional torch/transformers test dependencies')
class ModelOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        cls.threads=torch.get_num_threads();torch.set_num_threads(1)
    @classmethod
    def tearDownClass(cls):
        import torch
        torch.set_num_threads(cls.threads)
    def test_bert_selected_head_matches_full_single_mask_scores(self):
        import torch
        from transformers import BertConfig,BertForMaskedLM
        from lingmetrics.models import masked_logits
        torch.manual_seed(1729)
        model=BertForMaskedLM(BertConfig(vocab_size=97,hidden_size=24,num_hidden_layers=2,num_attention_heads=4,intermediate_size=32,max_position_embeddings=64)).eval()
        ids=torch.randint(3,97,(5,23));positions=[2,5,12,16,20]
        for i,p in enumerate(positions):ids[i,p]=1
        with torch.inference_mode():
            expected=model(ids).logits.log_softmax(-1)[torch.arange(5),positions]
            actual=masked_logits(model,ids,positions).log_softmax(-1)
        torch.testing.assert_close(actual,expected,rtol=0,atol=2e-6)

    def test_pythia_selected_head_preserves_long_stream_context(self):
        import torch
        from transformers import GPTNeoXConfig,GPTNeoXForCausalLM
        from lingmetrics import models
        torch.manual_seed(1729)
        model=GPTNeoXForCausalLM(GPTNeoXConfig(vocab_size=97,hidden_size=32,num_hidden_layers=2,num_attention_heads=4,intermediate_size=64,max_position_embeddings=32)).eval()
        class Tokenizer:
            bos_token_id=1;eos_token_id=2
            def __call__(self,text,**kw):return dict(input_ids=[3+ord(c)%94 for c in text],offset_mapping=[(i,i+1) for i in range(len(text))])
        tokenizer=Tokenizer();text='The language model keeps every left-context window. '*2
        ids=tokenizer(text)['input_ids'];all_ids=[1]+ids;reference=[]
        with torch.inference_mode():
            for start in range(1,len(all_ids),16):
                end=min(len(all_ids),start+16);begin=max(0,end-32)
                logits=model(torch.tensor([all_ids[begin:end]])).logits[0].log_softmax(-1)
                reference.extend(-float(logits[j-begin-1,all_ids[j]]) for j in range(start,end))
        with patch.object(models,'load',return_value=(tokenizer,model)):
            actual_ids,offsets,actual=models.score_stream(text)
        self.assertEqual(actual_ids,ids);self.assertEqual(len(actual),len(ids))
        np.testing.assert_allclose(actual,reference,rtol=0,atol=2e-6)

    def test_pll_measure_preserves_targets_and_aggregation(self):
        import torch
        from transformers import BertConfig,BertForMaskedLM
        from lingmetrics import models
        torch.manual_seed(1729)
        model=BertForMaskedLM(BertConfig(vocab_size=97,hidden_size=24,num_hidden_layers=2,num_attention_heads=4,intermediate_size=32,max_position_embeddings=64)).eval()
        class Tokenizer:
            all_special_ids=[0,1,2];mask_token_id=2
            def __call__(self,text,**kw):return {'input_ids':[0]+[3+ord(c)%94 for c in text]+[1]}
        tokenizer=Tokenizer();sentences=[SimpleNamespace(text='A long test sentence.'),SimpleNamespace(text='Another sentence.')]
        reference=[]
        with torch.inference_mode():
            for sentence in sentences:
                ids=tokenizer(sentence.text)['input_ids']
                for p in range(1,len(ids)-1):
                    masked=list(ids);masked[p]=2
                    reference.append(float(model(torch.tensor([masked])).logits.log_softmax(-1)[0,p,ids[p]]))
        ctx=SimpleNamespace(sentences=sentences,details={})
        with patch.object(models,'load',return_value=(tokenizer,model)):actual=models.measure('INF10',ctx)
        self.assertEqual(actual['INF10.scored_subwords'],len(reference))
        np.testing.assert_allclose([r['log_probability'] for r in ctx.details['mlm_scores']],reference,rtol=0,atol=2e-6)
        self.assertAlmostEqual(actual['INF10.pll_single_token'],sum(reference),places=4)

if __name__=='__main__':unittest.main()
