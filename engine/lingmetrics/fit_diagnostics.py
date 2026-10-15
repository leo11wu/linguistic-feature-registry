"""Model-specific diagnostics. Precision weights are never treated as replication counts."""
import math
from collections import defaultdict
import numpy as np
from .util import clean


def information_criteria(log_likelihood, n, k):
    if not math.isfinite(log_likelihood):
        return dict(log_likelihood=None, aic=None, bic=None, aicc=None,
                    information_criteria_note='误差方差为零或似然非有限，信息准则无定义')
    aic=2*k-2*log_likelihood
    return dict(log_likelihood=float(log_likelihood), aic=float(aic),
                bic=float(k*math.log(n)-2*log_likelihood),
                aicc=float(aic+2*k*(k+1)/(n-k-1)) if n>k+1 else None,
                likelihood_parameter_count=k,
                information_criteria_note='AICc为常用小样本修正；非线性与分布模型中属近似。只比较相同观测、响应量和相容的完整似然。')


def regression_diagnostics(y, predicted, weights, p, *, log_response=False):
    n=len(y);residual=y-predicted
    rss=float(np.sum(weights*residual**2));total=float(weights.sum())
    tss=float(np.sum(weights*(y-np.average(y,weights=weights))**2));df=n-p
    out=dict(sample_n=n, parameter_count=p, residual_df=df, weight_sum=total,
             sse=rss, mse=rss/total, rmse=math.sqrt(rss/total),
             mae=float(np.average(np.abs(residual),weights=weights)),
             residual_mean=float(np.average(residual,weights=weights)),
             maximum_absolute_error=float(np.max(np.abs(residual))),
             r_squared=1-rss/tss if tss>0 else None,
             adjusted_r_squared=1-(rss/df)/(tss/(n-1)) if df>0 and tss>0 else None,
             r_squared_note='加权中心化R²；非线性模型及其调整R²仅作描述，不能视为规律检验',
             residual_standard_error=math.sqrt(rss/df) if df>0 else None,
             weight_interpretation='relative inverse-variance precision; sample_n is rows, not weight sum',
             response_scale='original', comparison_basis='continuous_original_response',
             uncertainty_assumptions='独立误差；方差与1/权重成比例；区间与p值另需误差分布假设。未处理词句、作者、累计增长点间依赖。')
    target=y;target_prediction=predicted
    if log_response:
        target=np.log(y);target_prediction=np.log(predicted)
        lr=target-target_prediction;lrss=float(np.sum(weights*lr**2))
        ltss=float(np.sum(weights*(target-np.average(target,weights=weights))**2))
        out.update(log_space_sse=lrss,log_space_mse=lrss/total,log_space_rmse=math.sqrt(lrss/total),
                   log_space_mae=float(np.average(np.abs(lr),weights=weights)),
                   log_space_r_squared=1-lrss/ltss if ltss>0 else None,
                   log_space_adjusted_r_squared=1-(lrss/df)/(ltss/(n-1)) if df>0 and ltss>0 else None,
                   log_space_residual_standard_error=math.sqrt(lrss/df) if df>0 else None,
                   fit_objective='weighted_squared_log_residuals',
                   prediction_interpretation='反变换曲线exp(E[lnY|X])是几何中心；在对数正态误差假设下为条件中位数，未作算术均值偏差校正',
                   likelihood_model='lognormal response; Gaussian ln(Y), Jacobian -sum(ln(Y)) included')
    else:
        out.update(fit_objective='weighted_squared_original_residuals',
                   likelihood_model='Gaussian response, variance=sigma²/weight; sigma² estimated by ML')
    objective_rss=float(np.sum(weights*(target-target_prediction)**2))
    # A zero-variance Gaussian maximum has no finite likelihood, even when floating-point noise remains.
    scale=max(float(np.sum(weights*target**2)),1.)
    if objective_rss<=100*np.finfo(float).eps**2*scale:
        ll=math.inf
    else:
        ll=-.5*n*(math.log(2*math.pi)+1+math.log(objective_rss/n))+.5*float(np.log(weights).sum())
        if log_response:ll-=float(np.log(y).sum())
    out.update(information_criteria(ll,n,p+1))
    return out


