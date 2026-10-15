"""Offline tables and axis-labelled model/residual plots for the fitting workflow."""
import html
import json
import math
import numpy as np
from .util import clean
from .fit_diagnostics import format_p


def number(value):
    if value is None:return '—'
    if isinstance(value,bool):return '是' if value else '否'
    if isinstance(value,(int,float)):
        if not math.isfinite(value):return '—'
        return f'{value:.6g}'
    return str(value)


def table(headers,rows):
    esc=lambda x:html.escape(number(x))
    return '<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def overview(results):
    def value(row,key):
        if key=='sample_n':return row.get(key,row.get('n_rows'))
        if key=='correlation':return row.get('parameters',{}).get('r') if row.get('model') in {'pearson','spearman'} else None
        native={'chi_squared':'chi_squared','chi_squared_df':'df','goodness_of_fit_p_display':'p_value_display'}
        return row.get(key,row.get('lnre_goodness_of_fit',{}).get(native.get(key)))
    base=[('group','组'),('model_name','模型'),('status','状态'),('sample_n','n')]
    optional=[('correlation','相关系数'),('p_value_display','相关 p'),('r_squared','R² 原尺度'),
              ('log_space_r_squared','R² 对数'),('rmse','RMSE 原尺度'),('mae','MAE 原尺度'),
              ('chi_squared','χ²'),('chi_squared_df','df'),('goodness_of_fit_p_display','拟合优度 p'),
              ('discrepancy_coefficient','C（合并后）'),('aic','AIC'),('delta_aic','ΔAIC'),('akaike_weight','Akaike权重')]
    columns=base+[(key,label) for key,label in optional if any(value(r,key) is not None for r in results)]
    return table([label for _,label in columns],[[value(r,key) for key,_ in columns] for r in results])


STAT_LABELS=[('sample_n','样本量 n'),('n_rows','纳入表行数'),('observed_categories','观测类别数'),
 ('parameter_count','模型参数数'),('residual_df','残差自由度'),('sse','加权误差平方和 SSE（原尺度）'),
 ('rmse','加权RMSE（原尺度）'),('mae','加权MAE（原尺度）'),('r_squared','R²（原尺度）'),
 ('adjusted_r_squared','调整R²（原尺度；非线性仅描述）'),('residual_standard_error','残差标准误 sqrt(SSE/df)'),
 ('f_statistic','线性模型整体F'),('f_df_model','F分子自由度'),('f_df_residual','F分母自由度'),('f_p_value_display','整体F检验 p'),
 ('residual_mean','加权平均残差'),('maximum_absolute_error','最大绝对残差'),
 ('log_space_sse','SSE（ln响应）'),('log_space_rmse','RMSE（ln响应）'),('log_space_mae','MAE（ln响应）'),
 ('log_space_r_squared','R²（ln响应）'),('log_space_adjusted_r_squared','调整R²（ln响应）'),
 ('log_space_f_statistic','ln响应线性模型整体F'),('log_space_f_p_value_display','ln响应整体F检验 p'),
 ('observed_mean','观测均值'),('observed_variance','观测总体方差'),('fitted_mean','模型均值'),('fitted_variance','模型方差'),
 ('chi_squared','Pearson χ²（合并后）'),('chi_squared_df','χ²自由度'),('goodness_of_fit_p_display','拟合优度 p（近似）'),
 ('discrepancy_coefficient','C=χ²/N（合并后）'),('unpooled_discrepancy_coefficient','C（逐整数类别；仅描述）'),
 ('deviance_g2','似然比偏差 G²（合并后；描述）'),('total_variation_distance','总变差距离 TV'),
 ('discrete_cdf_distance','离散CDF最大距离 D（无连续KS p值）'),('gof_bins','合并后类别数'),('gof_minimum_expected','最小期望频数'),
 ('log_likelihood','完整对数似然'),('likelihood_parameter_count','似然参数数（回归含误差方差）'),
 ('aic','AIC'),('aicc','AICc（近似小样本修正）'),('bic','BIC'),('delta_aic','ΔAIC'),('delta_bic','ΔBIC'),
 ('delta_aicc','ΔAICc'),('akaike_weight','Akaike权重（本次候选集）'),('p_value_display','相关检验 p'),
 ('unique_x','不同X值数'),('unique_y','不同Y值数'),('tied_x_rows','X重复行数（n−不同值数）'),
 ('tied_y_rows','Y重复行数（n−不同值数）'),('parameter_correlation_condition','参数相关矩阵条件数'),
 ('parameters_at_boundary','位于边界的参数'),('converged','优化器收敛'),('function_evaluations','函数评估次数')]


