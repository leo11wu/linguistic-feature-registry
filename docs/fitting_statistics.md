# 拟合统计量审计与报告口径 · 0.2.3

本次检查覆盖拟合页全部17个候选模型。参数估计、描述性偏差、条件性检验和候选模型比较分别报告；数值无定义、缺少计算依赖、参数在边界或假设不适用时，保留原因，不用零填补。

| 模型 | 本版报告的主要统计量 |
| --- | --- |
| 线性关系 | n、参数/SE/95% t区间、参数t检验及其零假设值、SSE/MSE/RMSE/MAE、R²/调整R²、残差自由度/标准误、完整高斯似然/AIC/BIC/AICc |
| 幂函数（原尺度） | n、参数/SE/局部线性近似95%区间、误差/R²/调整R²、残差自由度、完整高斯似然及信息准则、收敛与边界诊断 |
| 幂函数（对数回归） | 原尺度及ln响应尺度误差/R²/调整R²、反变换参数及区间、完整对数正态似然（含Jacobian）、信息准则 |
| 指数关系 | 与原尺度幂函数相同的误差、不确定性和收敛诊断 |
| Zipf排名曲线 | 同上；普通坐标/双对数视图/残差图。不是归一化的词型概率分布 |
| Zipf–Mandelbrot排名曲线 | 同上；移位参数边界单独记录 |
| Heaps增长曲线 | 同上；累计增长点存在依赖，常规区间和似然比较以独立误差假设为条件 |
| Menzerath–Altmann | 同上；显示参数相关矩阵条件数、边界和收敛信息 |
| Pearson相关 | r、n、双侧p、Fisher z的95%区间、不同值/重复行数、散点图 |
| Spearman相关 | rho、n、双侧近似p、不同值/重复行数、小样本提示、散点图；不冒用Pearson区间 |
| 泊松 | N、参数/SE/95%区间、实际/理论均值方差、似然/AIC/BIC/AICc、完整支持拟合优度及偏差量 |
| 零截断泊松 | 同上，条件概率已按正整数支持归一化 |
| 几何（从1开始） | 同上，支持为1、2、… |
| 负二项（含零） | 同上，联合观测信息矩阵用于r、p协方差；边界/不可识别时保留原因 |
| LNRE fZM | 词次N/词型V、参数、zipfR多元χ²/修正df/p、实际与期望词频谱、估计种子/方法 |
| LNRE ZM | 同上 |
| LNRE GIGP | 同上 |

## 样本量与权重

关系模型的n是纳入行数，权重是相对逆方差精度，权重和不是复制观测后的样本量。RMSE=sqrt(Σw·e²/Σw)，MAE=Σw·|e|/Σw。SSE=Σw·e²，残差自由度=n−p，残差标准误=sqrt(SSE/(n−p))；后者是相对权重刻度的误差参数，权重整体倍增会改变其刻度，但不会改变参数区间、加权RMSE或完整高斯似然。

普通离散分布的N=Σ频数，类别数另报。LNRE的N=Σm·V_m，V=ΣV_m；不能把词频谱的表行数当成独立词次样本量。

## 拟合优度与残差

普通离散分布使用完整支持，包括没有出现的零类别、内部缺失整数类别及未观测上尾。按相邻类别合并，尽量使每格期望频数≥5；不足的最后一格向前合并。`fit_gof_bins.csv`保留确切边界和频数。

- 主报告χ²=Σ(O−E)²/E，C=χ²/N，两者都使用合并后的同一类别集；df=类别数−1−已估参数数。
- p是按拟合模型、独立同分布观测及合并前参数估计作出的渐近近似。类别/自由度不足、参数在边界或数值筛选实际改变支持时不输出p。原始参数估计不变，不伪称已按合并类别重新估计。
- 同时报告逐整数类别χ²/N（仅描述），合并后的G²、完整支持总变差距离TV和离散CDF最大距离D。不同合并规则的C不能直接混用，也不对D套用连续KS的p值。
- Pearson残差=(O−E)/sqrt(E)。回归导出原尺度残差；对数回归另导出ln残差。`standardized_residual`使用对应拟合目标的残差与相对精度，未作杠杆校正，不能冒充学生化残差。

LNRE使用zipfR的多元χ²检验，保留词频谱元素间的协方差，并扣除在该词频谱上估计的参数数。LNRE的多元χ²不与普通Pearson χ²或C混同。

## 区间、比较与不输出的项目

线性参数区间用t分布；非线性区间使用局部线性近似，边界或严重病态时不输出常规区间。普通分布区间由观测信息得到，正值参数在log尺度、概率参数在logit尺度构建再反变换，保留参数定义域。协方差不可用时说明原因，不捏造区间。分布参数零值通常属于边界，不自动给出常规Wald零值检验。非线性模型也不自动给出可能不适用的参数零值t检验。

对数回归的反变换曲线exp(E[lnY|X])代表几何中心，在对数正态误差假设下是条件中位数，未作算术均值校正；区间a在ln(a)尺度构建后反变换。其原响应似然包含−Σln(y)的Jacobian项，避免和原响应高斯AIC作错误比较。

回归AIC/BIC的参数数包括误差方差；AICc仅在n>k+1时定义，非线性及普通分布的小样本修正属于近似。相同组、相同观测和相同响应量的相容似然另给ΔAIC/ΔBIC/ΔAICc及Akaike权重。权重仅相对于本次候选集，不是模型为真的概率。完美拟合使高斯误差方差退化时，有限信息准则无定义。

Spearman当前p来自SciPy的大样本近似；n≤500时明确提示置换检验。未预设重抽样或多重检验族，故不自动生成Spearman区间、bootstrap p或多重校正p；现有相关/参数p为未校正值。LNRE接口没有参数协方差及相容的最大化完整似然，因此不自动生成SE/区间或AIC/BIC。普通排名回归也不自动生成离散分布卡方，幂律尾部阈值选择和专门bootstrap检验需另定方案。

## 方法来源

- [SciPy curve_fit：协方差、相对权重、参数边界与病态诊断](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html)
- [NIST：卡方拟合优度、类别划分与参数估计](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35f.htm)
- [R stats：完整似然、参数数与AIC/BIC比较条件](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/AIC.html)
- [SciPy Pearson：p值及Fisher区间](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html)
- [SciPy Spearman：小样本p值限制](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html)
- [zipfR官方发布手册：LNRE多元拟合优度与参数估计](https://r-forge.r-universe.dev/zipfR/doc/manual.html)
- [Mačutek、Čech与Milička（2019）：偏差系数C的计量语言学应用](https://aclanthology.org/W19-7913.pdf)
