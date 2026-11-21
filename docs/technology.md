# 学术写作应用的技术选型

核查日期为 2026 年 11 月 21 日。首版可在用户上传的 DOCX 副本上调整样式，用公开书目索引返回可核对的论文条目。原生 Word 编辑和第三方全文再利用各有独立的接入条件。

## GenOffice 的格式引擎

核查使用 GenOffice 提交 `b90e7989d170b47b4cedbd02591c4b98595067a6`。其 DOCX 引擎单独维护文档解析、片段生成和段落补丁。样式管理代码会追踪 `w:basedOn` 和 `w:link` 依赖，处理导入后引用的样式 ID。对论文而言，只复制某个标题的显示名称无法复制其实际字体或段落间距。应用导入模板时，应解析继承关系或读取最终生效的属性。[包清单](https://github.com/genspark-ai/genoffice/blob/b90e7989d170b47b4cedbd02591c4b98595067a6/packages/docx-engine/package.json) · [样式管理](https://github.com/genspark-ai/genoffice/blob/b90e7989d170b47b4cedbd02591c4b98595067a6/packages/docx-engine/src/style-organizer.ts)

GenOffice 的补丁保存和文档检查分别处理章节、关系引用和字段等对象。对仅修改格式的功能，合适的验收方式是检查输出中正文及域指令内容、图片部件、页眉页脚关系是否保留，再用 Word 或兼容渲染器查看分页和视觉效果。仅验证文件可解压会遗漏字体回退、编号错误和分页变化。[补丁保存源码](https://github.com/genspark-ai/genoffice/blob/b90e7989d170b47b4cedbd02591c4b98595067a6/packages/docx-engine/src/patch.ts) · [文档检查源码](https://github.com/genspark-ai/genoffice/blob/b90e7989d170b47b4cedbd02591c4b98595067a6/packages/cli/src/formats/docx-check.ts)

GenOffice 社区代码及该 DOCX 包声明 Apache-2.0。按该许可分发时可保留应用自身代码的专有许可，并须履行许可证副本、适用权利声明、修改标记及 NOTICE 等相应义务。仓库的 `ee/` 有单独的企业许可，生产使用、托管或分发须取得 Mainfunc 企业协议。字体和传递依赖也有各自条款。首版采用独立的格式处理实现，本文引用源码供设计研究。[社区许可](https://github.com/genspark-ai/genoffice/blob/b90e7989d170b47b4cedbd02591c4b98595067a6/LICENSE) · [企业许可](https://github.com/genspark-ai/genoffice/blob/b90e7989d170b47b4cedbd02591c4b98595067a6/ee/LICENSE) · [第三方声明说明](https://github.com/genspark-ai/genoffice/blob/b90e7989d170b47b4cedbd02591c4b98595067a6/NOTICE)

## 与官方 Word 集成

| 目标 | 官方机制与产品决策 |
| --- | --- |
| 让作者在自己的 Word 中使用论文助手 | Office.js 任务窗格加载项可访问选区、段落和内容控件。可将来把用户批准的改写应用到选区，按目标平台检测 Word API requirement set。适用于已有 Word 客户端的用户。[Word 加载项概述](https://learn.microsoft.com/en-us/office/dev/add-ins/word/word-add-ins-programming-overview) |
| 在自家网站内提供微软的 Word 网页编辑器 | Microsoft 365 for the web 提供面向合格云存储厂商的 CSPP 合作渠道。获批后接入 WOPI、验证宿主并按协议运营，在线编辑涉及用户 Microsoft 365 许可。此路线需单独立项评估。[合作计划及许可](https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/online/overview) · [加入流程](https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/online/apply-for-cspp-program) |
| 按学校或期刊模板生成可用 Word 文件 | 在应用中处理 DOCX，用户通过自己的 Word 打开结果。保存页边距、段落、字符样式等属性时可以直接操作 Office Open XML。[微软的 WordprocessingML 文档结构](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document) |

## 文献来源和可复用范围

下表列出候选源及此次接口实测。接入状态以应用实际启用的来源为准。

| 来源 | 检索和实测结果 | 商用产品设计依据 |
| --- | --- | --- |
| Crossref | 用 `/works?query.bibliographic=…` 检索跨学科出版物。以 DNA sequencing 查询得到 HTTP 200、标题及文献记录。 | 基础书目事实可复用，出版商或作者可能保留摘要版权。保存题名、作者、年份、DOI，并提供原始落地页。可设置联系邮箱，依响应头限制并发和调用频率。[REST 接口](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) · [权利说明](https://www.crossref.org/documentation/retrieve-metadata/) · [配额](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) |
| Europe PMC | 以同一查询调用 EMBL-EBI 的 JSON 搜索接口，返回 HTTP 200 和生命科学论文；记录可带 DOI、PMID 或 PMCID。 | 免费阅读与商业再分发适用不同条件。结果可链接文献页；如后续做全文入库，使用允许自动获取的开放子集接口，按文章许可处理正文、插图及署名。[查询样例](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DNA%20sequencing&format=json&pageSize=2) · [版权说明](https://dev.europepmc.org/Copyright) |
| OpenAlex | `/works?search=水稻&filter=language:zh` 实测 HTTP 200，返回中文条目及 DOI。该语言字段指题名或摘要的语言。适合作为跨语种扩展，中文覆盖率仍需用目标学科的已知论文测试。 | 开放书目数据采用 CC0。基础请求可免密钥，规模使用涉及密钥、用量和预算。索引中的全文链接还需查看作品或具体版本的许可。[作品字段](https://help.openalex.org/data/works/attributes/) · [使用和价格](https://help.openalex.org/access/pricing/) · [认证](https://help.openalex.org/api/authentication/) |
| arXiv | 以 `ti:transformer` 查询 Atom API，返回 HTTP 200 和预印本记录。宜保留 arXiv ID、版本、来源链接及预印本标记。 | arXiv 将题名、作者、摘要等描述性元数据按 CC0 提供。托管论文文件须有对应许可；旧 API 跨所有受控机器合计一次只开一个连接，每三秒至多一次请求。[官方 API 条款](https://info.arxiv.org/help/api/tou.html) |

产品对外标明实际查询的索引和失败的来源，可以解释同一关键词为何得到不同范围的结果。跨源合并时优先用规范化 DOI；标题近似的预印本与期刊版应保留各自的来源和版本。作者看见原始条目后再纳入参考文献，AI 写作时可引用选中的记录。仅有题名时，不足以据此归纳论文的方法、样本或结论。
