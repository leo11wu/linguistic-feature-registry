import csv, gzip, itertools, json, math, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lingmetrics.overlap import all_sentence_overlap
from lingmetrics.util import summary, csv_write, atomic_json, compress_outputs, read_json
from lingmetrics.fitting import table_path, read_table, fit
from lingmetrics.observations import choices, freeze_reference, load_reference
from lingmetrics.corpus import Corpus
from lingmetrics.runner import run


class ExactOverlapTests(unittest.TestCase):
    def test_histogram_matches_naive_pairs_including_empty_and_repeated_words(self):
        rng=np.random.default_rng(1729)
        cases=[[],[[]],[[],[],['a']], [['a','a'],['a'],['b'],[]]]
        cases.append([[str(x) for x in rng.integers(0,30,size=int(rng.integers(0,40)))] for _ in range(80)])
        for sentences in cases:
            values=[]
            for a,b in itertools.combinations(map(set,sentences),2):
                values.append(len(a&b)/len(a|b) if a|b else None)
            expected=summary(values,'DIS03.jaccard');actual=all_sentence_overlap(sentences)
            self.assertEqual(set(expected),set(actual))
            for key,value in expected.items():
                if value is None:self.assertIsNone(actual[key])
                else:self.assertAlmostEqual(actual[key],value,places=14,msg=key)

    def test_optional_pair_export_is_complete_and_not_used_as_checkpoint(self):
        sentences=[['a','b'],['a'],['c'],[]]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pairs.csv.gz'
            result=all_sentence_overlap(sentences,p)
            with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),6);self.assertEqual(float(rows[0]['jaccard']),.5)
            self.assertEqual(result['DIS03.jaccard.valid_n'],6)
            self.assertEqual({x.name for x in Path(d).iterdir()},{p.name})
            with self.assertRaises(InterruptedError):all_sentence_overlap(sentences,Path(d)/'cancelled.csv.gz',lambda:True)
            self.assertFalse((Path(d)/'cancelled.csv.gz.partial').exists())
            self.assertFalse((Path(d)/'cancelled.csv.gz').exists())

    def test_many_identical_sentences_are_counted_exactly_without_pair_rows(self):
        result=all_sentence_overlap([['one','two']]*500)
        self.assertEqual(result['DIS03.jaccard.valid_n'],500*499//2)
        self.assertEqual(result['DIS03.jaccard.mean'],1)
        self.assertEqual(result['DIS03.jaccard.sd_population'],0)


class CompactStorageTests(unittest.TestCase):
    def test_compressed_tables_fit_and_verify_like_plain_tables(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';source.mkdir()
            p=source/'observations/points.csv'
            csv_write(p,[dict(x=i,y=2*i+1) for i in range(1,10)])
            raw=p.read_bytes()
            atomic_json(source/'analysis_tables.json',dict(schema_version=1,tables=[dict(id='points',path='observations/points.csv')]))
            compress_outputs(source,threshold=1)
            path,entry=table_path(source,'points')
            self.assertEqual(path.name,'points.csv.gz')
            with gzip.open(path,'rb') as f:self.assertEqual(f.read(),raw)
            self.assertEqual(len(read_table(path)[1]),9)
            self.assertEqual(table_path(path)[0],path)
            report=fit(dict(source=str(source),table='points',output=str(root/'fit'),x='x',y='y',kind='relation',models=['linear']))
            self.assertEqual(report['state'],'complete')
            rows=read_table(root/'fit/fit_results.csv')[1]
            parameters=json.loads(rows[0]['parameters'])
            self.assertAlmostEqual(parameters['slope'],2);self.assertAlmostEqual(parameters['intercept'],1)

    def test_compressed_reference_remains_usable(self):
        recs=[dict(id='a',meta={},keys=['a','b'],sentences=[['a','b']],details={})]
        options=dict(token_unit='wordform');choices(options,recs)
        reference=freeze_reference(Corpus(recs,options,selected_features=[]),options,'test')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);atomic_json(root/'run.json',{'state':'complete'})
            atomic_json(root/'reference.json.gz',reference,compact=True)
            loaded,info=load_reference(dict(options,reference_mode='external',reference_path=d))
            self.assertEqual(loaded,reference);self.assertTrue(info['path'].endswith('.json.gz'))

    def test_completed_run_reuses_outputs_after_automatic_cache_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'text.txt';source.write_text('The cat sleeps. The dog runs.\n\nA bird flies.')
            job=dict(inputs=[str(source)],output=str(root/'out'),features=['LEN09','DIS02','DIS03'])
            report=run(job)
            self.assertEqual(report['state'],'complete')
            self.assertFalse((root/'out/.checkpoint').exists())
            self.assertNotIn('details/dis03_overlap.csv',report['outputs'])
            self.assertTrue((root/'out/tokens.csv').exists())
            with patch('spacy.load',side_effect=AssertionError('completed run must not reload NLP')):
                self.assertEqual(run(job)['signature'],report['signature'])


if __name__=='__main__':unittest.main()
