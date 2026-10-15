"""Statistical reference checks, support accounting, and report delivery invariants."""
import csv
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lingmetrics import resources
resources.activate()
from lingmetrics.fitting import relation, distribution, fit
from lingmetrics.fit_diagnostics import compare_results, discrete_diagnostics
from lingmetrics.fit_report import svg_plot


@unittest.skipUnless(importlib.util.find_spec('scipy'),'optional SciPy fitting dependency')
class DiagnosticTests(unittest.TestCase):
    def test_linear_uncertainty_and_gaussian_likelihood_reference(self):
        from scipy import stats
        x=np.arange(1.,11.);y=np.array([3,5,6,9,11,12,16,16,19,23.]);w=np.ones(10)
        info,pred=relation('linear',x,y,w)
        reference=stats.linregress(x,y)
        self.assertAlmostEqual(info['standard_errors']['slope'],reference.stderr)
        self.assertEqual(info['residual_df'],8)
        lo,hi=info['confidence_intervals']['slope']
        self.assertAlmostEqual(lo,reference.slope-stats.t.ppf(.975,8)*reference.stderr)
        self.assertAlmostEqual(hi,reference.slope+stats.t.ppf(.975,8)*reference.stderr)
        self.assertAlmostEqual(info['parameter_tests']['slope']['p_value'],reference.pvalue)
        self.assertAlmostEqual(info['f_statistic'],(reference.slope/reference.stderr)**2)
        self.assertAlmostEqual(info['f_p_value'],reference.pvalue)
        ll=float(stats.norm.logpdf(y,loc=pred,scale=np.sqrt(np.mean((y-pred)**2))).sum())
        self.assertAlmostEqual(info['log_likelihood'],ll)
        self.assertAlmostEqual(info['aic'],6-2*ll)
        self.assertEqual(info['likelihood_parameter_count'],3)
        self.assertAlmostEqual(info['mae'],np.abs(y-pred).mean())

    def test_precision_weight_rescaling_preserves_likelihood_and_ci(self):
        x=np.arange(1.,9.);y=np.array([2,4,4,7,8,7,12,11.]);w=np.arange(1.,9.)
        one,_=relation('linear',x,y,w);two,_=relation('linear',x,y,w*17)
        for key in ('rmse','mae','aic','bic','r_squared'):self.assertAlmostEqual(one[key],two[key])
        np.testing.assert_allclose(one['covariance'],two['covariance'])
        self.assertEqual(one['sample_n'],8)

    def test_log_power_likelihood_has_original_response_jacobian(self):
        from scipy import stats
        x=np.arange(1.,15.);y=7*x**-.8*np.exp(np.sin(x)*.15);w=np.ones(len(x))
        info,pred=relation('power_log',x,y,w)
        sigma=np.sqrt(np.mean((np.log(y)-np.log(pred))**2))
        ll=float(stats.lognorm.logpdf(y,s=sigma,scale=pred).sum())
        self.assertAlmostEqual(info['log_likelihood'],ll)
        self.assertGreater(info['log_space_r_squared'],.9)
        self.assertNotAlmostEqual(info['log_space_rmse'],info['rmse'])
        self.assertTrue(0<info['confidence_intervals']['a'][0]<info['parameters']['a']<info['confidence_intervals']['a'][1])
        self.assertIn('中位数',info['prediction_interpretation'])

    def test_all_nonlinear_models_report_common_statistics(self):
        x=np.arange(1.,51.);w=np.ones(len(x))
        cases={'power':3*x**-.4,'exponential':3*np.exp(-.02*x),
               'zipf':100*x**-1.2,'zipf_mandelbrot':150*(x+2)**-1.1,
               'heaps':5*x**.6,'menzerath_altmann':7*x**-.3*np.exp(-.02*x)}
        for model,y in cases.items():
            with self.subTest(model=model):
                info,pred=relation(model,x,y*(1+.002*np.sin(x)),w)
                self.assertTrue(info['converged'])
                for key in ('sse','mae','adjusted_r_squared','residual_df','aic','bic','aicc','standard_errors','covariance'):
                    self.assertIn(key,info)
                self.assertGreater(info['r_squared'],.99)

    def test_pearson_interval_and_spearman_small_sample_warning(self):
        from scipy import stats
        x=np.arange(1.,11.);y=np.array([1,4,3,4,7,8,7,9,9,11.]);w=np.ones(10)
        pearson,_=relation('pearson',x,y,w)
        reference=stats.pearsonr(x,y).confidence_interval()
        np.testing.assert_allclose(pearson['confidence_intervals']['r'],reference)
        spearman,_=relation('spearman',x,y,w)
        self.assertEqual(spearman['sample_n'],10);self.assertGreater(spearman['tied_y_rows'],0)
        self.assertIn('n≤500',spearman['warnings'][0]);self.assertIsNone(spearman['confidence_intervals'])

    def test_poisson_gof_includes_unobserved_zero_gaps_and_tail(self):
        from scipy import stats
        values=np.array([1.,2.,4.,6.]);counts=np.array([100.,80.,30.,10.])
        info,_=distribution('poisson',values,counts)
        n=counts.sum();lam=float(np.average(values,weights=counts));support=np.arange(0,7)
        actual=np.array([0,100,80,0,30,0,10,0.]);expected=np.append(n*stats.poisson.pmf(support,lam),n*stats.poisson.sf(6,lam))
        reference=float(np.sum((actual-expected)**2/expected))
        self.assertAlmostEqual(info['unpooled_chi_squared'],reference)
        bins=info['gof_bin_details']
        self.assertAlmostEqual(sum(b['observed'] for b in bins),n)
        self.assertAlmostEqual(sum(b['expected'] for b in bins),n)
        self.assertEqual(bins[0]['lower'],0);self.assertIsNone(bins[-1]['upper'])
        self.assertGreaterEqual(info['gof_minimum_expected'],5)
        self.assertAlmostEqual(info['discrepancy_coefficient'],info['chi_squared']/n)
        self.assertEqual(info['chi_squared_df'],len(bins)-2)
        self.assertGreater(info['total_variation_distance'],0)
        self.assertNotIn('ks_p_value',info)

    def test_all_ordinary_distributions_have_domain_respecting_intervals(self):
        values=np.arange(1.,13.);counts=np.array([80,90,70,55,43,32,23,16,11,8,6,4.])
        for model in ('poisson','zero_truncated_poisson','geometric','negative_binomial'):
            with self.subTest(model=model):
                info,_=distribution(model,values,counts)
                self.assertIn('goodness_of_fit_status',info)
                self.assertEqual(info['sample_n'],int(counts.sum()))
                for name,interval in (info['confidence_intervals'] or {}).items():
                    self.assertGreater(interval[0],0)
                    if name=='p':self.assertLess(interval[1],1)

    def test_repeated_values_and_frequency_compression_have_identical_gof(self):
        one,_=distribution('poisson',np.array([0.,1.,2.]),np.array([20.,30.,10.]))
        two,_=distribution('poisson',np.array([2.,1.,1.,0.]),np.array([10.,10.,20.,20.]))
        for key in ('chi_squared','unpooled_chi_squared','discrete_cdf_distance','aic'):
            self.assertAlmostEqual(one[key],two[key])

    def test_boundary_and_insufficient_cells_do_not_fabricate_p(self):
        info,_=distribution('poisson',np.array([0.]),np.array([20.]))
        self.assertIsNone(info['goodness_of_fit_p_value']);self.assertIsNone(info['confidence_intervals'])
        info,_=distribution('zero_truncated_poisson',np.array([1.]),np.array([20.]))
        self.assertIsNone(info['goodness_of_fit_p_value']);self.assertIsNone(info['confidence_intervals'])
        info,_=distribution('geometric',np.array([1.,2.]),np.array([2.,1.]))
        self.assertIsNone(info['goodness_of_fit_p_value'])

    def test_aic_comparison_does_not_mix_incompatible_response_measures(self):
        rows=[dict(group='a',status='computed',comparison_basis='continuous_original_response',aic=10.,bic=12.),
              dict(group='a',status='computed',comparison_basis='continuous_original_response',aic=12.,bic=15.),
              dict(group='a',status='computed',comparison_basis='discrete_probability_mass',aic=0.,bic=2.)]
        compare_results(rows)
        self.assertEqual(rows[0]['delta_aic'],0);self.assertEqual(rows[1]['delta_aic'],2)
        self.assertAlmostEqual(rows[0]['akaike_weight']+rows[1]['akaike_weight'],1)
        self.assertNotIn('delta_aic',rows[2])

    def test_lnre_forwards_native_multivariate_gof_without_inventing_aic(self):
        result=dict(parameters={'alpha':.5,'B':.01},goodness_of_fit={'chi_squared':3.,'df':5,'p_value':.7},
                    expected_spectrum=[dict(frequency=1,expected_types=90.),dict(frequency=2,expected_types=35.),dict(frequency=3,expected_types=12.)])
        with patch('lingmetrics.managed_r.fit',return_value=result):
            info,pred=distribution('lnre_zm',np.array([1.,2.,3.]),np.array([100.,30.,10.]))
        self.assertEqual(info['lnre_goodness_of_fit']['df'],5);self.assertNotIn('aic',info)
        np.testing.assert_allclose(pred,[90,35,12]);self.assertEqual(info['sample_n'],190)

    def test_saved_report_exposes_statistics_parameters_and_residuals(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'x.csv'
            source.write_text('rank,frequency\n1,100\n2,46\n3,31\n4,24\n5,20\n6,15\n')
            raw=source.read_bytes()
            manifest=fit(dict(source=str(source),output=str(root/'fit'),kind='relation',x='rank',y='frequency',models=['zipf','power_log','pearson']))
            self.assertEqual(manifest['state'],'complete');self.assertEqual(source.read_bytes(),raw)
            data=json.loads((root/'fit/fit_results.json').read_text())
            self.assertEqual(len(data['results']),3)
            page=(root/'fit/report.html').read_text()
            for label in ('95%区间下限','双对数视图','原尺度残差','Akaike权重','Fisher_z'):self.assertIn(label,page)
            self.assertNotIn('<script',page)
            with (root/'fit/fit_predictions.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),18)
            self.assertTrue(all(r['predicted']=='' for r in rows if r['model']=='pearson'))

    def test_lnre_undefined_spectrum_elements_stay_missing_without_losing_fit(self):
        result=dict(parameters={'alpha':.5,'B':.01},goodness_of_fit={'chi_squared':3.,'df':5,'p_value':.7},
                    expected_spectrum=[dict(frequency=1,expected_types=90.),dict(frequency=2,expected_types=None),dict(frequency=3,expected_types=12.)])
        with patch('lingmetrics.managed_r.fit',return_value=result):
            info,pred=distribution('lnre_zm',np.array([1.,2.,3.]),np.array([100.,30.,10.]))
        self.assertTrue(np.isnan(pred[1]));self.assertIn('留空',info['warnings'][0])

    def test_plot_retains_dense_head_and_escapes_labels(self):
        points=[dict(x=float(i),observed=1000/i,predicted=950/i,residual=50/i) for i in range(1,10001)]
        chart=svg_plot(points,'<unsafe>','rank','count',log=True)
        self.assertNotIn('aria-label="<unsafe>',chart)
        # More than 64 observations appear in the head; the old 400-point plot jumped from rank 1 to rank 26 here.
        self.assertGreater(chart.count('<circle'),1000)
        self.assertIn('对数坐标',chart)
        small=svg_plot([dict(p,x=p['x']*.0001) for p in points],'small means','x','y',log=True)
        self.assertIn('0.0001',small)


if __name__=='__main__':unittest.main()
