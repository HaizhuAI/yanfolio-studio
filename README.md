# 砚稿 Yanfolio

砚稿是面向个人研究者的中文学术写作工作台。可以从研究问题或已有 Word 正文开始写，在检索到的题录中选择引文，再用学校或期刊的模板生成 Word 副本。应用源码采用专有许可，仓库设为私有。当前交付为本机单用户版本。

## 在 Windows 启动

需要 Python 3.12 和 PowerShell。在项目目录运行以下命令。首次启动会建立虚拟环境并安装依赖。应用地址为 <http://127.0.0.1:8769/>。

~~~powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
~~~

**本机推理。** 在 Windows x64 上，可以先运行以下命令安装 llama.cpp CPU 运行时与 Qwen2.5-1.5B-Instruct 量化权重。下载约 1.15 GB，安装期间预留 3 GB 空间。下载文件会校验固定的 SHA-256。国内可选 Qwen 的 ModelScope 镜像。安装后再次启动应用，启动脚本会在回环地址启动模型。该小模型适合短段落起草、润色和工作流验证，学术判断和引文需作者核对。

~~~powershell
python .\scripts\setup_local_model.py --modelscope
powershell -ExecutionPolicy Bypass -File .\start.ps1
~~~

**自选模型。** 启动前可设置以下进程环境变量，连接支持 Chat Completions 的文本服务。设置了地址时优先使用指定服务。在服务端设置该供应商需要的 API 密钥。写作界面会显示配置的模型。使用外部服务时，点“生成建议”会发送标题、任务要求、选中文字或正文，以及本文已引用的题录。

~~~powershell
$env:YANFOLIO_AI_BASE_URL = 'https://your-provider.example/v1'
$env:YANFOLIO_AI_MODEL = 'your-model-id'
# 如供应商需要鉴权，在运行环境中配置 YANFOLIO_AI_KEY
.\start.ps1
~~~

## 从检索到排版

1. 在“论文创作”新建手稿，或用“导入正文”从 DOCX 提取标题和段落。导入用于文字创作。需要保留表格、公式、图片、脚注或引文字段时，将原始 DOCX 直接交给“格式工作室”。
2. 在“文献检索”输入中文或英文题名、主题、作者或 DOI，可选起始年份和来源。三个学术索引并发请求，显示各源状态，按 DOI 和规范化题名／年份去重。点题名打开原始记录，点“存入文献夹”收藏。匿名检索可能触发上游限流。可在服务端配置 OPENALEX_API_KEY 和 CROSSREF_MAILTO。
3. 在文献夹点“插入引文”，按首次使用分配编号。同一篇题录在同一手稿中复用编号，导出的 Word 包含对应参考文献表。题录用于核定文献身份，核实论断仍需阅读原文。当前覆盖学术元数据，不含知网、万方等订阅库和付费全文代理。
4. 选择段落后执行学术润色、拟定大纲、段落起草或同行评阅。先审阅模型输出，再决定替换选区、替换正文或追加到文末。可撤销刚刚采纳的建议。原稿改变后，需要重新生成。单次选区上限为 20,000 字，具体可处理长度还受模型上下文限制。
5. 在“格式工作室”上传 DOCX 原稿，或使用当前手稿。添加 DOCX／DOTX 模板、TXT／DOCX／文字型 PDF 要求，或直接粘贴规则。预检后查看影响范围和未识别原句，再下载排版副本。

### 格式规则与模板

下列各行可直接粘贴到“补充规则”。一行指定一个目标，避免在同一行混写多个标题级别。文件要求先于手动补充要求读取，后面的同一属性覆盖前面；明确识别出的文字要求覆盖模板。

~~~text
正文：宋体，Times New Roman，小四，1.5 倍行距，首行缩进两个字符
一级标题：黑体，三号，加粗，居中
二级标题：黑体，小四，加粗，段前 6 磅
上边距 2.5 cm，左边距 3 cm
A4 纵向
~~~

模板解析 Word 段落样式继承链，按论文标题、三级标题、正文、题注和参考文献条目选择最常见的代表性排版。读取明确记录的中西文字体、字号、段落对齐、间距、缩进及页面尺寸和边距。含多个节的模板使用末节页面参数，预检会提示。规则落在原稿顶层的匹配段落上，表格、页眉、页脚、域、媒体及关系保留在原包中。主题字体、复杂体例、目录更新、扫描 PDF 的 OCR、页眉页脚移植和任意版式仿制需要作者在 Word 中处理。两栏、奇偶页或复杂分节的成稿应逐页检查。

草稿和文献夹保存在当前浏览器的本地存储。清理浏览器数据会移除草稿。Word 上传文件在本机服务内存中处理，下载后可用桌面 Word 打开。原稿和模型权重均在 Git 同步范围之外。

## 源码同步

Windows 登录任务 Yanfolio-PrivateSourceSync 检查源文件的变化，保存停止约 3 秒后提交并推送到当前私有 GitHub origin。网络延迟会影响到达时间。检测到正在手动暂存、合并、变基或切换分支时暂缓推送；远程分支分叉需人工合并。任务会重试断网或认证错误，使用 Git Credential Manager 或 gh 的当前账号，每次推送前核查 GitHub 私有可见性。允许同步的文件路径见 scripts/sync.py。聊天内容、上传文件、运行日志、密钥配置、虚拟环境和本地模型均没有同步入口。

~~~powershell
# 在新机器上登录 GitHub、配置 Git 作者信息并克隆自己的私有仓库后运行
powershell -ExecutionPolicy Bypass -File .\scripts\install-sync.ps1
Get-ScheduledTask -TaskName Yanfolio-PrivateSourceSync
Get-Content .git\yanfolio-sync.log -Tail 5
~~~

## 核对与测试

[21 条参考材料和项目文件核对](docs/references.md) · [技术选型与第三方许可](docs/technology.md) · [源码专有许可](LICENSE)

应用使用 FastAPI、Starlette、Uvicorn、httpx、python-multipart、python-docx、lxml 和 pypdf。第三方包保留各自的发行许可。模型和推理运行时按需从各自项目下载，原始许可证见 [Qwen 模型仓库](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9) 和 [llama.cpp 对应版本](https://github.com/ggml-org/llama.cpp/tree/b8241)。向客户重新分发第三方程序或权重时，应随包保留相应许可证与 notices。

运行回归测试需在项目虚拟环境中额外安装 pytest。测试用程序生成含图片、表格、页眉、交叉引用域和公式的稿件，验证包部件、正文、规则优先级、Word 再打开、检索降级和去重。

~~~powershell
.\.venv\Scripts\python -m pip install pytest
.\.venv\Scripts\python -m pytest -q
~~~

