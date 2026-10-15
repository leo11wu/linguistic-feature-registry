import unittest, math, tempfile, json, csv, os
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lingmetrics.stats import diversity, association, dispersion, uid, grid_transitions, graph_measures, recurrence, finite_burstiness, mtld
from lingmetrics.syntax import tree_results
from lingmetrics.catalogue import catalogue, route, PENDING
from lingmetrics.core import Text,base_measure
from lingmetrics.util import Unavailable
from lingmetrics.runner import input_documents,result,run

class FormulaTests(unittest.TestCase):
    def test_diversity_and_short_inputs(self):
        d=diversity(['a','a','b','b'],window=2,sample=2)
        self.assertEqual(d['LD01.ttr'],.5);self.assertAlmostEqual(d['LD02.root_ttr'],1.)
        self.assertAlmostEqual(d['LD03.cttr'],2/math.sqrt(8));self.assertAlmostEqual(d['LD11.yule_k'],2500)
        self.assertAlmostEqual(d['LD12.simpson_d'],1/3);self.assertAlmostEqual(d['LD09.hdd'],5/6)
        self.assertAlmostEqual(d['LD06.msttr'],.5);self.assertAlmostEqual(d['LD07.mattr'],2/3)
        short=diversity(['a','b'])
        self.assertIsNone(short['LD07.mattr']);self.assertIsNone(short['LD09.hdd']);self.assertIsNone(mtld(['a','b']))
    def test_corrected_dp_unequal_sizes(self):
        dp,norm=dispersion([0,10],[80,20]);self.assertAlmostEqual(dp,.8);self.assertAlmostEqual(norm,1.)
        self.assertEqual(dispersion([1],[1]),(None,None))
    def test_directional_association(self):
        a=association(10,20,5,65)
        self.assertAlmostEqual(a['delta_p_y_given_x'],10/30-5/70)
        self.assertAlmostEqual(a['delta_p_x_given_y'],10/15-20/85)
        self.assertNotEqual(a['delta_p_y_given_x'],a['delta_p_x_given_y'])
        self.assertAlmostEqual(a['logdice'],14+math.log2(20/45))
        self.assertIsNone(association(0,1,1,0)['pmi'])
    def test_uid_population_and_local(self):
        u=uid([1.,3.,5.],reference=0.)
        self.assertAlmostEqual(u['INF08.within_sentence_variance'],8/3)
        self.assertEqual(u['INF08.local_squared_difference'],4.)
        self.assertAlmostEqual(u['INF08.reference_squared_deviation'],35/3)
    def test_entity_grid_keeps_absent_windows(self):
        g=grid_transitions([['S','-','O'],['-','-','-']],2)
        self.assertEqual(len(g),16);self.assertEqual(g['--'],.5);self.assertAlmostEqual(sum(g.values()),1)
        h=grid_transitions([['S','-','O'],['-','-','-']],3)
        self.assertEqual(len(h),64);self.assertEqual(h['S-O'],.5)
    def test_directed_disconnected_graph(self):
        rows,s=graph_measures([('a','b'),('b','c')],['a','b','c','d']);d={r['word']:r for r in rows}
        self.assertEqual(d['b']['betweenness'],1);self.assertEqual(d['a']['clustering'],0)
        self.assertIsNone(s['NET03.mean_geodesic_directed_all_pairs']);self.assertAlmostEqual(s['NET04.global_efficiency'],2.5/12)
    def test_recurrence_boundary(self):
        self.assertEqual(recurrence([0,3,6])['burstiness'],-1.)
        self.assertIsNone(recurrence([0,3])['burstiness']);self.assertIsNone(finite_burstiness([0,1],10))
    def test_original_tree_figure(self):
        tree='(ROOT (S (NP (PRP she)) (VP (VBD was) (NP (NP (DT a) (NN cook)) (PP (IN in) (NP (DT a) (NN school) (NN cafeteria)))))))'
        values,rows,counts=tree_results(tree)
        self.assertEqual(rows[0]['frazier_scores'],[2.5,1.,2.,0.,1.,1.,0.,0.])
        self.assertEqual(sum(rows[0]['yngve_scores']),9)
        self.assertEqual(counts['W'],8);self.assertEqual(counts['T'],1)
        self.assertAlmostEqual(values['SYN24.frazier.mean'],7.5/8)
    def test_full_catalogue_routes(self):
        rows=catalogue();self.assertEqual(len(rows),177);self.assertEqual(len(set(r['id'] for r in rows)),177)
        self.assertEqual({r['id'] for r in rows if r['state']=='method_pending'},set(PENDING))
        self.assertEqual({r['id'] for r in rows if r['scope']=='corpus'} & {'LEN01'},set())

