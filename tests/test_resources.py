import unittest,tempfile,json,csv
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lingmetrics import resources
from lingmetrics.util import Unavailable
from lingmetrics.core import Text
from lingmetrics.lexicons import lexical_measure
from lingmetrics.corpus import Corpus

class ResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import spacy
        cls.nlp=spacy.load('en_core_web_sm')
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.cache=patch.object(resources,'CACHE',self.base/'cache');self.cache.start();resources.table.cache_clear();resources.configuration.cache_clear()
    def tearDown(self):
        resources.table.cache_clear();resources.configuration.cache_clear();self.cache.stop();self.temp.cleanup()
    def table(self,name,body):
        p=self.base/(name+'.csv');p.write_text(body);resources.import_resource(name,p)
    def test_wordform_coverage_token_type_separate(self):
        self.table('concreteness','Word,Conc.M\ndog,5\ncat,4\n')
        t=Text('The dog chased the dog and the cat.',self.nlp)
        values=lexical_measure('SEM02',t)
        self.assertAlmostEqual(values['SEM02.concreteness.token.mean'],14/3)
        self.assertEqual(values['SEM02.concreteness.type.mean'],4.5)
        self.assertEqual(values['SEM02.eligible_n'],4)
        self.assertEqual(values['SEM02.token_coverage'],.75)
    def test_missing_does_not_become_zero(self):
        self.table('aoa','word,aoa\nunknown,5\n')
        with self.assertRaises(Unavailable):lexical_measure('SEM01',Text('The dog slept.',self.nlp))
    def test_duplicate_conflicting_values(self):
        self.table('concreteness','word,concreteness\ndog,5\ndog,4\n')
        with self.assertRaisesRegex(Unavailable,'重复'):resources.table('concreteness')
    def test_mrc_zero_is_missing(self):
        self.table('mrc','word,familiarity,imageability\ndog,0,500\n')
        row=resources.table('mrc')['dog'];self.assertNotIn('familiarity',row);self.assertEqual(row['imageability'],500)
    def test_invalid_resource_nan(self):
        with self.assertRaises(ValueError):self.table('aoa','word,aoa\ndog,nan\n')
    def test_phrase_coverage_union(self):
        self.table('academic','word,category\nin other words,academic\nother words,academic\n')
        t=Text('In other words, we agree.',self.nlp)
        value=lexical_measure('FREQ08',t)['FREQ08.all_covered_token_rate']
        self.assertAlmostEqual(value,3/5)
    def test_corpus_association_uses_same_event_universe(self):
        r=dict(id='a',meta={},text='a b a b',keys=['a','b','a','b'],sentences=[['a','b','a','b']])
        c=Corpus([r]);s=c.pair_stats[('a','b')]
        self.assertEqual(s['event_total'],3);self.assertEqual(s['left_total'],2);self.assertEqual(s['right_total'],2)
        self.assertEqual(s['delta_p_y_given_x'],1.)

if __name__=='__main__':unittest.main()
