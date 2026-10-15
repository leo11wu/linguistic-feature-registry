"""Independent fitting of saved observations. Uses NumPy and optional existing SciPy/zipfR."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, html, json, math, signal, time, warnings, subprocess
import numpy as np
from . import __version__, resources
from .util import atomic_json, clean, csv_write, emit, sha, Unavailable

MODELS={
    'linear':('线性关系','relation'), 'power':('幂函数 y=a·x^b','relation'),
    'power_log':('幂函数（对数空间回归）','relation'),
    'exponential':('指数关系','relation'), 'zipf':('Zipf 排名曲线','relation'),
    'zipf_mandelbrot':('Zipf–Mandelbrot 排名曲线','relation'),
    'heaps':('Heaps 词型增长','relation'), 'menzerath_altmann':('Menzerath–Altmann 关系','relation'),
    'pearson':('Pearson 相关','relation'), 'spearman':('Spearman 秩相关','relation'),
    'poisson':('泊松分布（含零）','distribution'),
    'zero_truncated_poisson':('零截断泊松分布','distribution'),
    'geometric':('几何分布（从1开始）','distribution'),
    'negative_binomial':('负二项分布（含零）','distribution'),
    'lnre_fzm':('LNRE：有限 Zipf–Mandelbrot','distribution'),
    'lnre_zm':('LNRE：Zipf–Mandelbrot','distribution'),
    'lnre_gigp':('LNRE：GIGP','distribution'),
}
cancelled=False


def table_path(source,table=''):
    source=Path(source).expanduser().resolve()
    if source.is_file():
        if not source.name.lower().endswith(('.csv','.csv.gz')):raise ValueError('请选择提取结果目录或CSV数据表（支持.csv.gz）')
        return source,{}
    manifest=json.loads((source/'analysis_tables.json').read_text(encoding='utf-8-sig'))
    tables=manifest.get('tables',[])
    if manifest.get('schema_version')!=1:raise ValueError('不支持该观测表版本')
    entry=next((r for r in tables if r['id']==table),tables[0] if not table and tables else None)
    if entry is None:raise ValueError('未找到所选观测表')
    path=(source/entry['path']).resolve()
    if not path.is_relative_to(source) or not path.is_file():raise ValueError('观测表路径无效')
    if entry.get('sha256') and sha(path)!=entry['sha256']:raise ValueError('观测表已变化；如需分析编辑后的数据，请直接导入该CSV')
    return path,dict(entry,source_signature=manifest.get('source_signature'),measurement_choices=manifest.get('choices'),order=manifest.get('order'))


def read_table(path):
    from .util import text_open
    with text_open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);columns=reader.fieldnames or []
        if not columns or len(columns)!=len(set(columns)):raise ValueError('CSV列名为空或重复')
        rows=[]
        for number,row in enumerate(reader,2):
            if None in row or any(v is None for v in row.values()):raise ValueError(f'CSV第{number}行的列数不一致')
            rows.append(row)
    return columns,rows


def inspect(source,table=''):
    path,entry=table_path(source,table)
    preview=[];count=0;numeric=set();seen=set()
    from .util import text_open
    with text_open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);columns=reader.fieldnames or []
        if not columns or len(columns)!=len(set(columns)):raise ValueError('CSV列名为空或重复')
        for row in reader:
            count+=1
            if None in row or any(v is None for v in row.values()):raise ValueError('CSV行列数不一致')
            if count<=100:
                if len(preview)<5:preview.append(row)
                for key,value in row.items():
                    if value.strip():
                        if key not in seen:numeric.add(key);seen.add(key)
                        if finite(value) is None:numeric.discard(key)
    tables=[]
    if Path(source).is_dir():tables=json.loads((Path(source)/'analysis_tables.json').read_text(encoding='utf-8-sig'))['tables']
    emit('fit_columns',source=str(source),path=str(path),tables=tables,columns=columns,numeric_columns=[c for c in columns if c in numeric],rows=count,
         preview=preview,defaults=entry,
         models=[dict(id=k,name=v[0],kind=v[1],resource='lnre' if k.startswith('lnre_') else 'corpus' if k not in {'linear','power_log'} else '') for k,v in MODELS.items()])


def finite(value):
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None


def relation(model,x,y,w):
    n=len(x)
    if n<3 or np.unique(x).size<2:raise ValueError('关系分析至少需要3行和2个不同的X值')
    if model=='power_log':
        if np.any(x<=0) or np.any(y<=0):raise ValueError('对数空间回归要求X和Y均大于0；请显式筛选范围')
        base,log_prediction=relation('linear',np.log(x),np.log(y),w)
        a=math.exp(base['parameters']['intercept']);b=base['parameters']['slope'];predicted=np.exp(log_prediction)
        rss=float(np.sum(w*(y-predicted)**2));denom=float(np.sum(w*(y-np.average(y,weights=w))**2))
        return dict(parameters={'a':a,'b':b},method='weighted_log_log_least_squares',
                    log_space_covariance=base['covariance'],log_space_rmse=base['rmse'],
                    rmse=math.sqrt(rss/float(w.sum())),r_squared=1-rss/denom if denom else None,
                    inference='拟合目标是对数空间误差；原尺度RMSE另报。不等同于原尺度非线性最小二乘。'),predicted
    if model=='linear':
        design=np.column_stack([np.ones(n),x]);root=np.sqrt(w)
        params,_,rank,_=np.linalg.lstsq(design*root[:,None],y*root,rcond=None)
        if rank!=2:raise ValueError('线性模型不可识别')
        predicted=design@params;cov=np.linalg.inv((design*root[:,None]).T@(design*root[:,None]))*np.sum(w*(y-predicted)**2)/(n-2)
        names=['intercept','slope'];method='weighted_least_squares' if not np.all(w==1) else 'least_squares'
    else:
        try:from scipy import optimize,stats
        except ImportError:raise Unavailable('请在资源页准备“拟合计算工具：SciPy”','resource_required')
        if model in {'pearson','spearman'}:
            if not np.all(w==1):raise ValueError('相关分析不接受权重列；请先明确观测单位')
            if np.std(y)==0:raise ValueError('相关分析的Y没有变异')
            r,p=stats.pearsonr(x,y) if model=='pearson' else stats.spearmanr(x,y)
            return dict(parameters={'r':float(r)},p_value=float(p),method=model,
                        inference='p值基于相应抽样假设；不自动处理词型、文本或作者间的依赖'),None
        if np.any(x<=0) and model in {'power','zipf','zipf_mandelbrot','heaps','menzerath_altmann'}:
            raise ValueError('此模型要求X全部大于0；请显式设置筛选范围')
        if np.any(y<=0) and model in {'power','exponential','zipf','zipf_mandelbrot','heaps','menzerath_altmann'}:
            raise ValueError('此模型要求Y全部大于0')
        ymax=max(float(np.max(y)),1.)
        specs={
            'power':(lambda x,a,b:a*x**b,[float(np.median(y)),-.1],([0,-10],[np.inf,10]),['a','b']),
            'exponential':(lambda x,a,b:a*np.exp(b*x),[float(np.median(y)),0.],([0,-10],[np.inf,10]),['a','b']),
            'zipf':(lambda x,c,a:c*x**(-a),[ymax,1.],([0,0],[np.inf,10]),['C','a']),
            'zipf_mandelbrot':(lambda x,c,a,b:c*(x+b)**(-a),[ymax,1.,1.],([0,0,0],[np.inf,10,1e6]),['C','a','b']),
            'heaps':(lambda x,k,b:k*x**b,[1.,.5],([0,0],[np.inf,1]),['K','beta']),
            'menzerath_altmann':(lambda x,a,b,c:a*x**b*np.exp(c*x),[float(np.median(y)),-.1,0.],([0,-5,-1],[np.inf,5,1]),['a','b','c'])}
        func,p0,bounds,names=specs[model]
        if n<=len(p0) or np.unique(x).size<=len(p0):raise ValueError('不同X值及观测行数须多于模型参数数目')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            params,cov=optimize.curve_fit(func,x,y,p0=p0,bounds=bounds,sigma=1/np.sqrt(w),absolute_sigma=False,maxfev=12000)
        predicted=func(x,*params);method='nonlinear_least_squares'
    if not np.all(np.isfinite(predicted)):raise ValueError('预测值非有限数')
    residual=y-predicted;rss=float(np.sum(w*residual**2));denom=float(np.sum(w*(y-np.average(y,weights=w))**2))
    se=np.sqrt(np.maximum(0,np.diag(cov)))
    info=dict(parameters=dict(zip(names,map(float,params))),standard_errors=clean(dict(zip(names,map(float,se)))),
              covariance=clean(cov.tolist()),rmse=math.sqrt(rss/float(w.sum())),r_squared=1-rss/denom if denom else None,
              method=method,inference='描述性拟合；协方差和标准误依赖误差假设，不构成规律成立的证据')
    if model not in {'linear'} and caught:info['warnings']=[str(warning.message) for warning in caught]
    return info,predicted


def distribution(model,values,counts):
    if np.any(values<0) or np.any(values!=np.floor(values)):raise ValueError('离散分布需要非负整数观测值')
    if np.any(counts!=np.floor(counts)):raise ValueError('频数列须为正整数；不能用比例代替频数')
    total=float(counts.sum());mean=float(np.average(values,weights=counts))
    if total<3:raise ValueError('至少需要3个观测值（按频数展开后的数量）')
    if model.startswith('lnre_'):
        if np.any(values<1):raise ValueError('LNRE词频谱需要正整数频次')
        from .managed_r import fit as lnre
        result=lnre([dict(frequency=int(v),types=int(c)) for v,c in zip(values,counts)],model[5:])
        return dict(parameters=result['parameters'],method='zipfR_'+model[5:],inference='词频谱模型参数；未自动执行外推检验或重抽样'),None
    try:from scipy import optimize,stats
    except ImportError:raise Unavailable('请在资源页准备“拟合计算工具：SciPy”','resource_required')
    if model in {'zero_truncated_poisson','geometric'} and np.any(values<1):raise ValueError('此分布从1开始，不能包含零')
    if model=='poisson':
        params={'lambda':mean};logp=stats.poisson.logpmf(values,mean);k=1
        predict=lambda v:stats.poisson.pmf(v,mean)
    elif model=='zero_truncated_poisson':
        def objective(lam):return -float(np.sum(counts*(stats.poisson.logpmf(values,lam)-math.log(-math.expm1(-lam)))))
        result=optimize.minimize_scalar(objective,bounds=(1e-8,max(2,mean*2)),method='bounded')
        if not result.success:raise ValueError('零截断泊松估计未收敛')
        lam=float(result.x);params={'lambda':lam};logp=stats.poisson.logpmf(values,lam)-math.log(-math.expm1(-lam));k=1
        predict=lambda v:stats.poisson.pmf(v,lam)/(-math.expm1(-lam))
    elif model=='geometric':
        p=1/mean;params={'p':p};logp=stats.geom.logpmf(values,p);k=1
        predict=lambda v:stats.geom.pmf(v,p)
    elif model=='negative_binomial':
        if mean<=0:raise ValueError('负二项估计需要正均值')
        def objective(logr):
            r=math.exp(float(logr));p=r/(r+mean)
            return -float(np.sum(counts*stats.nbinom.logpmf(values,r,p)))
        result=optimize.minimize_scalar(objective,bounds=(-12,18),method='bounded')
        if not result.success or abs(result.x+12)<1e-3 or abs(result.x-18)<1e-3:raise ValueError('负二项估计位于边界；当前数据不能支持稳定的离散参数估计')
        r=math.exp(float(result.x));p=r/(r+mean);params={'r':r,'p':p};logp=stats.nbinom.logpmf(values,r,p);k=2
        predict=lambda v:stats.nbinom.pmf(v,r,p)
    else:raise ValueError('未知分布')
    ll=float(np.sum(counts*logp))
    if not math.isfinite(ll):raise ValueError('所选模型赋予观测数据零概率或出现数值问题')
    return dict(parameters=params,log_likelihood=ll,aic=2*k-2*ll,bic=k*math.log(total)-2*ll,
                sample_n=int(total),method='frequency_weighted_maximum_likelihood',
                inference='AIC/BIC仅比较同一组观测、同一支持及相容似然；不等于分布通过拟合优度检验'),predict(values)*total


def plot_svg(points,title):
    points=[p for p in points if p.get('predicted') is not None]
    if not points:return '<p>该分析不产生预测曲线。</p>'
    indices=np.linspace(0,len(points)-1,min(400,len(points)),dtype=int);points=[points[i] for i in indices]
    xs=[p['x'] for p in points];ys=[p['observed'] for p in points]+[p['predicted'] for p in points]
    xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
    xspan=xmax-xmin or 1.;yspan=ymax-ymin or 1.
    xp=lambda v:65+565*(v-xmin)/xspan
    yp=lambda v:280-240*(v-ymin)/yspan
    circles=''.join(f'<circle cx="{xp(p["x"]):.2f}" cy="{yp(p["observed"]):.2f}" r="2.4" fill="#718096" opacity=".6"/>' for p in points)
    line=' '.join(f'{xp(p["x"]):.2f},{yp(p["predicted"]):.2f}' for p in sorted(points,key=lambda p:p['x']))
    return f'<svg viewBox="0 0 680 330" role="img" aria-label="{html.escape(title,quote=True)}"><path d="M65 30V280H640" fill="none" stroke="#a0aec0"/>{circles}<polyline points="{line}" fill="none" stroke="#0e419c" stroke-width="2"/><g fill="#374151" font-size="12"><text x="65" y="305">{xmin:.4g}</text><text x="600" y="305">{xmax:.4g}</text><text x="5" y="280">{ymin:.4g}</text><text x="5" y="40">{ymax:.4g}</text></g></svg>'


def fit(job):
    global cancelled
    cancelled=False
    def stop(*_):
        global cancelled
        cancelled=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    resources.activate()
    path,entry=table_path(job['source'],job.get('table',''))
    source_hash=sha(path)
    columns,rows=read_table(path)
    if sha(path)!=source_hash:raise ValueError('读取期间源表发生变化，请重新载入')
    kind=job.get('kind','relation');models=list(dict.fromkeys(job.get('models',[])))
    if kind not in {'relation','distribution'} or not models:raise ValueError('请选择分析类型和至少一个候选模型')
    if any(m not in MODELS or MODELS[m][1]!=kind for m in models):raise ValueError('模型与分析类型不匹配')
    xcol=job.get('x','');ycol=job.get('y','');weight=job.get('weight','');group=job.get('group','')
    needed=[xcol]+([ycol] if kind=='relation' else [])+([weight] if weight else [])+([group] if group else [])
    if any(not c or c not in columns for c in needed):raise ValueError('所选变量、频数或分组列不存在')
    if len({xcol,ycol})<2 and kind=='relation':raise ValueError('X和Y需要选择不同列')
    low=finite(job.get('min_x')) if job.get('min_x') not in {None,''} else None
    high=finite(job.get('max_x')) if job.get('max_x') not in {None,''} else None
    if (job.get('min_x') not in {None,''} and low is None) or (job.get('max_x') not in {None,''} and high is None):raise ValueError('X筛选范围须为有限数值')
    if low is not None and high is not None and low>high:raise ValueError('X下限不能大于上限')
    ylow=finite(job.get('min_y')) if job.get('min_y') not in {None,''} else None
    yhigh=finite(job.get('max_y')) if job.get('max_y') not in {None,''} else None
    if (job.get('min_y') not in {None,''} and ylow is None) or (job.get('max_y') not in {None,''} and yhigh is None):raise ValueError('Y筛选范围须为有限数值')
    if ylow is not None and yhigh is not None and ylow>yhigh:raise ValueError('Y下限不能大于上限')
    output=Path(job['output']).expanduser().resolve()
    if output==path.parent or (Path(job['source']).is_dir() and (output==Path(job['source']).resolve() or output in path.parents)):
        raise ValueError('拟合结果需要独立目录，请勿覆盖观测数据')
    if output.exists() and any(output.iterdir()):raise ValueError('拟合输出目录已有文件，请使用新的结果目录')
    grouped=defaultdict(list);excluded=Counter();selected=[]
    for index,row in enumerate(rows,2):
        x=finite(row[xcol]);y=finite(row[ycol]) if kind=='relation' else None;w=finite(row[weight]) if weight else 1.
        if x is None or (kind=='relation' and y is None):excluded['missing_or_non_numeric']+=1;continue
        if w is None or w<=0:excluded['missing_or_nonpositive_weight']+=1;continue
        if job.get('positive_only',False) and (x<=0 or (kind=='relation' and y<=0)):excluded['nonpositive_value']+=1;continue
        if (low is not None and x<low) or (high is not None and x>high):excluded['outside_x_range']+=1;continue
        if kind=='relation' and ((ylow is not None and y<ylow) or (yhigh is not None and y>yhigh)):excluded['outside_y_range']+=1;continue
        if group and not row[group].strip():excluded['missing_group']+=1;continue
        label=row[group] if group else 'all_rows'
        obs=dict(source_row=index,group=label,x=x,y=y,weight=w)
        selected.append(obs);grouped[label].append(obs)
    if not selected:raise ValueError('筛选后没有可用的数值观测；请检查变量和范围')
    # A common observation set is used for every candidate; domain violations are errors, not silent extra filtering.
    if any(m.startswith('lnre_') for m in models) and (not weight or not (entry.get('id')=='frequency_spectrum' or job.get('lnre_frequency_spectrum') is True)):
        raise ValueError('LNRE仅适用于频次—词型数的词频谱；外部CSV需明确确认该口径')
    output.mkdir(parents=True,exist_ok=True)
    csv_write(output/'selected_observations.csv',selected,['source_row','group','x','y','weight'])
    config=dict(job,source=str(Path(job['source']).resolve()),source_table=str(path),source_sha256=source_hash,measurement=entry)
    atomic_json(output/'fit_config.json',config)
    manifest=dict(version=__version__,workflow='fit',state='running',started_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  source_sha256=config['source_sha256'],input_rows=len(rows),selected_rows=len(selected),excluded=dict(excluded),
                  row_unit=entry.get('unit','user supplied'),weight_interpretation='frequency counts' if kind=='distribution' else 'least squares inverse-variance weights (relative)',
                  source_order=entry.get('order'),limits='No automatic independence, causal, goodness-of-fit or law-validation claim. No diachronic analysis.')
    atomic_json(output/'fit_manifest.json',manifest)
    emit('fit_started',groups=len(grouped),models=len(models),rows=len(selected),output=str(output))
    results=[];points=[];sections=[];done=0;total=len(grouped)*len(models)
    try:
        for label,observations in grouped.items():
            x=np.array([r['x'] for r in observations]);w=np.array([r['weight'] for r in observations]);y=np.array([r['y'] for r in observations]) if kind=='relation' else None
            for model in models:
                if cancelled:break
                done+=1;emit('progress',completed=done,total=total,message='拟合 '+label+' · '+MODELS[model][0])
                row=dict(group=label,model=model,model_name=MODELS[model][0],n_rows=len(x))
                current=[]
                try:
                    if kind=='distribution':
                        compressed=Counter()
                        for v,c in zip(x,w):compressed[float(v)]+=float(c)
                        xx=np.array(sorted(compressed));ww=np.array([compressed[v] for v in xx])
                        info,predicted=distribution(model,xx,ww);actual=ww
                    else:xx=x;actual=y;info,predicted=relation(model,x,y,w)
                    row.update(status='computed',**info)
                    if predicted is not None:
                        current=[dict(group=label,model=model,source_row=observations[i]['source_row'] if kind=='relation' else '',x=float(a),observed=float(b),predicted=float(c),residual=float(b-c)) for i,(a,b,c) in enumerate(zip(xx,actual,predicted))]
                        points.extend(current)
                except (ValueError,RuntimeError,Unavailable,ArithmeticError,np.linalg.LinAlgError,OSError,subprocess.SubprocessError) as error:
                    row.update(status=getattr(error,'status','error'),reason=str(error))
                results.append(row)
                if len(sections)<12:
                    title=label+' · '+MODELS[model][0]
                    detail=html.escape(json.dumps(clean(row),ensure_ascii=False,indent=2))
                    sections.append('<section><h2>'+html.escape(title)+'</h2>'+plot_svg(current,title)+'<pre>'+detail+'</pre></section>')
            if cancelled:break
        csv_write(output/'fit_results.csv',results)
        csv_write(output/'fit_predictions.csv',points,['group','model','source_row','x','observed','predicted','residual'])
        caveat='结果用于比较所选数据与模型；参数、相关或较低AIC不自动证明语言规律或因果关系。曲线图展示至多400个点；完整观测与残差保存在CSV。增长曲线的累计点不独立。'
        variables=f'源表：{path.name}；观测单位：{manifest["row_unit"]}；X/观测值：{xcol}；Y：{ycol if kind=="relation" else "实际/预测频数"}；权重/频数：{weight or "每行等权"}；分组：{group or "全部行"}。灰点为观测，蓝线为预测。'
        page='<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LingMetrics 拟合报告</title><style>body{max-width:1000px;margin:40px auto;padding:0 24px;font:16px system-ui;color:#17233b;background:#f6f8fc}section{background:white;padding:20px;margin:20px 0;border-radius:12px}svg{max-width:680px;width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}p{line-height:1.7}</style><h1>LingMetrics 拟合报告</h1><p>'+html.escape(variables)+'</p><p>'+html.escape(caveat)+'</p><p>'+html.escape(f'输入 {len(rows)} 行；纳入 {len(selected)} 行；排除 {dict(excluded)}；图形最多展示前12个分析。')+'</p>'+''.join(sections)+'</html>'
        (output/'report.html').write_text(page,encoding='utf-8')
        statuses=Counter(r['status'] for r in results)
        state='cancelled' if cancelled else 'complete' if statuses.get('computed')==len(results) else 'partial' if statuses.get('computed') else 'failed'
        manifest.update(state=state,finished_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),status_counts=dict(statuses),
                        outputs={p.name:sha(p) for p in output.iterdir() if p.is_file() and p.name!='fit_manifest.json'})
        atomic_json(output/'fit_manifest.json',manifest)
        summary='\n'.join(r['group']+' · '+r['model_name']+'：'+(json.dumps(clean(r.get('parameters',{})),ensure_ascii=False) if r['status']=='computed' else r.get('reason',r['status'])) for r in results[:30])
        emit('fit_finished',state=state,output=str(output),status_counts=dict(statuses),summary=summary)
        return manifest
    except Exception as error:
        manifest.update(state='failed',error=f'{type(error).__name__}: {error}');atomic_json(output/'fit_manifest.json',manifest);raise
