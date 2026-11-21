# 砚稿界面改版参考

2026 年 11 月 21 日按具体任务从去重后的资源清单中取样。官网需要让访客亲手对比一段修改，编辑器需要让作者连续阅读，桌面导航需要让人记住常用目的地。三个场景适合不同的视觉密度和动作幅度。

| 场景 | 从案例得到的设计取舍 |
|---|---|
| 官网主视觉 | Crest 把单一物体、反射面与光源组织成可辨认的空间。砚稿选用书页作主体，以银蓝边缘和层间阴影表达纸页起伏，标题放在稳定的暗部。该示例标为 Premium，商用许可随会员提供。[HorizonX · Crest Water Hero](https://horizonx.so/explore/crest-water-hero) |
| 手稿演示 | Compare 用同一窗口展示两个版本，并提供拖动、悬停和自动播放。用于论文时，在同一段原文上呈现两种排版，让读者拖动分界，比较字号、对齐与缩进。润色采用可采纳和撤销的逐句标记。键盘方向键和触屏均应能完成比较。[Aceternity · Compare](https://ui.aceternity.com/components/compare) |
| 登录与状态反馈 | Bencho 的密码示例将可见性变化放在眼睛按钮旁。Transitions 的文字状态切换在原位置换入下一条消息。对应砚稿，短反馈放在正在操作的控件上。编辑器的同步状态留出固定宽度，避免更换几个字就推移整排操作。[Bencho · Password reveal](https://bencho.dev/blocks/pass-reveal) · [Transitions · Text states swap](https://transitions.dev/studio.html?lib=text-states-swap) |
| 桌面导航与上传 | BoardUI 侧栏把常用导航、快捷动作与账户操作分层；上传示例同时考虑键盘选择、类型校验和进度。砚稿的桌面轨应始终标出当前页面，云文档的上传进度取自服务端确认的字节数，失败或暂停仍能看见文件名。[BoardUI · Sidebar](https://www.boardui.com/components/sidebar) · [File Upload](https://www.boardui.com/components/file-upload) |
| 字形与数值 | Typewolf 收录的 Dirty Vine 同时使用 Swear 与 DM Mono。砚稿借用按信息用途分配字形的方法：标题以字号和字重建立层级，容量、点数、时间使用等宽数字，中文正文优先选择终端上可稳定显示的字形。[Typewolf · Dirty Vine](https://www.typewolf.com/site-of-the-day/dirty-vine) |
| 图标与动作 | Lucide 明确规定统一图标画布和安全边距。Anime.js 的时间线可安排动作顺序，其媒体查询示例也演示了如何响应减少动态效果的偏好。桌面和网页可据此统一图标笔画、控制面板切换顺序，并给减少动态效果的用户提供同样可辨认的选中和完成状态。[Lucide · 设计语言](https://lucide.dev/contribute/icons/design-principles) · [Anime.js · Timeline](https://animejs.com/documentation/timeline) · [媒体查询](https://animejs.com/documentation/scope/scope-parameters/mediaqueries/) |

60fps 将手机交互拆成连续画面，适合检查操作前、按下时、完成后三个时刻。砚稿的验收重点是焦点仍可定位、手稿仍可阅读、余额或用量的最终值与服务端一致。案例页中的字体和视觉素材有各自的分发条件；上表记录观察与设计取舍，相关模板、字体文件和示例源码均未随本调研引入。[60fps · Storyboards](https://60fps.design/storyboards)

## 本版随包组件

官网的书页切换和标题入场使用 Anime.js 4.5.0；发行包内脚本保留官方 MIT 声明。Geist 可变字体从 Vercel 的固定提交取得，并在同目录提供 OFL 许可证。中文正文采用系统中文字体。书页主视觉、应用图标、原生窗口导航和页面组件为砚稿定制。[Anime.js](https://github.com/juliangarnier/anime) · [Geist 对应提交](https://github.com/vercel/geist-font/tree/ef2597cfc42f4797676df105517ccc0a1cfa6569)
