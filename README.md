# 砚稿 Yanfolio

商业闭源学术写作工作台，提供网页端、Windows x64 桌面端和运营后台。两端均需邮箱注册、验证并登录，使用同一账号的点数、手稿和文献夹。源码使用仓库中的专有许可。

## 官网、个人中心与云文档

官网位于 <http://127.0.0.1:8769/>。登录后可进入[个人中心](http://127.0.0.1:8769/profile.html)、[文档库](http://127.0.0.1:8769/drive.html)或[写作工作台](http://127.0.0.1:8769/studio)。新老账号默认获得 5 GB 文件配额，可上传、断点续传、保留版本、跨设备下载和恢复回收站文件。管理员可管理配额、查看存储卷剩余容量并远程暂停或恢复上传。[云资源架构、部署与恢复](docs/cloud.md)

界面 2.2 使用原创光学书页主视觉。官网可以试用改写、引文和排版对照；桌面端带有原生导航轨与应用图标。写作页面的“专注写作”可收起侧栏，Esc 退出。文档库支持把文件拖到当前文件夹。[设计参考与动效取舍](docs/interface-design.md)

## 本机使用

- 工作台 <http://127.0.0.1:8769/studio>，运营后台 <http://127.0.0.1:8769/admin.html>，兑换入口 <http://127.0.0.1:8769/wallet.html>。
- Windows 客户端位于 dist/Yanfolio.exe，可直接双击。默认连接本机。在“连接服务器”可改为运营方的 HTTPS 根地址。分发给另一台电脑时须能访问运营服务。
- Windows 启动 Web 服务需 Python 3.12 和 PowerShell。在项目目录运行以下命令。

~~~powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
~~~

当前机器已安装两款本地模型。新机器需要本地推理时，可先安装并校验模型与运行时；也可在启动前配置 YANFOLIO_AI_BASE_URL、YANFOLIO_AI_MODEL、YANFOLIO_AI_KEY，然后从后台新增接口。API 密钥只保存在服务端。

~~~powershell
python .\scripts\setup_local_model.py --modelscope --with-fast
python .\scripts\build_desktop.py --service-url http://127.0.0.1:8769
~~~

首次创建管理员需在服务端运行以下命令。生产使用真实运营邮箱并在交互提示中设置密码。本机验收也可以添加 --save-local-credentials，将随机密码写入服务私有数据目录的 admin-access.txt。公开注册的用户没有管理员权限。

~~~powershell
.\.venv\Scripts\python scripts\create_admin.py --email operator@example.com
~~~

**邮箱配置。** 设置 YANFOLIO_SMTP_HOST、YANFOLIO_SMTP_PORT、YANFOLIO_MAIL_FROM，按需设置 YANFOLIO_SMTP_USER 和 YANFOLIO_SMTP_PASSWORD。465 使用 TLS，其他端口使用 STARTTLS。本机无 SMTP 时，验证码写入 .local/service/mail，供设备所有者测试。公网注册与找回密码依赖实际发信服务。

## 运营与创作

1. 管理员在“模型与接口”增加兼容 Chat Completions 的服务，配置模型 ID、基础点数、千输入与千输出 Token 点数、输出上限。密钥支持替换和清除。点“测试”可检查上游模型列表。
2. 在“套餐与发码”设置面额和参考售价，按批生成并下载兑换码，在自己的渠道销售。用户进入“我的点数”兑换到账。后台可停用整批剩余的未兑码。
3. 用户新建或导入 Word 正文，选择写作模型、学科专家和专业程度。先查看最高扣点，再确认生成。普通模式调用一次，期刊评审包含草拟和复核两次调用。用户审阅后决定是否采纳。
4. 文献检索并发查询 Crossref、OpenAlex 和 Europe PMC，展示来源和故障状态，按 DOI 及规范化题名／年份去重。可收藏、插入编号引文并导出 Word。接口可配置 OPENALEX_API_KEY、CROSSREF_MAILTO。
5. 格式工作室支持 DOCX 原稿、DOCX／DOTX 模板和 TXT／DOCX／文字型 PDF 要求。预检展示影响范围、最终格式和待确认原句。需要保留域、表格、公式和图片时，使用原始 DOCX 套版。复杂分节、目录和最终分页请用正式模板在 Word 中复核。

可粘贴的格式规则示例：

~~~text
正文：宋体，Times New Roman，小四，1.5 倍行距，首行缩进两个字符
一级标题：黑体，三号，加粗，居中
上边距 2.5 cm，左边距 3 cm
A4 纵向
~~~

## 公网部署

deploy/compose.yaml 提供 Caddy HTTPS、单实例 API 服务和持久化卷。将域名 DNS 指向部署主机，在部署环境中设置 YANFOLIO_DOMAIN、SMTP 参数和首个模型接口。生产只给反向代理开放 80/443，应用使用服务网络中的内部端口。容器的本机地址指容器本身，宿主机模型应配置为容器可达的受控地址。首次启动后初始化运营账号：

~~~sh
docker compose -f deploy/compose.yaml up -d --build
docker compose -f deploy/compose.yaml exec app python scripts/create_admin.py --email operator@example.com
~~~

运行 python scripts/build_web.py 可生成运营交付包 dist/Yanfolio-Web.zip，其中包括服务端、网页和部署文件，以及已构建的桌面程序。网站登录页可下载 Windows 客户端。交付包限运营方持有。

构建面向客户的桌面程序时，将 --service-url 改为已部署的 HTTPS 地址。Windows 客户端需 WebView2 Evergreen。数据库、主密钥、验证码、管理员凭据、上游模型权重与构建产物均排除在源码同步范围外。[完整架构、结算与备份](docs/architecture.md)

## 开发验证与源码同步

Windows 登录任务 Yanfolio-PrivateSourceSync 监控允许的源码路径。编辑稳定约 3 秒后自动提交并向私有 GitHub origin 推送，网络故障会重试。检测到手动暂存、切换分支或远端分叉会暂缓；日志在 .git/yanfolio-sync.log。新工作站配置 Git 作者、GitHub 凭据并克隆私有仓库后，可运行 scripts/install-sync.ps1。

~~~powershell
.\.venv\Scripts\python -m pip install pytest
.\.venv\Scripts\python -m pytest -q
~~~

[21 条资料与项目文件核对](docs/references.md) · [技术选型与许可证](docs/technology.md) · [源码专有许可](LICENSE)

FastAPI、Uvicorn、httpx、cryptography、python-docx、lxml、pypdf、WebView2 SDK 等组件保留各自许可。客户端包含 WebView2 SDK 的 LICENSE.txt。模型和 llama.cpp 运行时由构建脚本从各自项目下载并校验，不随客户 EXE 分发。

