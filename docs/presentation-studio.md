# 学术演示制作与工作台外观

## 制作演示稿

在网页 /slides、工作台侧栏的“PPT 制作”，或 Windows 客户端的“演示”入口打开演示库。选择模板后，可以用题目创建封面、把已有段落分页，也可以从已保存的论文手稿带入文字与题录。论文页的“文件 → 用手稿制作 PPT”可以带入正在编辑的内容。

**直接建稿**用于手动编排，创建、编辑、放映、下载模板及导出均免写作点数。**AI 起草**支持 3 至 8 页，先选择模型、材料和页数，查看本次最高预留点数后确认。服务端验证模型的结构化页稿及 PowerPoint 版式后，在同一个事务内保存草稿、结算调用与记录流水。相同任务号可幂等重试，失败会退回预留点数。生成的学术判断和论据由作者复核。

编辑器提供封面、正文、双栏、收尾四种版式。可以拖动页序缩略图，也可以用按钮增加、复制、前移、后移和移除页面，修改文字与讲者备注，切换模板，逐页放映。演示草稿在账号内单独保存，更新带版本号；出现跨设备冲突时可保留本机副本。每份最多 32 页，账号内最多 250 份草稿，结构化草稿总量上限为 12 MB。桌面与网页读取同一草稿。

导出文件为可编辑的 16:9 PowerPoint。PowerPoint 文本框、原生装饰形状与讲者备注保存在 PPTX 中。页内文本按模板空间进行换行和字号适配；仍然过密时，预览会提示作者拆页或精简。编辑器预览按模板几何和文本属性绘制，最终字体替换和字形度量以接收端的 PowerPoint 为准。

独立 PPTX 可以下载或存入 5 GB 云文档。外部 PPTX 可导入文字及讲者备注后重新套版，图片、图表、嵌入对象、动画和任意外部排版留在原文件中。导入上限 16 MB、32 页；优先从砚稿导出稿恢复可识别的版式和字段。超过可编辑字段容量的原稿会提示拆分。

## 内置模板与字体

| 模板 | 使用场景 | 来源 |
|---|---|---|
| 紫带答辩 | 开题、学位答辩、证据对照 | 适配原生 [Academic PPT Template](https://github.com/yctrrr/academic-ppt-template)，沿用可编辑的通栏色带。 |
| Gaia 研讨 | 组会、研究进度汇报 | 将 [Marp Gaia](https://github.com/marp-team/marp-core/tree/main/themes) 的主旨页和正文主题适配为 PowerPoint 原生对象。 |
| 几何讲堂 | 课程报告、跨学科讲座 | 将 [Slidev Bricks](https://github.com/slidevjs/themes/tree/main/packages/theme-bricks) 的模块构图适配为可编辑矩形和椭圆。 |

每套模板有四张可下载的样板页。三份固定版本的来源与 MIT 许可随运营包提供；导出的 PPTX 在文档自定义属性中携带所用模板的许可通知。[模板来源与适配记录](../app/deck_assets/SOURCES.md)

“外观设置”可分别选择系统、浅色或深色，默认跟随系统，并响应运行时的系统变化。可以分别设置界面字体、手稿正文字体和字号。在已登录状态下保存到账号，下次在另一端登录也能取得设置。Windows 原生导航接受同源页面的两种配色通知，标题栏着色取决于 Windows 版本。界面字体选择作用于网页与 WebView 工作区，原生菜单采用系统字体。

Geist、Noto Sans SC 和 Noto Serif SC 均在本服务自托管。两份中文 WOFF2 保留上游可变字重，各覆盖 GB 2312 全部 6,763 个汉字；第一次选择时才加载对应字体。界面的外观选择与幻灯片模板的导出字体独立。[中文字体许可、覆盖与校验值](../app/static/fonts/SOURCES.md)

## 布局取舍

- **正文与辅助工具。** Overleaf 允许控制各个编辑面板的可见性，Notion 可在选区触发 AI 编辑。砚稿将目录做成可折叠区域，写作助手和文献夹按需打开，共用一个面板；低频文件操作收进“文件”。[Overleaf 编辑器布局](https://docs.overleaf.com/getting-started/how-do-i-use-overleaf/redesigned-overleaf-editor) · [Notion AI 选区编辑](https://www.notion.com/help/notion-ai-faqs)
- **页序与内容分工。** Gamma 的左侧页条用于管理页面顺序、复制和移除。砚稿将这些动作放在页序与本页工具中，中间保留当前页预览，右侧只展示所选版式实际需要的字段。[Gamma 页序管理](https://help.gamma.app/en/articles/11016403-how-does-the-filmstrip-in-gamma-work)
- **从材料到演示。** Gamma 区分生成、粘贴和导入，PowerPoint Copilot 支持围绕主题或源材料创建演示。砚稿把手工分页与按点数生成初稿明确区分，生成前展示页数和报价，生成后允许逐页改写。[Gamma 创建流程](https://help.gamma.app/en/articles/7838093-how-do-i-create-a-new-presentation-document-or-webpage-in-gamma) · [PowerPoint Copilot](https://support.microsoft.com/en-us/powerpoint/copilot/create-a-new-presentation-with-copilot-in-powerpoint)

