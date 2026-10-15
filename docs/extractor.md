# LingMetrics 使用说明

LingMetrics 0.1.0 为 Apple Silicon、macOS 13 及以上的组内测试应用。自带 Python 3.11 和固定英语基础模型。应用源代码与研究目录放在同一仓库；目录的核验状态和程序的计算状态分别记录。

## 开始提取

1. 解压安装包，将 LingMetrics.app 放到方便的位置，双击打开。可先点“载入示例”，直接运行自带英文样例。组内测试包采用本地签名；macOS 如要求来源确认，使用系统提供的正常确认流程。
2. 添加 TXT、文件夹或 CSV。默认 UTF-8/BOM；CSV 选择文本列，支持字段内换行和引号。可附 `doc_id`、`group_id`、`section_id`、`pair_id`。
3. 选择指标。默认“常用组合”适合先检查长度、词性、依存和词汇多样性；全库条目包括需资源及方法待核项目。
4. 选择专属输出目录。开始后可取消；相同输入、参数、资源与版本可在原目录续算。
5. 用 `feature_status.csv` 检查缺失原因，再将 `features.csv` 用于研究。

## 输出

- `features.csv`：文档指标及原CSV元数据。
- `feature_status.csv`：每文档、每条目的计算状态及原因。
- `tokens.csv`、`sentences.csv`、`word_frequency.csv`：细粒度结果。
- `details/`：所选方法实际产生的边、树、词表匹配和模型评分。
- `corpus_features.csv`、`corpus/`：语料层曲线、分布与拟合。不要当成独立文档观测重复入模。
- `field_dictionary.csv`、`execution_manifest.json`、`run.json`：定义、配置、来源、版本、资源哈希和结果校验值。
- `.checkpoint/`：续算文件，包含解析结果和原文信息；保留在本机，不纳入应用分发。

缺失字段为空，状态表区分 `partial`、`undefined`、`resource_required`、`input_required`、`coverage_insufficient`、`method_pending` 和 `error`。部分缺失会列出具体列名。零值只在定义成立时输出。177 个目录条目包含指标族，因此不对应固定177列。

## 默认口径

基础模型 spaCy en_core_web_sm 3.8.0；大小写折叠词形；标点不计入词数；词性、句界和依存使用固定模型。lemma模式另存配置，避免与词形结果混合。字符位置以Unicode codepoint计；Apple校对器位置以UTF-16计并单独标明。

MATTR/MSTTR窗口50；MSTTR丢弃末尾不完整块。MTLD双向平均、阈值0.72；HD-D抽样42词；短于窗口/样本的文本返回无定义。Maas使用自然对数并在列名中注明。voc-D使用35–50词无放回抽样、100次、三轮拟合平均，随机种子1729；不是未声明版本的CLAN结果。

依存完整树包含解析标点节点，排除ROOT自环；边长按句内位置差；中间词数版本另列。z分数是明确命名的Monte Carlo估计，默认1000次。最小长度采用无约束同树排列；小树可精确穷举，大树需要精确助手。

原始Penn PTB成分树与spaCy分词分别标识。L2SCA保留上游结构查询、去重计数和词数正则。Yngve/Frazier保留树结构，EDITED子树不参与复杂度评分；自动树通常不含人工空NP。细粒度SYN18–20为明确命名的spaCy依存操作化，SYN21为直接ADVP/PP附件计数，不冒称TAASSC所有版本等价。

CMUdict默认取词典第一发音，未命中不估补音节。音节可读性严格要求完整覆盖；SMOG标准模式需至少30句。Fog列明确使用词典多音节词并排除PROPN，须区别于带其他例外规则的实现。

相邻词对在句内取有序位置，关联量的两个边际都来自同一对位置总体。DP以section_id分块，无此列时以文档分块；使用2012勘误归一化。网络为有向二值路径，强度另存；度<2聚类置0为本实现明确补充约定，不可达路径均值无定义、效率贡献0。

Zipf、Zipf–Mandelbrot、Heaps输出描述性非线性拟合及协方差。它们不能单独证明总体服从幂律；推断性模型比较、尾部筛选和重采样应在研究计划中另定。复现序列按输入顺序连接，开放边界B与周期边界An分列。

模型默认CPU，固定资源修订后离线评分。MPNet对超过384子词的句/段返回输入条件不足，避免静默截断。fastText备选后端为300维词向量的词次均值再L2归一化，保留.bin的子词OOV能力；两种后端分别命名。

因果模型每个子词只计分一次，词级聚合检查偏移重叠；SLOR另按去标点、小写词形序列评分，与同单位的unigram参照配合。PLL按句逐token掩码、排除特殊token。word-l2r、MTLD-MA及若干原方法细节仍在对应操作化状态中注明。

## 高级参数

高级参数为JSON对象，可设置 `hdd_sample`、`mtld_threshold`、`random_permutations`、`low_frequency_pm`、`frequency_bands`、`bundle_order`、`bundle_min_frequency`、`bundle_min_documents`、`taylor_window`、`character_ngram_order`、`network_max_nodes`、`uid_power`、`uid_reference_mean`、`morphological_process`、`wordnet_senses`。

WordNet深度需要明确synset选择，如 `{"wordnet_senses":{"dog":"dog.n.01"}}`。默认语料网络上限2000词型；超出时要求指定较小语料或显式提高上限。参数全部写入run.json。

## 构建与验证

开发者使用 `python3 scripts/build_macos.py` 构建；基础环境隔离在系统临时目录，可用 `LINGMETRICS_BUILD_DIR` 指定位置，成品在 `dist/`。组员只需要应用。核心测试为 `PYTHONPATH=engine:engine/vendor python3 -m unittest discover -s tests`；研究目录仍使用原有校验脚本。
