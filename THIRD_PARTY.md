# Third-party components

LingMetrics uses a relocatable CPython runtime, NumPy, spaCy, en_core_web_sm, CMUdict and their dependencies. Their upstream license files remain inside the app's runtime and site-packages directories. The resolved versions are listed in `requirements-core.lock`.

The pure Python tree-search subset under `engine/vendor/neosca` comes from [Tan Long's NeoSCA](https://github.com/tanloong/neosca), a fork of Xiaofei Lu's L2SCA. It includes GPL-3.0 code and adaptations of Stanford CoreNLP tree utilities. The original GPL text and per-file hashes are included under that directory and in `engine/vendor/provenance.json`. No Qt GUI, PyInstaller runtime or Java parser is included. LingMetrics distribution containing this subset is subject to GPL-3.0; corresponding application source accompanies the test distribution in this private repository. This notice does not assign a new license to the existing research catalogue or to third-party data.

Optional models, norms, WordNet, fastText, LAL and zipfR retain their respective licenses. They are acquired separately and their identities are recorded in each run. Imported research data is not included in a source or application distribution.

The distribution also contains the LAL v24.10 minimum-arrangement API (AGPL-3.0), a protocol wrapper, GMP 6.2.1 (GPL/LGPL) and LLVM OpenMP 14.0.6 (Apache-2.0 with LLVM exception). The combined application distribution is governed by AGPL-3.0 where applicable. Corresponding source archives and license texts accompany the native helper archive. Its minimum API is compiled from unmodified upstream sources; unrelated maximum-arrangement components are excluded.

The fastText v0.9.2 command-line helper is MIT-licensed; its source archive and license accompany its native archive. Pretrained `cc.en.300.bin` weights are imported separately.