def parameter_uncertainty(names, estimates, covariance, *, df=None, bounds=None, nonlinear=False):
    estimates=np.asarray(estimates,dtype=float);covariance=np.asarray(covariance,dtype=float)
    valid=(covariance.shape==(len(names),len(names)) and np.all(np.isfinite(covariance))
           and np.all(np.diag(covariance)>=0))
    out=dict(confidence_level=.95, confidence_intervals=None, standard_errors=None,
             parameter_tests=None, parameter_uncertainty_status='unavailable')
    messages=[];boundary=[]
    if bounds is not None:
        for name,value,low,high in zip(names,estimates,*bounds):
            if ((math.isfinite(low) and abs(value-low)<=1e-7*max(1,abs(low))) or
                (math.isfinite(high) and abs(value-high)<=1e-7*max(1,abs(high)))):
                boundary.append(name)
        out['parameters_at_boundary']=boundary
    if not valid:
        out['parameter_uncertainty_note']='协方差非有限或不可用，不能给出可靠标准误和区间'
        return out
    errors=np.sqrt(np.diag(covariance))
    out.update(standard_errors=dict(zip(names,map(float,errors))),covariance=clean(covariance.tolist()))
    # Parameter-correlation conditioning avoids treating mere differences in parameter units as ill conditioning.
    corr=np.divide(covariance,np.outer(errors,errors),out=np.zeros_like(covariance),where=np.outer(errors,errors)>0)
    condition=float(np.linalg.cond(corr)) if np.all(errors>0) else None
    out.update(parameter_correlation_matrix=clean(corr.tolist()),parameter_correlation_condition=clean(condition))
    unstable=condition is not None and (not math.isfinite(condition) or condition>1e12)
    if boundary or unstable:
        out['parameter_uncertainty_note']='参数位于边界或参数相关矩阵接近奇异；保留协方差/标准误作诊断，常规Wald区间和参数p值不可靠，故不输出'
        out['parameter_uncertainty_status']='boundary_or_ill_conditioned'
        return out
    try:
        from scipy import stats
    except ImportError:
        out['parameter_uncertainty_note']='标准误已计算；t区间及参数p值需要可选SciPy工具'
        return out
    critical=float(stats.t.ppf(.975,df)) if df is not None else float(stats.norm.ppf(.975))
    intervals={name:[float(v-critical*s),float(v+critical*s)] for name,v,s in zip(names,estimates,errors)}
    tests={}
    for name,v,s in zip(names,estimates,errors):
        if s>0:
            statistic=float(v/s)
            p=float(2*(stats.t.sf(abs(statistic),df) if df is not None else stats.norm.sf(abs(statistic))))
            tests[name]=dict(statistic=statistic,p_value=p,p_value_display=format_p(p),null_value=0.)
        else:tests[name]=dict(statistic=None,p_value=None,reason='标准误为零，常规检验无定义')
    out.update(confidence_intervals=intervals,parameter_tests=tests,parameter_uncertainty_status='computed',
               confidence_interval_method=('local_linearization_approximate_t' if nonlinear else 'Student_t') if df is not None else 'asymptotic_Wald_normal',
               parameter_uncertainty_note='条件于所选误差模型的95%区间；非线性模型用局部线性近似，未作重抽样或依赖校正。')
    return out


def format_p(p):
    if p is None or not math.isfinite(p):return '无定义'
    return '<1e-300' if p==0 else f'{p:.4g}'


def discrete_diagnostics(values,counts,pmf,cdf,sf,k,*,boundary=False):
    """Full-support GOF, including unseen integers and the unobserved infinite tail."""
    from scipy import stats
    n=float(counts.sum());observed=dict(zip(map(int,values),map(float,counts)))
    expected=np.asarray(pmf(values))*n
    if np.any(expected<=0) or not np.all(np.isfinite(expected)):
        return dict(goodness_of_fit_status='numerically_unavailable',goodness_of_fit_note='观测类别期望频数数值下溢，保留似然；Pearson拟合优度无法可靠计算')
    omitted=max(0.,n-float(expected.sum()))
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        unpooled=float(np.sum((counts-expected)**2/expected)+omitted)
    tv=.5*(float(np.abs(counts-expected).sum())+omitted)/n
    empirical=np.cumsum(counts)/n;before=empirical-counts/n
    d=float(max(np.max(np.abs(empirical-cdf(values))),np.max(np.abs(before-cdf(values-1)))))
    # Sparse intervals retain missing internal categories without allocating 0..max(values).
    cells=[];start=0
    def mass(lo,hi):
        if hi is None:return float(sf(lo-1))
        a=float(cdf(hi));b=float(cdf(lo-1))
        return max(0.,float(sf(lo-1)-sf(hi)) if a>.5 else a-b)
    for value,count in sorted(observed.items()):
        if value>start:
            probability=mass(start,value-1)
            if probability>0:cells.append(dict(lower=start,upper=value-1,observed=0.,expected=n*probability))
        probability=float(pmf(value))
        cells.append(dict(lower=value,upper=value,observed=count,expected=n*probability))
        start=value+1
    probability=mass(start,None)
    if probability>0:cells.append(dict(lower=start,upper=None,observed=0.,expected=n*probability))
    pooled=[];current=None
    for cell in cells:
        if current is None:current=dict(cell)
        else:
            current['upper']=cell['upper'];current['observed']+=cell['observed'];current['expected']+=cell['expected']
        if current['expected']>=5:pooled.append(current);current=None
    if current is not None:
        if pooled:
            pooled[-1]['upper']=current['upper'];pooled[-1]['observed']+=current['observed'];pooled[-1]['expected']+=current['expected']
        else:pooled.append(current)
    for cell in pooled:
        o=cell['observed'];e=cell['expected']
        cell.update(pearson_residual=(o-e)/math.sqrt(e),chi_squared_contribution=(o-e)**2/e)
    chi=sum(c['chi_squared_contribution'] for c in pooled);df=len(pooled)-1-k
    valid=(df>0 and all(c['expected']>=5 for c in pooled) and not boundary)
    p=float(stats.chi2.sf(chi,df)) if valid else None
    g2=2*sum(c['observed']*math.log(c['observed']/c['expected']) for c in pooled if c['observed']>0)
    out=dict(goodness_of_fit_status='computed' if valid else 'descriptive_only',
             chi_squared=float(chi),chi_squared_df=df if df>0 else None,
             goodness_of_fit_p_value=p,goodness_of_fit_p_display=format_p(p),
             discrepancy_coefficient=float(chi/n),unpooled_chi_squared=clean(unpooled),
             unpooled_discrepancy_coefficient=clean(unpooled/n),deviance_g2=float(max(0.,g2)),
             total_variation_distance=float(tv),discrete_cdf_distance=d,
             gof_bins=len(pooled),gof_minimum_expected=min(c['expected'] for c in pooled),
             gof_bin_details=clean(pooled),
             goodness_of_fit_method='Pearson chi-square; contiguous cells pooled to expected>=5; full support and upper tail included',
             goodness_of_fit_note='χ²、df、p和C使用同一套合并类别；p为独立同分布观测下的渐近近似，参数在合并前估计。C=χ²/N；逐整数类别C另报，不能混用两者或不同合并规则。CDF距离不套用连续KS检验的p值。')
    if not valid:out['goodness_of_fit_note']+=' 类别/自由度不足或参数在边界，仅报告偏差量，p不输出。'
    return out


