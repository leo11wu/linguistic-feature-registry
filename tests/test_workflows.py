"""Measurement/analysis boundaries, reusable inputs and explicit study-unit choices."""
import csv, json, tempfile, unittest, importlib.util
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lingmetrics import resources
resources.activate()
from lingmetrics.fitting import fit, relation, distribution, table_path, read_table
from lingmetrics.observations import choices, freeze_reference, load_reference
from lingmetrics.corpus import Corpus
from lingmetrics.stats import graph_measures
from lingmetrics.runner import run


def records(*sequences):
    return [dict(id=str(i),meta={},keys=list(s),sentences=[list(s)],token_sentences=[list(s)],pos_sentences=[[(w,'NOUN') for w in s]],details={}) for i,s in enumerate(sequences)]


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


class FitTests(unittest.TestCase):
    def test_linear_reference_solution_and_weighted_objective(self):
        x=np.array([1.,2.,3.,4.]);y=2+3*x
        info,predicted=relation('linear',x,y,np.ones(4))
        self.assertAlmostEqual(info['parameters']['intercept'],2);self.assertAlmostEqual(info['parameters']['slope'],3)
        np.testing.assert_allclose(predicted,y,atol=1e-12)
        x=np.array([0.,0.,1.,1.]);y=np.array([0.,10.,0.,10.]);w=np.array([9.,1.,1.,9.])
        info,_=relation('linear',x,y,w)
        self.assertAlmostEqual(info['parameters']['intercept'],1);self.assertAlmostEqual(info['parameters']['slope'],8)

    def test_log_space_power_has_separate_definition(self):
        x=np.arange(1.,11.);y=3*x**1.4
        info,predicted=relation('power_log',x,y,np.ones(len(x)))
        self.assertAlmostEqual(info['parameters']['a'],3);self.assertAlmostEqual(info['parameters']['b'],1.4)
        self.assertEqual(info['method'],'weighted_log_log_least_squares');np.testing.assert_allclose(predicted,y)

    def test_lnre_interface_preserves_frequency_spectrum(self):
        with patch('lingmetrics.managed_r.fit',return_value={'parameters':{'alpha':.4}}) as mock:
            info,predicted=distribution('lnre_fzm',np.array([1.,2.,3.]),np.array([100.,30.,10.]))
        mock.assert_called_once_with([{'frequency':1,'types':100},{'frequency':2,'types':30},{'frequency':3,'types':10}],'fzm')
        self.assertEqual(info['parameters'],{'alpha':.4});self.assertIsNone(predicted)

    @unittest.skipUnless(importlib.util.find_spec('scipy'),'optional SciPy fitting dependency')
    def test_nonlinear_known_zipf_and_distribution_frequency_weights(self):
        x=np.arange(1.,41.);y=100*x**(-1.2)
        info,predicted=relation('zipf',x,y,np.ones(len(x)))
        self.assertAlmostEqual(info['parameters']['a'],1.2,places=6);self.assertAlmostEqual(info['parameters']['C'],100,places=5)
        counts=np.array([1.,2.,1.]);values=np.array([0.,1.,2.])
        info,_=distribution('poisson',values,counts)
        self.assertEqual(info['parameters']['lambda'],1);self.assertEqual(info['sample_n'],4)
        self.assertAlmostEqual(info['log_likelihood'],-4-np.log(2))
        raw,_=distribution('poisson',np.array([0.,1.,1.,2.]),np.ones(4))
        self.assertAlmostEqual(info['aic'],raw['aic'])
        with self.assertRaisesRegex(ValueError,'整数'):distribution('poisson',values,np.array([1.,1.5,1.]))

    @unittest.skipUnless(importlib.util.find_spec('scipy'),'optional SciPy fitting dependency')
    def test_reuse_grouping_filter_failures_and_source_immutability(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'observations.csv'
            source.write_text('group,x,y\na,1,5\na,2,8\na,3,11\na,4,14\nb,1,1\nb,2,1\nb,3,1\nb,4,1\na,,9\na,5,-1\n')
            original=source.read_bytes()
            job=dict(source=str(source),output=str(root/'fit'),kind='relation',x='x',y='y',group='group',models=['linear','power'],min_y=0)
            manifest=fit(job);rows=csv_rows(root/'fit/fit_results.csv')
            self.assertEqual(manifest['selected_rows'],8);self.assertEqual(manifest['excluded'],{'missing_or_non_numeric':1,'outside_y_range':1})
            self.assertEqual(manifest['state'],'complete');self.assertEqual(len(rows),4)
            self.assertEqual({int(r['n_rows']) for r in rows},{4});self.assertEqual(source.read_bytes(),original)
            self.assertTrue((root/'fit/report.html').exists());self.assertEqual(len(csv_rows(root/'fit/selected_observations.csv')),8)
            with self.assertRaisesRegex(ValueError,'已有文件'):fit(job)
            job.update(output=str(root/'other'),models=['linear','poisson'])
            with self.assertRaisesRegex(ValueError,'不匹配'):fit(job)
            self.assertEqual(source.read_bytes(),original)

    @unittest.skipUnless(importlib.util.find_spec('scipy'),'optional SciPy fitting dependency')
    def test_domain_failure_does_not_change_other_model_sample(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'x.csv';p.write_text('x,y\n0,2\n1,5\n2,8\n3,11\n')
            report=fit(dict(source=str(p),output=str(root/'out'),kind='relation',x='x',y='y',models=['linear','power']))
            rows=csv_rows(root/'out/fit_results.csv')
            self.assertEqual(report['state'],'partial');self.assertEqual([r['status'] for r in rows],['computed','error'])
            self.assertEqual([r['n_rows'] for r in rows],['4','4'])

    def test_manifest_table_hash_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'x.csv';p.write_text('x,y\n1,2\n')
            manifest=root/'analysis_tables.json';manifest.write_text(json.dumps(dict(schema_version=1,tables=[dict(id='x',path='x.csv',sha256='wrong')])))
            with self.assertRaisesRegex(ValueError,'变化'):table_path(root,'x')
            manifest.write_text(json.dumps(dict(schema_version=1,tables=[dict(id='x',path='../outside.csv')])))
            with self.assertRaisesRegex(ValueError,'路径'):table_path(root,'x')
            p.write_text('x,x\n1,2\n')
            with self.assertRaisesRegex(ValueError,'列名'):read_table(p)


class ChoiceTests(unittest.TestCase):
    def test_frozen_reference_is_independent_of_target_batch(self):
        options=dict(token_unit='wordform');ref_records=records(['the','cat','the','cat'],['a','dog'])
        choices(options,ref_records);reference=freeze_reference(Corpus(ref_records,options,selected_features=[]),options,'test')
        target=records(['the','cat']);one=Corpus(target,options,reference=reference)
        two=Corpus(target+records(['unseen','words','unseen','words']),options,reference=reference)
        self.assertEqual(one.measure('MWE01',target[0]),two.measure('MWE01',target[0]))
        self.assertEqual(one.measure('MWE01',target[0])['MWE01.order2_reference_count.mean'],2)
        self.assertIn('INF07.js_bits_vs_external_reference',one.measure('INF07',target[0]))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'reference.json').write_text(json.dumps(reference))
            (root/'run.json').write_text('{"state":"complete"}')
            options.update(reference_mode='external',reference_path=d,token_unit='lemma')
            with self.assertRaisesRegex(ValueError,'口径'):load_reference(options)

    def test_graph_direction_window_and_unordered_betweenness(self):
        recs=records(['a','b','c'])
        adjacent=Corpus(recs,dict(network_edge='adjacent',network_directed=True));adjacent.measure('NET01',recs[0])
        window=Corpus(recs,dict(network_edge='window',network_window=2,network_directed=False));window.measure('NET01',recs[0])
        self.assertEqual(len(adjacent.details['network_edges']),2);self.assertEqual(len(window.details['network_edges']),3)
        rows,values=graph_measures([('a','b'),('b','c')],{'a','b','c'},directed=False)
        self.assertEqual(next(r for r in rows if r['word']=='b')['betweenness'],1)
        self.assertAlmostEqual(values['NET04.global_efficiency'],5/6)

    def test_missing_metadata_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'元数据'):choices(dict(corpus_group_column='group'),records(['cat']))
        with self.assertRaisesRegex(ValueError,'参照'):choices(dict(reference_mode='external'),records(['cat']))


