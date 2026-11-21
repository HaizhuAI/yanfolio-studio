# 内置演示模板的来源与适配

三个文件均为 16∶9 的可编辑 PowerPoint 演示，每个文件内含封面、正文、双栏比较与收尾四张样板页。目录中的色彩、标题、正文、页脚和几何图形均可作为 PowerPoint 对象编辑。

| 文件 | 原始项目与版本 | 砚稿的适配 |
|---|---|---|
| academic-ribbon.pptx | Academic PPT Template Contributors 的[原生 academic-template.pptx](https://github.com/yctrrr/academic-ppt-template/blob/ac7c64f0d02704f87e863b39cf977b209cc0ca83/assets/academic-template.pptx)，MIT。[许可](https://github.com/yctrrr/academic-ppt-template/blob/ac7c64f0d02704f87e863b39cf977b209cc0ca83/LICENSE) | 从同版本 PPTX 克隆封面色带与章节通栏的可编辑形状，保留紫色基调；重组四种学术汇报页，以统一命名的中文文本框替换示例文案。 |
| gaia-seminar.pptx | Yuki Hattori 与 Marp Team 的 [Gaia 主题源文件](https://github.com/marp-team/marp-core/blob/01ef3a4ef0888403097e2c8f7988ea71c460cf97/themes/gaia.scss)，MIT。[许可](https://github.com/marp-team/marp-core/blob/01ef3a4ef0888403097e2c8f7988ea71c460cf97/LICENSE) | 将 lead 居中布局、蓝色主题场与暖白正文转换成 PowerPoint 原生形状；调整蓝色明度，增加适用于研究方法的双栏和讨论收尾。 |
| bricks-talk.pptx | iiiiiiinès 与 Slidev.js Team 的 [Bricks 主题](https://github.com/slidevjs/themes/tree/6bb2889af4c66c1fbab4c1beb2e8d962a3b55648/packages/theme-bricks)，MIT。[封面图形源](https://github.com/slidevjs/themes/blob/6bb2889af4c66c1fbab4c1beb2e8d962a3b55648/packages/theme-bricks/assets/page-1.svg) · [许可](https://github.com/slidevjs/themes/blob/6bb2889af4c66c1fbab4c1beb2e8d962a3b55648/LICENSE) | 按源主题的珊瑚、蓝与暖黄色以及积木构图，用独立的 PowerPoint 矩形和椭圆重绘模块图形，配套中文衬线标题。 |

各上游 MIT 许可全文随本目录分发。模板只引用字体名称，不附带 Microsoft YaHei 或 SimSun 字体文件。三个 WebP 预览由对应 PPTX 的实际封面渲染生成。