def discrete_uncertainty(model,values,counts,params):
    from scipy import special
    n=float(counts.sum());mean=float(np.average(values,weights=counts));boundary=False
    names=list(params);estimates=list(params.values());cov=None
    if model=='poisson':
        lam=params['lambda'];boundary=lam<=1e-7
        cov=np.array([[lam/n]])
    elif model=='geometric':
        p=params['p'];boundary=p>=1-1e-7
        cov=np.array([[p*p*(1-p)/n]])
    elif model=='zero_truncated_poisson':
        lam=params['lambda'];boundary=lam<=1e-7 or mean<=1+1e-12;norm=-math.expm1(-lam)
        information=n*(mean/lam**2-math.exp(-lam)/norm**2)
        if information>0:cov=np.array([[1/information]])
    else:
        r=params['r'];p=params['p'];boundary=p<=1e-7 or p>=1-1e-7
        information=np.array([[n*special.polygamma(1,r)-float(np.sum(counts*special.polygamma(1,values+r))),-n/p],
                              [-n/p,n*r/p**2+n*mean/(1-p)**2]])
        if np.all(np.linalg.eigvalsh(information)>0):cov=np.linalg.inv(information)
    bounds=([0 if name!='p' else 0 for name in names],[1 if name=='p' else math.inf for name in names])
    if cov is None:cov=np.full((len(names),len(names)),np.nan)
    info=parameter_uncertainty(names,estimates,cov,bounds=bounds)
    if boundary:
        info.update(confidence_intervals=None,parameter_uncertainty_status='boundary',
                    parameter_uncertainty_note='MLE位于或接近退化分布的边界，常规正态区间不适用')
    elif info.get('confidence_intervals'):
        # Transform the Wald interval rather than clipping it, so the reported interval respects the parameter domain.
        critical=1.959963984540054
        intervals={}
        for name,value in params.items():
            error=info['standard_errors'][name]
            if name=='p':
                eta=math.log(value/(1-value));se_eta=error/(value*(1-value))
                from scipy.special import expit
                intervals[name]=[float(expit(eta-critical*se_eta)),float(expit(eta+critical*se_eta))]
            else:
                se_log=error/value
                intervals[name]=clean([float(np.exp(math.log(value)-critical*se_log)),float(np.exp(math.log(value)+critical*se_log))])
        info.update(confidence_intervals=intervals,confidence_interval_method='asymptotic_Wald_on_log_or_logit_scale')
    # Test of lambda=0, p=0 or r=0 is not a regular interior test of a discrete distribution.
    info.pop('parameter_tests',None)
    info['parameter_test_note']='分布参数的零值常在参数空间边界，不自动给出常规零值Wald检验'
    return info,boundary


def compare_results(results):
    groups=defaultdict(list)
    for row in results:
        if row.get('status')=='computed' and row.get('comparison_basis'):
            groups[(row['group'],row['comparison_basis'])].append(row)
    for (_,basis),rows in groups.items():
        for criterion in ('aic','bic','aicc'):
            eligible=[r for r in rows if isinstance(r.get(criterion),(int,float)) and math.isfinite(r[criterion])]
            if len(eligible)<2:continue
            lowest=min(r[criterion] for r in eligible)
            denominator=sum(math.exp(-.5*(r[criterion]-lowest)) for r in eligible)
            for r in eligible:
                r['delta_'+criterion]=r[criterion]-lowest
                if criterion=='aic':r['akaike_weight']=math.exp(-.5*(r[criterion]-lowest))/denominator
                r['comparison_model_count_'+criterion]=len(eligible)
                r['comparison_note']='同组、同一纳入观测与响应量的相容似然比较；权重仅针对本次候选集，不是模型为真的概率。'
    return results