def parameter_table(row):
    params=row.get('parameters',{});errors=row.get('standard_errors') or {};intervals=row.get('confidence_intervals') or {}
    tests=row.get('parameter_tests') or {}
    headers=['参数','估计值','标准误','95%区间下限','95%区间上限']+(['零假设值','参数检验 p'] if tests else [])
    return table(headers,[[name,value,errors.get(name),*(intervals.get(name) or [None,None])]+
                          ([tests.get(name,{}).get('null_value'),tests.get(name,{}).get('p_value_display')] if tests else []) for name,value in params.items()])


def svg_plot(points,title,xlabel,ylabel,*,log=False,residual=False,curve=True):
    usable=[];dropped=0
    for p in points:
        y=p.get('residual') if residual else p.get('observed');prediction=p.get('predicted')
        if y is None or not math.isfinite(y) or not math.isfinite(p['x']):continue
        if log and (p['x']<=0 or y<=0 or (curve and prediction is not None and prediction<=0)):
            dropped+=1;continue
        usable.append(p)
    if not usable:return '<p>没有可用于该坐标的观测。</p>'
    usable.sort(key=lambda p:p['x']);all_points=usable
    # Preserve all first 64 ranks; use both index and logarithmic coverage for the rest.
    if len(usable)>1600:
        xs=np.array([p['x'] for p in usable]);chosen=set(range(min(64,len(usable))))
        chosen.update(np.linspace(0,len(usable)-1,1000,dtype=int).tolist())
        if xs.min()>0:
            chosen.update(np.minimum(np.searchsorted(xs,np.geomspace(xs.min(),xs.max(),500)),len(xs)-1).tolist())
        usable=[usable[i] for i in sorted(chosen)]
    transform=lambda v:math.log10(v) if log else v
    xs=[transform(p['x']) for p in all_points]
    ys=[transform(p['residual'] if residual else p['observed']) for p in all_points]
    if curve and not residual:ys.extend(transform(p['predicted']) for p in all_points if p.get('predicted') is not None)
    if residual:ys.append(0.)
    xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
    if ymin==ymax:ymin-=.5;ymax+=.5
    if xmin==xmax:xmin-=.5;xmax+=.5
    xp=lambda v:82+550*(v-xmin)/(xmax-xmin)
    yp=lambda v:270-225*(v-ymin)/(ymax-ymin)
    shapes=[]
    xticks=np.arange(math.ceil(xmin),math.floor(xmax)+1) if log else np.linspace(xmin,xmax,5)
    yticks=np.arange(math.ceil(ymin),math.floor(ymax)+1) if log else np.linspace(ymin,ymax,5)
    if len(xticks)<2:xticks=np.linspace(xmin,xmax,4)
    if len(yticks)<2:yticks=np.linspace(ymin,ymax,4)
    for tx in xticks:
        labelx=10.**tx if log else tx
        shapes.append(f'<path d="M{xp(tx):.2f} 45V270" stroke="#e5e7eb" fill="none"/><text x="{xp(tx):.2f}" y="290" text-anchor="middle">{labelx:.3g}</text>')
    for ty in yticks:
        labely=10.**ty if log else ty
        shapes.append(f'<path d="M82 {yp(ty):.2f}H632" stroke="#e5e7eb" fill="none"/><text x="74" y="{yp(ty)+4:.2f}" text-anchor="end">{labely:.3g}</text>')
    if residual:shapes.append(f'<path d="M82 {yp(0):.2f}H632" stroke="#42638b" stroke-dasharray="4 3"/>')
    shapes.extend(f'<circle cx="{xp(transform(p["x"])):.2f}" cy="{yp(transform(p["residual"] if residual else p["observed"])):.2f}" r="2" fill="#66788b" opacity=".5"/>' for p in usable)
    if curve and not residual:
        line=' '.join(f'{xp(transform(p["x"])):.2f},{yp(transform(p["predicted"])):.2f}' for p in usable if p.get('predicted') is not None)
        if line:shapes.append(f'<polyline points="{line}" fill="none" stroke="#1256a0" stroke-width="2"/>')
    axisx=html.escape(xlabel+('（对数坐标）' if log else ''));axisy=html.escape(ylabel+('（对数坐标）' if log else ''))
    shapes.append(f'<text x="357" y="323" text-anchor="middle">{axisx}</text><text transform="translate(17,158) rotate(-90)" text-anchor="middle">{axisy}</text>')
    svg=f'<svg viewBox="0 0 680 340" role="img" aria-label="{html.escape(title,quote=True)}"><g font-family="system-ui" font-size="12" fill="#334155">'+''.join(shapes)+'</g></svg>'
    caption=f'显示 {len(usable):,}/{len(all_points):,} 个点；坐标变换不改变拟合参数。'
    if dropped:caption+=f'该对数视图省略 {dropped:,} 个非正值点；这些点仍保留在分析和CSV中。'
    return '<figure>'+svg+'<figcaption>'+caption+'</figcaption></figure>'


