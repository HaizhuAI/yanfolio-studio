# 砚稿内置中文字体

两款字体来自 Google Fonts 的 Noto CJK 简体中文发行文件。构建时固定上游提交，保留完整可变字体的字形、Unicode 字符映射、字重轴和排版表，以 WOFF2 在本机服务或部署服务器提供。浏览器和桌面 WebView2 都可以在用户选择相应字族时加载文件。[Noto CJK 官方项目](https://github.com/notofonts/noto-cjk)

| 字族 | 字体版本 | 字重范围 | WOFF2 字节 | 字形数 | Unicode 映射数 | GB 2312 汉字覆盖 | 来源与许可 |
|---|---|---|---:|---:|---:|---:|---|
| Noto Sans SC | 2.004-H2 | 100–900 | 9,280,668 | 31,036 | 30,890 | 6,763 / 6,763 | [发行文件](https://github.com/google/fonts/tree/06bfe0d62a98375cb09c942fa18e68bd32cff057/ofl/notosanssc) · [原始许可](noto-sans-sc-OFL.txt) |
| Noto Serif SC | 2.003-H1 | 200–900 | 13,046,176 | 31,058 | 30,928 | 6,763 / 6,763 | [发行文件](https://github.com/google/fonts/tree/06bfe0d62a98375cb09c942fa18e68bd32cff057/ofl/notoserifsc) · [原始许可](noto-serif-sc-OFL.txt) |

字形数含同一字符的替换字形等内部条目。Unicode 映射数取自最完整的 Unicode cmap。GB 2312 覆盖按其双字节汉字区逐个解码并与 cmap 比对。两款均覆盖常用简体汉字、许多扩展区汉字及部分拉丁字母和希腊字母。超出字库的字符由浏览器回退字体显示。

## 文件来源与校验

- Noto Sans SC 的原始文件为 `NotoSansSC[wght].ttf`，Git Blob `fb0637bafbcd804fe32152370a1225990745b4bc`。原始 SHA-256 为 `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`，交付的 `noto-sans-sc.woff2` 为 `f685e068e013298945ea2b0de797b6b85f68d1aa69cacf3e7c4eb3292934bc0b`。
- Noto Serif SC 的原始文件为 `NotoSerifSC[wght].ttf`，Git Blob `eab063faf229160a52d3760f5555150e4eb9e5bf`。原始 SHA-256 为 `050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9`，交付的 `noto-serif-sc.woff2` 为 `986ce6f38425505cded3eeecf7f3b0071ad1383b52b48770b21f4a8c97595999`。

两款字体均按 SIL Open Font License 1.1 分发，随包保留各自原始英文版权及许可证。该许可允许字体随软件捆绑、嵌入及再分发。修改、单独销售和保留字体名称等条款以对应上游原文为准。[SIL OFL 1.1 正文](https://openfontlicense.org/open-font-license-official-text/)
