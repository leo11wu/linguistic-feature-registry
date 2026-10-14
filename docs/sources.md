# 来源索引

下列73条为来源记录，核验边界随原记录保留。书目、摘要、方法段和源码／数据文件核验分别看待。

## R01 · TextDescriptives

- 类型：官方文档
- 支持范围：基础统计、词性、可读性、依存距离
- 书目／版本：文档显示 2.8.4；未安装试跑
- [来源页面](https://hlasse.github.io/TextDescriptives/usingthepackage.html)
- 核验边界：Available Attributes；组件范围不等于完整句法复杂度体系

## R02 · LFTK

- 类型：论文与官方文档
- 支持范围：通用特征及特征检索命名
- 书目／版本：Lee & Lee (2023), BEA, 1–19；论文称超过 220 项
- [来源页面](https://aclanthology.org/2023.bea-1.1/)
- 核验边界：补充入口 https://lftk.readthedocs.io/en/latest/；数量含归一化和聚合变体

## R03 · LexicalRichness

- 类型：官方文档
- 支持范围：TTR、MATTR、MTLD、HD-D、voc-D 等
- 书目／版本：Python；未试跑
- [来源页面](https://lexicalrichness.readthedocs.io/en/latest/)
- 核验边界：Details of Lexical Richness Measures；应保留窗口、阈值、抽样种子

## R04 · quanteda.textstats

- 类型：维护者参考手册
- 支持范围：词汇多样性和文本统计
- 书目／版本：R；手册列出 TTR、Yule、Simpson、MATTR 等
- [来源页面](https://quanteda.r-universe.dev/quanteda.textstats/doc/manual.html)
- 核验边界：textstat_lexdiv；不要假定其包含 LexicalRichness 的所有方法

## R05 · TAALED

- 类型：官方页面
- 支持范围：词汇多样性，lemma/POS 口径
- 书目／版本：官方提供 Python 3 版本；页面仍标为 Beta
- [来源页面](https://www.linguisticanalysistools.org/taaled.html)
- 核验边界：同形词可结合词性区分；与只按词形计数的结果不可直接互换

## R06 · TAALES

- 类型：官方页面
- 支持范围：词频、分布范围、心理常模、多词单位
- 书目／版本：页面称超过 400 项；稳定版 2.2，Beta 2.8.1
- [来源页面](https://www.linguisticanalysistools.org/taales.html)
- 核验边界：旧 Mac 发行版有兼容性提示；不是已验证的当前环境安装建议

## R07 · TAALES 2.2 index guide

- 类型：作者发布指标表
- 支持范围：指标代码、分母、常模来源
- 书目／版本：检索到了可读的前部索引内容；未完整下载所有工作表
- [来源页面](https://docs.google.com/spreadsheets/d/1axmeHlKE-aelPHX4L17WpHjC7Jn4yQlE/edit)
- 核验边界：部分 MRC 行的 numerator/denominator 文本疑似复制残留；不照抄其公式

## R08 · SUBTLEX-US

- 类型：研究团队页面
- 支持范围：词形频率、语境覆盖
- 书目／版本：美国英语字幕词频；Brysbaert & New (2009)
- [来源页面](https://www.ugent.be/plone_portal/pp/experimentele-psychologie/en/research/documents/subtlexus/overview.htm)
- 核验边界：参考语料与目标语域不同会影响词汇难度解释

## R09 · wordfreq

- 类型：维护者 README
- 支持范围：多语种参考词频与 Zipf frequency
- 书目／版本：作者说明数据大致反映截至 2021 年的使用
- [来源页面](https://github.com/rspeer/wordfreq/blob/master/README.md?plain=1)
- 核验边界：Zipf 刻度是 log10(每十亿词频率)；默认未登录词 0 是回退值

## R10 · Age-of-acquisition norms

- 类型：原始论文出版页
- 支持范围：词汇习得年龄 AoA
- 书目／版本：Kuperman, Stadthagen-Gonzalez & Brysbaert (2012), 44, 978–990
- [来源页面](https://link.springer.com/article/10.3758/s13428-012-0210-4)
- 核验边界：30,121 个实词；出版页列有 2013 勘误，实际使用应核对修正版

## R11 · Concreteness norms

- 类型：作者机构记录
- 支持范围：具体性常模
- 书目／版本：Brysbaert, Warriner & Kuperman (2014), 46, 904–911
- [来源页面](https://biblio.ugent.be/publication/5774089)
- 核验边界：37,058 个词和 2,896 个双词表达；常模评分不能替代语境词义

## R12 · Lancaster Sensorimotor Norms

- 类型：研究团队页面
- 支持范围：六类知觉、五类动作强度
- 书目／版本：39,707 个概念；Lynott et al.
- [来源页面](https://www.lancaster.ac.uk/psychology/lsnorms/)
- 核验边界：保留 11 维评分或预先选定的合成分数；不要把各维相加当默认总分

## R13 · NRC VAD

- 类型：作者资源页
- 支持范围：valence、arousal、dominance
- 书目／版本：页面提供 v2.1（2025-03）及 v1
- [来源页面](https://saifmohammad.com/WebPages/nrc-vad.html)
- 核验边界：版本、评分尺度、单词与多词条目须固定；研究教育用途条款见原页

## R14 · WordNet

- 类型：官方说明
- 支持范围：词义、上位词、同义词集合
- 书目／版本：英语词汇语义网络
- [来源页面](https://wordnet.princeton.edu/front)
- 核验边界：必须区分词形、词性、synset；未消歧时是词典层面特征

## R15 · MorphoLex-en

- 类型：作者仓库及论文
- 支持范围：派生形态、词根与词缀变量
- 书目／版本：约 70,000 词；doi:10.3758/s13428-017-0981-8
- [来源页面](https://github.com/hugomailhot/MorphoLex-en)
- 核验边界：数据词典提供字段定义；不把派生形态表误当逐词上下文屈折分析器

## R16 · Universal Dependencies

- 类型：官方标注规范
- 支持范围：词性、形态、依存关系
- 书目／版本：本次查看英语形态页与通用特征规范
- [来源页面](https://universaldependencies.org/en/feat/)
- 核验边界：通用规范 https://universaldependencies.org/u/feat/all.html；语言和树库支持程度不同

## R17 · L2SCA

- 类型：作者页面
- 支持范围：14 个经典句法复杂度指标
- 书目／版本：Lu (2010), IJCL 15(4), 474–496；作者页列 4.2.2
- [来源页面](https://sites.psu.edu/xxl13/l2sca/)
- 核验边界：9 类结构计数；MLS 已归入基础长度条目，不再重复计数

## R18 · TAASSC

- 类型：官方页面
- 支持范围：细粒度短语、从句复杂度与 VAC 熟练度
- 书目／版本：Kyle (2016)；官网页面列 1.3.8
- [来源页面](https://www.linguisticanalysistools.org/taassc.html)
- 核验边界：官网旧发行版涉及 Python 2.7/Java；实施前需核验替代实现与原定义

## R19 · Linear Arrangement Library (LAL)

- 类型：研究团队页面与仓库
- 支持范围：依存距离、交叉、线性排列和随机基线
- 书目／版本：Python/C++；未编译或试跑
- [来源页面](https://cqllab.upc.edu/lal/)
- 核验边界：仓库 https://github.com/LAL-project/linear-arrangement-library；输入是结构，原始文本需先解析

## R20 · TAACO

- 类型：官方页面及维护仓库
- 支持范围：局部/全局重叠、连接词、语义相似度
- 书目／版本：官网列 Python 2.1.3（2023-10-06）；概述写 150 项
- [来源页面](https://www.linguisticanalysistools.org/taaco.html)
- 核验边界：https://github.com/LCR-ADS-Lab/TAACO；2.1.x 改用 spaCy，结果与旧版有差异

## R21 · TextDescriptives coherence

- 类型：官方组件文档
- 支持范围：相邻及隔句向量余弦相似度
- 书目／版本：第一阶与第二阶 coherence
- [来源页面](https://hlasse.github.io/TextDescriptives/coherence.html)
- 核验边界：这是向量相似度操作化；不等于读者理解层面的全部连贯性

## R22 · Transformers perplexity

- 类型：官方文档
- 支持范围：因果语言模型的条件概率与 PPL
- 书目／版本：适用于因果语言模型；需记录窗口和 tokenizer
- [来源页面](https://huggingface.co/docs/transformers/perplexity)
- 核验边界：PPL=exp(平均负对数概率)；不同 tokenizer 的数值不直接可比

## R23 · SciPy entropy

- 类型：官方 API 文档
- 支持范围：Shannon entropy 与 KL divergence
- 书目／版本：定义与底数参数已核对；实现由研究者选输入分布
- [来源页面](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.entropy.html)
- 核验边界：公式函数不会替研究者确定 token、概率空间或抽样偏差修正

## R24 · textstat

- 类型：维护者仓库
- 支持范围：传统可读性公式
- 书目／版本：Python；提供多种英文公式
- [来源页面](https://github.com/textstat/textstat)
- 核验边界：相同公式跨工具可能因分词、音节和句界不同而数值不同

## R25 · Multidimensional Analysis Tagger (MAT)

- 类型：作者页面
- 支持范围：Biber 文体语域特征和维度
- 书目／版本：Nini (2019)；当前下载页面主推 Windows/Java
- [来源页面](https://sites.google.com/site/multidimensionaltagger/about)
- 核验边界：原始语法计数与标准化维度分数分开；需使用匹配的标准化基准

## R26 · LIWC-22

- 类型：官方产品页
- 支持范围：词典类别、语言风格匹配
- 书目／版本：商业软件，页面有购买入口；未购买/安装
- [来源页面](https://www.liwc.app/)
- 核验边界：类别词频可用作可解释特征；类别重叠，不能视作互斥概率分布

## R27 · CMUdict

- 类型：项目官方仓库
- 支持范围：美式英语音素、词汇重音
- 书目／版本：发音词典；未下载数据
- [来源页面](https://github.com/cmusphinx/cmudict)
- 核验边界：多发音词与未登录词须有策略；词典读音不等于实际语流

## R28 · English Lexicon Project

- 类型：项目官方页面
- 支持范围：词汇特征及词汇判断/命名行为数据
- 书目／版本：40,481 词及配套非词
- [来源页面](https://elexicon.wustl.edu/)
- 核验边界：本次仅核对资源范围；具体 OLD20/PLD20 字段映射实施前复核

## R29 · zipfR

- 类型：CRAN 作者参考手册
- 支持范围：频谱、词汇增长、LNRE 模型
- 书目／版本：手册版本 0.6-70；Evert & Baroni
- [来源页面](https://cran.r-project.org/web/packages/zipfR/zipfR.pdf)
- 核验边界：lnre、spc、vgc；手册生成日期不等于软件更新日期

## R30 · Power-law distributions in empirical data

- 类型：作者资源页
- 支持范围：幂律估计、拟合检验和替代分布比较
- 书目／版本：Clauset, Shalizi & Newman (2009), SIAM Review 51, 661–703
- [来源页面](https://aaronclauset.github.io/powerlaws/)
- 核验边界：方法参考；频率分布与排名曲线的指数不是同一参数

## R31 · Menzerath-Altmann Law in Syntactic Dependency Structure

- 类型：原始论文
- 支持范围：构体大小与组成单位大小的关系
- 书目／版本：Mačutek, Čech & Milička (2017)
- [来源页面](https://aclanthology.org/W17-6513/)
- 核验边界：原文研究捷克语；此处收录方法候选，不声称英语已复现

## R32 · Taylor’s law for Human Linguistic Sequences

- 类型：原始论文
- 支持范围：词项计数均值与波动的标度
- 书目／版本：Kobayashi & Tanaka-Ishii (2018), ACL, 1138–1148
- [来源页面](https://aclanthology.org/P18-1105/)
- 核验边界：std 对 mean 与 variance 对 mean 的指数相差 2 倍，必须注明

## R33 · Burstiness and memory in complex systems

- 类型：原始论文
- 支持范围：事件间隔离散程度及相邻间隔相关
- 书目／版本：Goh & Barabási (2008), EPL 81, 48002
- [来源页面](https://barabasi.com/media/pub_imports/files/233.pdf)
- 核验边界：移用于词项位置属于本目录的操作化建议；要检验长度与频率效应

## R34 · Word lengths are optimized for efficient communication

- 类型：原始论文
- 支持范围：词长、词频、条件信息量关系
- 书目／版本：Piantadosi, Tily & Gibson (2011), PNAS 108, 3526–3529
- [来源页面](https://pmc.ncbi.nlm.nih.gov/articles/PMC3048148/)
- 核验边界：用于区分词频与语境信息量的解释；不直接采纳其机制结论

## R35 · spaCy linguistic features

- 类型：官方文档
- 支持范围：分词、lemma、POS、形态、依存、实体
- 书目／版本：作为底层标注；不是全部指标的现成实现
- [来源页面](https://spacy.io/usage/linguistic-features)
- 核验边界：英语模型依存标签未必是 UD；记录模型、版本和标注方案

## R36 · NLTK collocations

- 类型：官方文档
- 支持范围：n-gram、PMI 与搭配关联量
- 书目／版本：Bigram/Trigram/QuadgramAssocMeasures
- [来源页面](https://www.nltk.org/howto/collocations.html)
- 核验边界：PMI 对罕见组合敏感；应固定计数窗口与最低频数

## R37 · GAMET

- 类型：官方页面
- 支持范围：语法、拼写、标点等错误标记
- 书目／版本：Crossley, Bradfield & Bustamante (2019), JoWR 11(2), 251–270
- [来源页面](https://www.linguisticanalysistools.org/gamet.html)
- 核验边界：错误识别需人工抽核；旧发行版存在平台依赖

## R38 · TextDescriptives quality

- 类型：官方组件文档
- 支持范围：重复及字符组成等质量诊断
- 书目／版本：语料过滤用途
- [来源页面](https://hlasse.github.io/TextDescriptives/quality.html)
- 核验边界：这些量适合质控；不要把软件过滤标记直接称作语言能力

## R39 · Semantic diversity

- 类型：作者机构记录
- 支持范围：不同使用语境之间的语义变异
- 书目／版本：Hoffman, Lambon Ralph & Rogers (2013), BRM 45, 718–730
- [来源页面](https://research.manchester.ac.uk/en/publications/semantic-diversity-a-measure-of-semantic-ambiguity-based-on-varia/)
- 核验边界：与 TTR 和 WordNet 词义数量不同；常模/再估计模型需另行固定

## R40 · Coh-Metrix 理论与测量框架

- 类型：原始论文与官方入口
- 支持范围：篇章衔接、多层文本指标
- 书目／版本：Graesser & McNamara (2011), Topics in Cognitive Science
- [来源页面](https://doi.org/10.1111/j.1756-8765.2010.01081.x)
- 核验边界：https://cohmetrix.com/ 重定向到 Memphis 页面，本次未获得可读界面；未验证在线可用性

## R41 · TextDescriptives information theory

- 类型：官方组件文档
- 支持范围：基于 spaCy 词汇概率表的分数
- 书目／版本：与因果语言模型条件 surprisal 分开
- [来源页面](https://hlasse.github.io/TextDescriptives/information_theory.html)
- 核验边界：文档所写 PPL 指数符号与示例数值存在疑点；本轮不推荐直接入模

## R42 · scikit-learn 方法文档

- 类型：官方文档
- 支持范围：训练内预处理、特征选择、分组验证
- 书目／版本：仅作预测建模流程参考
- [来源页面](https://scikit-learn.org/stable/common_pitfalls.html)
- 核验边界：另见 https://scikit-learn.org/stable/modules/cross_validation.html

## R43 · LingFeat

- 类型：作者仓库
- 支持范围：历史特征清单及迁移记录
- 书目／版本：README 说 255 项；2023-03-06 通知迁移 LFTK；仓库已归档
- [来源页面](https://github.com/brucewlee/lingfeat)
- 核验边界：适合补查 entity-grid/树结构等旧指标；不是可直接叠加的另一套独立指标

## R44 · Dispersions and adjusted frequencies in corpora

- 类型：原始论文
- 支持范围：DP；词项在语料分块中的分布
- 书目／版本：Gries (2008), IJCL 13(4), 403–437; doi:10.1075/ijcl.13.4.02gri
- [来源页面](https://www.stgries.info/research/2008_STG_Dispersion_IJCL.pdf)
- 核验边界：核对 DP 定义；归一化版本须同时读 R45 勘误。

## R45 · Correction to Dispersions and adjusted frequencies in corpora

- 类型：勘误原文
- 支持范围：DPnorm 的不等长分块修正
- 书目／版本：Lijffijt & Gries (2012), IJCL 17(1), 147–149; doi:10.1075/ijcl.17.1.08lij
- [来源页面](https://www.stgries.info/research/2012_JL-STG_DispersionCorrection_IJCL.pdf)
- 核验边界：全文核对 pp.147–149，尤其 Eq.(2)；不沿用只适合等长分块的旧式。

## R46 · 50-something years of work on collocations: What is or should be next

- 类型：方法论文
- 支持范围：有方向的关联强度 ΔP
- 书目／版本：Gries (2013), IJCL 18(1); doi:10.1075/ijcl.18.1.09gri
- [来源页面](https://stgries.info/research/2013_STG_DeltaP%26H_IJCL.pdf)
- 核验边界：核对 §2.3、Eq.(3)；这是把关联学习指标引入搭配研究，不能称其发明 ΔP。

## R47 · A Lexicographer-Friendly Association Score

- 类型：原始论文
- 支持范围：logDice；共现计数口径
- 书目／版本：Rychlý (2008), RASLAN, 6–9
- [来源页面](https://nlp.fi.muni.cz/raslan/2008/papers/13.pdf)
- 核验边界：核对 §4 公式；目录不把分数正负当作统计显著性检验。

## R48 · Normalized Dependency Distance: Proposing a New Measure

- 类型：原始论文元数据
- 支持范围：NDD 的提出与书目定位
- 书目／版本：Lei & Jockers (2020), JQL 27(1), 62–79; online 2018; doi:10.1080/09296174.2018.1504615
- [来源页面](https://www.tandfonline.com/doi/abs/10.1080/09296174.2018.1504615)
- 核验边界：本轮未取得原文全文；公式由 R49 替代实现文档核对，原始预处理口径仍待原文核验。

## R49 · QuanSyn

- 类型：工具维护者仓库
- 支持范围：NDD、root distance 的实现定义
- 书目／版本：YuhuYang/QuanSyn README；本轮未安装
- [来源页面](https://github.com/YuhuYang/QuanSyn)
- 核验边界：非 Lei/Jockers 原作者实现；只用于明确此替代实现的定义，不据此证明原实现完全一致。

## R50 · Optimality of syntactic dependency distances

- 类型：论文与作者预印本
- 支持范围：Γ、Δ、Dz、Ω；随机排列与最小排列基线
- 书目／版本：Ferrer-i-Cancho et al. (2022), Physical Review E 105, 014308; doi:10.1103/PhysRevE.105.014308
- [来源页面](https://www.grupolys.org/biblioteca/FerGomEstAle2021a.pdf)
- 核验边界：方法按作者预印本 §II, Eqs.(1)–(6) 核对；期刊记录 https://upcommons.upc.edu/handle/2117/365207 。

## R51 · Syntactic complexity measures for detecting Mild Cognitive Impairment

- 类型：原始研究中的实现说明
- 支持范围：Yngve、Frazier 的树规则与聚合方式
- 书目／版本：Roark, Mitchell & Hollingshead (2007), ACL workshop, 1–8
- [来源页面](https://aclanthology.org/W07-1001/)
- 核验边界：核对 PDF §§2–3.2；本次采用此论文操作化，未宣称已核对 Yngve 1960/Frazier 1985 原著全部细节。

## R52 · Automatic Measurement of Syntactic Complexity Using the Revised Developmental Level Scale

- 类型：原始实现论文
- 支持范围：修订 D-Level 0–7 级及识别规则
- 书目／版本：Lu (2008), FLAIRS
- [来源页面](https://cdn.aaai.org/FLAIRS/2008/FLAIRS08-043.pdf)
- 核验边界：核对 The Developmental Level Scale 节；儿童英语材料不能自动代表成人写作效度。

## R53 · Automatic measurement of propositional idea density from part-of-speech tagging

- 类型：原始工具论文
- 支持范围：CPIDR 3.2；standard/speech 两种模式
- 书目／版本：Brown et al. (2008), BRM 40(2), 540–545; doi:10.3758/BRM.40.2.540
- [来源页面](https://ai.uga.edu/sites/default/files/inline-files/caspr/BrownSnodgrassKemperHermanCovington2008.pdf)
- 核验边界：核对 Rules 与 Speech mode；论文规则总数为 37，不能用简单 POS 比率冒充完整 CPIDR。

## R54 · Idea density for predicting Alzheimer’s disease from transcribed speech

- 类型：原始方法与应用论文
- 支持范围：DEPID、DEPID-R；基于聚类的 SID
- 书目／版本：Sirts, Piguet & Johnson (2017), CoNLL; arXiv:1706.04473
- [来源页面](https://aclanthology.org/K17-1033/)
- 核验边界：方法全文核对版本 https://arxiv.org/pdf/1706.04473 ，§§3–4、Table 2；不据临床任务结果提出诊断建议。

## R55 · Modeling Local Coherence: An Entity-Based Approach

- 类型：原始方法论文
- 支持范围：entity-grid 角色转移、共指、显著性
- 书目／版本：Barzilay & Lapata (2008), Computational Linguistics 34(1), 1–34; doi:10.1162/coli.2008.34.1.1
- [来源页面](https://aclanthology.org/J08-1001/)
- 核验边界：核对 §§3.1–3.3；长度、角色编码及 salience 都属于指标定义。

## R56 · Revisiting the Uniform Information Density Hypothesis

- 类型：方法比较及操作化论文
- 支持范围：五种非均匀性操作化
- 书目／版本：Meister et al. (2021), EMNLP, 963–980; doi:10.18653/v1/2021.emnlp-main.74
- [来源页面](https://aclanthology.org/2021.emnlp-main.74/)
- 核验边界：核对 §3.2 Eqs.(6)–(9)；区分句内方差、外部均值偏离和相邻差分。

## R57 · Grammaticality, Acceptability, and Probability

- 类型：原始比较研究
- 支持范围：SLOR 等语言模型可接受度评分
- 书目／版本：Lau, Clark & Lappin (2017), Cognitive Science 41, 1202–1241; doi:10.1111/cogs.12414
- [来源页面](https://jeyhan.my/files/2017-cogsci-grammaticality.pdf)
- 核验边界：核对 §3.2 p.1221；该文注明 SLOR 源于 Pauls & Klein (2012)，本轮尚未核对那篇原始提出文献。

## R58 · Masked Language Model Scoring

- 类型：原始方法论文
- 支持范围：PLL、pseudo-perplexity
- 书目／版本：Salazar et al. (2020), ACL; doi:10.18653/v1/2020.acl-main.240
- [来源页面](https://aclanthology.org/2020.acl-main.240/)
- 核验边界：核对 §2.1 PLL 与 §2.3 PPPL；不等同于因果 LM 的联合句概率。

## R59 · A Better Way to Do Masked Language Model Scoring

- 类型：原始修正论文
- 支持范围：PLL-word-l2r；同一词内部的子词泄漏
- 书目／版本：Kauf & Ivanova (2023), ACL Short Papers, 925–935; doi:10.18653/v1/2023.acl-short.80
- [来源页面](https://aclanthology.org/2023.acl-short.80/)
- 核验边界：核对正式摘要与搜索索引中的正文 §§1–3；整份 PDF 因读取大小限制未完整取得，代码实现仍待核验。

## R60 · Investigating minimum text lengths for lexical diversity indices

- 类型：原始比较研究
- 支持范围：MTLD 变体及文本长度敏感性
- 书目／版本：Zenker & Kyle (2021), Assessing Writing 47, 100505; doi:10.1016/j.asw.2020.100505
- [来源页面](https://www.sciencedirect.com/science/article/pii/S1075293520300660)
- 核验边界：本轮核对摘要与书目；操作规则另由 R61 维护者文档核对，不声称已复核全文算法或全部稳定长度结果。

## R61 · TAALED: MTLD variants

- 类型：工具维护者文档
- 支持范围：MTLD-MA-Bi 与 MTLD-MA-Wrap 的算法区别
- 书目／版本：LCR-ADS-Lab/TAALED README，MTLD (Original, MA-Bi, MA-Wrap) 节
- [来源页面](https://github.com/LCR-ADS-Lab/TAALED/blob/main/README.md)
- 核验边界：核对 moving-average 起点、双向与回绕规则；阈值、最短因子限制与极端短文本行为仍须锁定源码版本。

## R62 · Measuring burstiness for finite event sequences

- 类型：原始方法论文
- 支持范围：有限序列突发性 An；边界条件
- 书目／版本：Kim & Jo (2016), Physical Review E 94, 032311; doi:10.1103/PhysRevE.94.032311
- [来源页面](https://arxiv.org/pdf/1604.01125)
- 核验边界：核对 Eq.(22)、§II 及 Appendix A；原任务为事件时间序列，词位置应用属于迁移候选。

## R63 · Distinguishing between Positive and Negative Opinions with Complex Network Features

- 类型：原始语言网络应用论文
- 支持范围：词共现网络的度、强度、聚类、路径、效率、介数
- 书目／版本：Amancio et al. (2010), TextGraphs, 83–87
- [来源页面](https://aclanthology.org/W10-2313/)
- 核验边界：核对 §2.1 Eqs.(1)–(6)；原文为葡语新闻。图构造、权重和单邻居聚类边界需显式登记。

## R64 · AoA 2013 erratum and supplementary-data entry

- 类型：勘误页面与补充文件入口
- 支持范围：AoA 资源版本选择
- 书目／版本：Kuperman et al. (2013), BRM 45, 900; doi:10.3758/s13428-013-0348-8
- [来源页面](https://link.springer.com/article/10.3758/s13428-013-0348-8)
- 核验边界：已核对勘误记录及 XLSX 入口；本轮未读取附件内部单元格，不声称已逐词核验修正。

## R65 · all-mpnet-base-v2

- 类型：模型发布者模型卡
- 支持范围：英文句子与短段向量
- 书目／版本：sentence-transformers/all-mpnet-base-v2；768维；默认384 word pieces截断
- [来源页面](https://huggingface.co/sentence-transformers/all-mpnet-base-v2)
- 核验边界：核对用途、对比训练和输入上限；未下载权重或验证目标语料，选型为本目录建议。

## R66 · fastText multilingual Common Crawl/Wikipedia vectors

- 类型：官方模型说明
- 支持范围：静态词向量与词表外字串构向量
- 书目／版本：English cc.en.300.bin；300维；157语言系列
- [来源页面](https://fasttext.cc/docs/en/crawl-vectors.html)
- 核验边界：核对 .bin/.vec 差别与 OOV 支持；有输出不代表词义可靠，未下载模型。

## R67 · COCA word frequency data

- 类型：资源发布者说明
- 支持范围：分语域词频与lemma/wordform表
- 书目／版本：当前页列10亿词COCA、八大语域；全表有付费入口
- [来源页面](https://www.wordfrequency.info/)
- 核验边界：核对字段结构和访问范围；未购买、下载全表，也未接受网站的最准确等宣传主张。

## R68 · Academic Vocabulary List (AVL)

- 类型：作者资源页与下载说明
- 支持范围：学术词表与lemma级覆盖率
- 书目／版本：Gardner & Davies；3,000-lemma academic core；120M词学术子语料
- [来源页面](https://www.academicvocabulary.info/download.asp)
- 核验边界：同时核对首页 https://www.academicvocabulary.info/ ；学术用途可下载，原页不允许再分发词表，未下载词条。

## R69 · WordNet database format

- 类型：官方数据规范
- 支持范围：lemma+POS的synset计数与层级字段
- 书目／版本：wndb(5WN)
- [来源页面](https://wordnet.princeton.edu/documentation/wndb5wn)
- 核验边界：核对 sense/synset、词性和形态例外；不是上下文词义消歧算法。

## R70 · Pythia-410M-deduped

- 类型：模型发布者模型卡
- 支持范围：因果语言模型评分候选
- 书目／版本：EleutherAI/pythia-410m-deduped；拟用step143000，实施时固定commit
- [来源页面](https://huggingface.co/EleutherAI/pythia-410m-deduped)
- 核验边界：核对去重Pile、checkpoint及基础模型属性；未试跑，也未验证其人类加工拟合或最优性。

## R71 · Stanza available models

- 类型：官方文档
- 支持范围：UD标注模型备选路线
- 书目／版本：UD trained pipelines；默认可为多树库combined包
- [来源页面](https://stanfordnlp.github.io/stanza/available_models.html)
- 核验边界：核对UD模型与combined默认；具体英语包及版本须实施时锁定，不把语言名en当模型版本。

## R72 · spaCy English trained pipelines

- 类型：官方模型页
- 支持范围：英语标注候选
- 书目／版本：en_core_web_trf；页面说明web written text
- [来源页面](https://spacy.io/models/en)
- 核验边界：本轮页面无法加载GitHub release详情；只确认模型系列/用途，未据此声称最新版本或精度。

## R73 · GPT-2 model card

- 类型：模型卡
- 支持范围：历史因果LM评分对照
- 书目／版本：openai-community/gpt2；WebText；默认上下文1024 token
- [来源页面](https://huggingface.co/openai-community/gpt2)
- 核验边界：仅作为历史比较候选；训练数据未完整公开，未验证其指标在当前任务中优于其他模型。
