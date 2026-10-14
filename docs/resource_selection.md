# 外部资源选型

选择依据是构念对应、语域匹配、可追溯性、覆盖和资源替换敏感性。以下是待实施的方案；实际文件哈希、匹配表现及运行成本仍需在资源取得后核验。

| 级别 | 用途 |
| --- | --- |
| A 优先建设 | 自身计数、SUBTLEX、AoA、具体性及统一标注底层 |
| B 按问题启用 | 特定语域、语义、形态、搭配或音系问题 |
| C 校准后启用 | 句编码器和因果语言模型评分 |
| D 平行复核 | 检验结论对资源／实现选择的敏感性 |
| E 暂缓默认 | 当前缺少问题匹配、口径或校准依据的方案 |

首批可解释词汇输出可保留SUBTLEX的Lg10WF和Lg10CD、AoA均值及具体性均值，同时保存每项覆盖和有效词数。Lg10WF是`log10(FREQcount+1)`，不要直接当成每百万词频率的对数。详细公式和匹配单位以CSV为准。

## 25项决策

| ID | 模块 | 级别 | 选定资源／方案 | 关联指标 | 来源ID |
| --- | --- | --- | --- | --- | --- |
| RS01 | 原文与语料自身计数 | A 优先建设 | 固定分词和标准化规则；频数/位置从研究语料本身计算 | LEN01,LEN02,LEN05,LEN06,LD01,LD07,LD08,LD09,INF01,QL01,QL02,QL03,QL04,QL08,QL09,QL10 | R03,R23,R29,R30,R32,R33 |
| RS02 | 通用参考词频与语境覆盖 | A 优先建设 | SUBTLEX-US完整版；优先保留Lg10WF、Lg10CD及原始计数 | FREQ01,FREQ02,FREQ04,FREQ05,FREQ06,FREQ09 | R08 |
| RS03 | 多源词频复核 | D 平行复核 | wordfreq英语large词表，固定软件和数据版本 | FREQ03,FREQ09 | R09 |
| RS04 | 语域与领域参照 | B 按问题启用 | 明确语域后使用COCA对应分区；专业领域优先可取得的匹配参照语料 | FREQ01,FREQ07,FREQ09 | R67 |
| RS05 | 学术词汇覆盖 | B 按问题启用 | AVL academic core的3,000 lemma版本 | FREQ08,FREQ09 | R68 |
| RS06 | 词汇习得年龄常模 | A 优先建设 | Kuperman et al. 2012 AoA，并以2013勘误附件为版本核验入口 | SEM01,FREQ09 | R10,R64 |
| RS07 | 具体性常模 | A 优先建设 | Brysbaert, Warriner & Kuperman 2014人工具体性评分 | SEM02,FREQ09 | R11 |
| RS08 | 感知运动语义 | B 按问题启用 | Lancaster Sensorimotor Norms | SEM08,FREQ09 | R12 |
| RS09 | 情绪词汇常模 | B 按问题启用 | NRC VAD v2.1（研究/教育适用范围）；复现旧文时保留其原版 | SEM05,SEM06,SEM07,FREQ09 | R13 |
| RS10 | 熟悉度与意象性 | E 暂缓默认 | MRC仅保留为候选或严格复现资源；本轮不选为通用默认 | SEM03,SEM04 | R07 |
| RS11 | 词典多义性 | B 按问题启用 | 固定Princeton WordNet发行版；实施时明确版本号 | SEM09 | R14,R69 |
| RS12 | 上下文义项与上位层级深度 | E 暂缓默认 | 取得可核验的词义消歧结果后再确定WordNet synset | SEM10 | R14,R69 |
| RS13 | 派生形态词典 | B 按问题启用 | MorphoLex-en原数据及数据字典 | MOR01,MOR02,MOR03,MOR04,MOR05,MOR06 | R15 |
| RS14 | 语境语义多样性 | B 按问题启用 | Hoffman et al.的原始SemD常模；再估计作为独立版本 | SEM11 | R39 |
| RS15 | 句子语义向量 | C 校准后启用 | sentence-transformers/all-mpnet-base-v2 | DIS08,DIS09,DIS10 | R65,R21,R35 |
| RS16 | 静态词向量 | B 按问题启用 | 需要词级分布语义时选fastText cc.en.300.bin；句级主方案见RS15 | DIS08,DIS09,DIS10 | R66,R35 |
| RS17 | 现成工具的coherence字段 | D 平行复核 | 保留TextDescriptives/TAACO的固定原配置作为对照 | DIS08,DIS09,DIS10 | R20,R21,R35 |
| RS18 | 因果语言模型评分 | C 校准后启用 | EleutherAI/pythia-410m-deduped，选step143000并在实施时固定commit | INF04,INF05,INF06,INF08 | R70,R22,R73 |
| RS19 | SLOR与掩码LM评分 | E 暂缓默认 | 仅在明确研究问题或严格复现时，分别锁定unigram基线或MLM及掩码规则 | INF09,INF10 | R57,R58,R59 |
| RS20 | 连接词词表 | B 按问题启用 | TAACO所选版本的连接表达清单与类别定义 | DIS04 | R20 |
| RS21 | 心理/语域/立场类别词典 | E 暂缓默认 | LIWC/MAT或人工词表按具体构念单独选；本轮不设通用默认类别库 | SEM12,STY01,STY04,STY05,STY06,STY07 | R25,R26 |
| RS22 | 搭配与词块参照语料 | B 按问题启用 | 具有共现及文档信息的独立匹配语料；语域确定后固定版本 | MWE01,MWE02,MWE03,MWE05,MWE06,MWE07,MWE08,FREQ10 | R36,R44,R45,R46,R47,R67 |
| RS23 | 词典发音 | B 按问题启用 | CMUdict固定版本 | LEN07,PHO01,PHO02 | R27 |
| RS24 | 基础词性与依存标注 | A 优先建设 | 英语实现先以spaCy en_core_web_trf为候选统一底层；严格UD问题另建Stanza固定包版本 | POS01,POS02,POS03,MOR07,DEP02,DEP03,DEP04,DEP05,DEP06,DIS05 | R35,R16,R71,R72 |
| RS25 | 共指与任务训练的语义单位 | E 暂缓默认 | 共指解析与SID聚类须按研究任务专门配置，不设全域通用默认 | DIS06,DIS07,DIS12 | R54,R55 |

完整理由、缺失处理和启用条件见[资源选型CSV](../data/external_resource_selection.csv)。来源ID见[来源索引](sources.md)。