def section(row,points,xlabel,ylabel):
    title=row['group']+' · '+row['model_name'];parts=['<section><h2>'+html.escape(title)+'</h2>']
    if row.get('status')!='computed':return ''.join(parts)+'<p class="warning">'+html.escape(row.get('reason','未完成'))+'</p></section>'
    parts.append(parameter_table(row))
    parts.append(table(['统计量','结果'],[[label,row[key]] for key,label in STAT_LABELS if key in row]))
    gof=row.get('lnre_goodness_of_fit')
    if gof:
        parts.append('<h3>LNRE多元拟合优度</h3>'+table(['统计量','结果'],[[k,v] for k,v in gof.items()]))
    for key in ('parameter_uncertainty_note','parameter_test_note','confidence_interval_note','prediction_interpretation',
                'goodness_of_fit_note','information_criteria_note','comparison_note','support_note','selection_note','inference'):
        if row.get(key):parts.append('<p class="note">'+html.escape(str(row[key]))+'</p>')
    if row.get('warnings'):parts.append('<p class="warning">'+html.escape('；'.join(row['warnings']))+'</p>')
    if points:
        curve=any(p.get('predicted') is not None for p in points)
        parts.append('<h3>观测与'+('拟合' if curve else '相关散点')+'</h3>'+svg_plot(points,title,xlabel,ylabel,curve=curve))
        if curve and all(p['x']>0 and p['observed']>0 and (p['predicted'] is None or p['predicted']>0) for p in points):
            parts.append('<h3>双对数视图</h3>'+svg_plot(points,title,xlabel,ylabel,log=True))
        if curve and any(p.get('residual') is not None for p in points):
            parts.append('<h3>原尺度残差</h3>'+svg_plot(points,title,xlabel,'观测−预测',residual=True,curve=False))
    detail={k:v for k,v in row.items() if k not in {'gof_bin_details','lnre_expected_spectrum'}}
    parts.append('<details><summary>完整统计字段与计算说明</summary><pre>'+html.escape(json.dumps(clean(detail),ensure_ascii=False,indent=2))+'</pre></details></section>')
    return ''.join(parts)


def report_page(results,points,variables,scope,xlabel,ylabel):
    sections=[]
    for row in results[:12]:
        selected=[p for p in points if p['group']==row['group'] and p['model']==row['model']]
        sections.append(section(row,selected,xlabel,ylabel))
    style='body{max-width:1140px;margin:32px auto;padding:0 24px;font:15px system-ui;color:#17233b;background:#f6f8fc}section{background:white;padding:24px;margin:24px 0;border-radius:12px}svg{max-width:800px;width:100%;display:block}figure{margin:16px 0}figcaption,.note{font-size:13px;color:#536276}p{line-height:1.65}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:9px 12px;border-bottom:1px solid #e5eaf0;text-align:left;white-space:nowrap}th{background:#edf2f8}td:first-child{font-weight:500}.table-scroll{overflow-x:auto;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.warning{color:#964b09}h3{margin-top:24px}'
    caveat='参数估计完成不等于拟合充分或语言规律成立。区间和p值以各模型列出的抽样/误差假设为条件；未自动处理文档内依赖。C不是p值；LNRE多元χ²与普通Pearson χ²不能混用。图形最多展示前12个分析，CSV/JSON保存所有结果。'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LingMetrics 拟合报告</title><style>'+style+'</style><h1>LingMetrics 拟合报告</h1><p>'+html.escape(variables)+'</p><p>'+html.escape(scope)+'</p><p class="note">'+html.escape(caveat)+'</p><h2>模型比较</h2>'+overview(results)+''.join(sections)+'</html>'


def summary(results):
    lines=[]
    for r in results[:30]:
        title=r['group']+' · '+r['model_name']
        if r.get('status')!='computed':lines.append(title+'：'+r.get('reason',r.get('status','失败')));continue
        stats=[]
        for key,label in [('sample_n','n'),('r_squared','R²'),('rmse','RMSE'),('mae','MAE'),('log_space_r_squared','ln空间R²'),
                          ('chi_squared','χ²'),('chi_squared_df','df'),('goodness_of_fit_p_display','拟合优度p'),
                          ('discrepancy_coefficient','C（合并后）'),('aic','AIC'),('delta_aic','ΔAIC')]:
            if key in r:stats.append(label+'='+number(r[key]))
        if 'p_value_display' in r:stats.append('相关p='+r['p_value_display'])
        if r.get('lnre_goodness_of_fit'):
            g=r['lnre_goodness_of_fit'];stats.extend(['多元χ²='+number(g.get('chi_squared')),'df='+number(g.get('df')),'p='+str(g.get('p_value_display','—'))])
        lines.append(title+'\n  '+', '.join(name+'='+number(value) for name,value in r.get('parameters',{}).items())+'\n  '+'；'.join(stats))
    return '\n\n'.join(lines)
