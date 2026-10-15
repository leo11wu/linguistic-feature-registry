# 资源与导入模板

基础词典CMUdict随应用提供。大型依赖和模型存放在用户的 `Library/Application Support/LingMetrics`；单个资源准备成功后才写入清单，记录实际版本和文件校验值。

“拟合计算工具：SciPy”仅是计算依赖，不含语料，内部资源ID保留`corpus`以兼容已有安装。线性和对数空间幂函数使用已有NumPy；其他常规拟合按需使用SciPy，LNRE使用独立R/zipfR。冻结参照来自用户先前的提取结果，选择方式见[工作流](fitting.md)。Biber与SID应用已给定的维度/训练簇，不在提取时重新训练。

## 词表

导入UTF-8 CSV/TSV，首列 `word`，其他列采用资源页显示的字段名。支持常见原字段别名，例如 SUBTLEX-US 的 `Word/SubtlWF/Lg10WF/Lg10CD`、具体性 `Word/Conc.M`、AoA `Word/AoA_Kup`。无法判断的字段要求按模板整理，不能自动猜含义。

```csv
word,frequency_pm,lg10wf,lg10cd,rank
example,12.5,2.0,1.5,1000
```

此例数字只用于格式展示，不是SUBTLEX真实词频。真实资源应保留原文件，确认计数单位；Lg10WF是log10(FREQcount+1)。词表导入可含缺失，但不允许悄悄合并同词不同值。

规范资源默认对NOUN、VERB、ADJ查词形，排除PROPN/AUX；词次与词型均值、覆盖率分开。固定词表支持多词词条，以句内完整词序列匹配。类别可重叠，整体覆盖率使用词位置并集。

资源及标准列：

|资源ID|标准字段|
|---|---|
|subtlex|word, frequency_pm, lg10wf, lg10cd, contextual_diversity, rank|
|aoa / concreteness|word, aoa / concreteness|
|mrc|word, familiarity, imageability|
|vad|word, valence, arousal, dominance|
|lancaster|word及视觉、听觉、触觉、嗅觉、味觉、内感、五类动作；字段见资源页|
|morpholex|word, morphemes, prefixes, suffixes, roots, family_size, family_frequency, process|
|semd|word, semd|
|academic / semantic_categories / connectives / function_words / stance / nominalizations / easy_words|word, category|
|register_frequency|word, register, frequency_pm|
|vac|word=lemma\|sorted_dependency_frame, construction, frequency_pm|
|unigram|word, probability（0<p≤1）|

## 模型

模型下载时解析远程修订并固定commit，随后只读本地快照。首次选择新版本会产生新的资源身份；它会阻止旧运行无说明续算。资源尺寸为预估，实际磁盘大小以资源页统计为准。

语义基线MPNet、因果基线Pythia410M step143000和BERT uncased为新计算后端，不能当作原工具结果直接替换。共指与成分树默认CPU；Stanza原始PTB配置为ptb3_charlm。

## 研究配置资源

SID的JSON包含 `centroids`、`distance_means`、`distance_sds`、`embedding_id`、`training_hash`；只能使用训练数据拟合簇。Biber配置包含 `features`（id、rule或sequence、scale、reference_mean、reference_sd）及 `dimensions`（id、weights）。规则支持pos、tag、lemma、word、dep及morph，均为字段匹配，不能执行任意代码。

LAL v24.10精确助手随应用提供；输入n和边，输出 `{"minimum":整数,"exact":true}`。协议包装器校验树结构、排列和实际长度；支持最多500节点。源码、库和许可随native档案提供。外部替代助手可通过JSON配置导入，必须明确版本及exact标记。

LNRE模块按需下载R 4.5.3与zipfR 0.6-70，提取到独立缓存并重定位内部库路径；不安装系统R，不需要用户编译。保留官方安装包校验值与组件版本。

fastText可直接导入300维.bin或使用指向文件的JSON配置，建议 `cc.en.300.bin`；保留子词OOV能力，.vec不作为同一资源。删除登记保留用户的原始.bin文件。SID使用fastText时embedding_id为 `fasttext.bin.` 加实际文件SHA256；使用MPNet时须另提供matching的embedding_revision。所有配置和来源文件哈希均随运行保存。