class WorkflowTests(unittest.TestCase):
    def test_extraction_keeps_units_without_fitting_and_pair_rows_are_unique(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'texts.csv'
            source.write_text('doc_id,text,group,pair\na,The dog slept. The cat ran.,A,p\nb,A dog ran. A cat slept.,A,p\nc,The birds fly.,B,\n')
            job=dict(inputs=[str(source)],output=str(root/'extract'),features=['LEN01','MWE01','STY07','NET01'],
                     options=dict(corpus_group_column='group',pair_column='pair',network_edge='window',network_window=2,network_directed=False))
            lex={'the':{'category':'article'},'a':{'category':'article'}}
            with patch.object(resources,'available',return_value=True),patch.object(resources,'table',return_value=lex),patch('lingmetrics.fitting.relation',side_effect=AssertionError('fitting during extraction')):
                report=run(job)
            self.assertEqual(report['state'],'complete')
            out=root/'extract';features=csv_rows(out/'features.csv')
            self.assertFalse(any(k.startswith(('QL01.','QL06.','STY07.')) for row in features for k in row))
            pairs=csv_rows(out/'pair_features.csv');self.assertEqual(len(pairs),1)
            self.assertEqual({pairs[0]['doc_id_left'],pairs[0]['doc_id_right']},{'a','b'})
            self.assertEqual(len(csv_rows(out/'pair_status.csv')),2)
            sentences=csv_rows(out/'observations/sentence_measures.csv');self.assertEqual(len(sentences),5)
            self.assertEqual(float(sentences[0]['sentence_words']),3);self.assertAlmostEqual(float(sentences[0]['mean_word_letters']),11/3)
            ranks=csv_rows(out/'observations/rank_frequency.csv');self.assertEqual({r['corpus_id'] for r in ranks},{'A','B'})
            self.assertTrue((out/'reference.json').is_file());self.assertFalse((out/'corpus/curve_fits.csv').exists())
            manifest=json.loads((out/'analysis_tables.json').read_text());self.assertEqual(manifest['choices']['pair_column'],'pair')
            matrix=(out/'features.csv').read_bytes()
            fitted=fit(dict(source=str(out),table='rank_frequency',output=str(root/'fit'),kind='relation',x='rank',y='frequency',group='corpus_id',models=['linear']))
            self.assertEqual(fitted['state'],'complete');self.assertEqual((out/'features.csv').read_bytes(),matrix)

    def test_old_fitting_ids_cannot_silently_fit_in_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.txt';p.write_text('The dog slept.')
            with self.assertRaisesRegex(ValueError,'拟合页'):run(dict(inputs=[str(p)],output=str(Path(d)/'out'),features=['QL01']))


if __name__=='__main__':unittest.main()