class InputTests(unittest.TestCase):
    def test_csv_bom_quotes_empty_and_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'text.csv'
            with p.open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['doc_id','body','pair_id']);w.writeheader();w.writerows([dict(doc_id='a',body='Hello, "world".\nNew line.',pair_id='p'),dict(doc_id='b',body='',pair_id='p')])
            docs,_=input_documents(dict(inputs=[str(p)],text_column='body'))
            self.assertEqual(len(docs),2);self.assertIn('"world"',docs[0]['text']);self.assertEqual(docs[1]['text'],'')
            p.write_text('doc_id,body\na,one\na,two\n')
            with self.assertRaisesRegex(ValueError,'重复'):input_documents(dict(inputs=[str(p)],text_column='body'))
    def test_missing_reason_is_not_zero(self):
        values,status=result('SEM01',lambda:(_ for _ in ()).throw(Unavailable('资源缺失','resource_required')))
        self.assertIsNone(values['SEM01.value']);self.assertEqual(status['status'],'resource_required')

class NLPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import spacy
        cls.nlp=spacy.load('en_core_web_sm')
    def test_dependency_identity_and_passive(self):
        t=Text('The cat was chased by the dog.',self.nlp)
        m=base_measure('DEP02',t);d=base_measure('DEP01',t)['DEP01.total_length'];edges=len(t.details['dependencies'])
        self.assertAlmostEqual(m['DEP02.mdd_position'],d/edges)
        self.assertAlmostEqual(m['DEP02.mdd_intervening'],d/edges-1)
        self.assertEqual(base_measure('POS09',t)['POS09.passive_predicate_rate'],1.)
    def test_all_base_handlers(self):
        from lingmetrics.runner import calculate
        t=Text(('The dog chased the cat. The cat slept. '*30),self.nlp)
        for r in catalogue():
            if route(r['id'])=='base':
                with self.subTest(r['id']):
                    values,state=result(r['id'],lambda r=r:calculate(r['id'],t,'base'))
                    self.assertNotEqual(state['status'],'error');self.assertTrue(values)
    def test_run_and_resume_preserves_matrix(self):
        with tempfile.TemporaryDirectory(prefix='指标 ') as d:
            p=Path(d)/'输入.csv';p.write_text('doc_id,text\na,"The dog was chased by the cat."\nb,""\n',encoding='utf-8-sig')
            job=dict(inputs=[str(p)],output=str(Path(d)/'结果'),features=['LEN01','LD01','DEP02','POS09','SEM01','DEP16'],options={'seed':1729})
            a=run(job);matrix=(Path(job['output'])/'features.csv').read_bytes();b=run(job)
            self.assertEqual(a['state'],'complete');self.assertEqual(matrix,(Path(job['output'])/'features.csv').read_bytes())
            with (Path(job['output'])/'feature_status.csv').open(encoding='utf-8-sig') as f:status=list(csv.DictReader(f))
            self.assertTrue(any(r['status']=='resource_required' for r in status));self.assertTrue(any(r['status']=='method_pending' for r in status))
            job['options']['seed']=1
            with self.assertRaisesRegex(ValueError,'另一'):run(job)

    def test_paragraph_trailing_newline_and_blank_text(self):
        t=Text('One paragraph.\n\nSecond paragraph.\n',self.nlp)
        self.assertEqual(base_measure('LEN04',t)['LEN04.paragraphs'],2)
        self.assertEqual(base_measure('LEN03',Text('   ',self.nlp))['LEN03.sentences'],0)

    def test_cancel_and_resume(self):
        import lingmetrics.runner as runner
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.csv';p.write_text('doc_id,text\na,The dog slept.\nb,The cat slept.\n')
            job=dict(inputs=[str(p)],output=str(Path(d)/'output'),features=['LEN01','LD01'])
            original=runner.emit
            def event(kind,**data):
                if kind=='progress' and data.get('document_id')=='a':runner.cancel()
            with patch.object(runner,'emit',event):first=runner.run(job)
            self.assertEqual(first['state'],'cancelled')
            second=runner.run(job);self.assertEqual(second['state'],'complete')
            with (Path(job['output'])/'features.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)

    def test_unrelated_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.txt';p.write_text('Hello.')
            out=Path(d)/'output';out.mkdir();keep=out/'original.csv';keep.write_text('keep me')
            with self.assertRaisesRegex(ValueError,'其他文件'):run(dict(inputs=[str(p)],output=str(out),features=['LEN01']))
            self.assertEqual(keep.read_text(),'keep me')

if __name__=='__main__':unittest.main()
