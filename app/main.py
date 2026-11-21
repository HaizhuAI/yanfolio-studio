from contextlib import asynccontextmanager
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool

from . import formatting, literature, accounts, agent, commerce, control, store
from .agent import Manuscript

@asynccontextmanager
async def lifespan(app):
    store.init()
    with store.db(True) as c:
        agent.expire(c)
    yield


app = FastAPI(title="砚稿 Yanfolio", docs_url=None, redoc_url=None, openapi_url=None,lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_fields(request, exc):
    fields=", ".join(".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()[:5])
    return JSONResponse({"detail":"输入字段格式有误："+fields},422)


for router in (accounts.router,agent.router,commerce.router,control.router):
    app.include_router(router)
TYPES = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
FILES_MAX = 16*1024*1024
PUBLIC = {"/login.html","/login.js","/common.js","/style.css","/account.css","/health",
          "/api/auth/code","/api/auth/register","/api/auth/login","/api/auth/reset","/api/auth/options","/desktop/download"}


@app.middleware("http")
async def access(request, call_next):
    public_url=store.public_origin()
    configured=urlparse(public_url)
    allowed={configured.hostname}
    if configured.hostname in {"localhost","127.0.0.1","::1"}:
        allowed.update({"localhost","127.0.0.1","::1","testserver"})
    if request.url.hostname not in allowed:
        return JSONResponse({"detail":"服务域名不匹配。"},403)
    origin=request.headers.get("origin")
    same_origin={f"{request.url.scheme}://{request.headers.get('host')}",public_url}
    if origin and origin not in same_origin:
        return JSONResponse({"detail":"仅接受本站请求。"},403)
    path=request.url.path
    if request.method in ("POST","PUT","PATCH","DELETE"):
        if request.headers.get("x-yanfolio-request")!="1":
            return JSONResponse({"detail":"缺少客户端请求标记。"},403)
        try:
            length=int(request.headers["content-length"])
        except (KeyError,ValueError):
            return JSONResponse({"detail":"需要指定上传大小。"},411)
        if not 0<=length<=40*1024*1024:
            return JSONResponse({"detail":"单次请求最多 40 MB。"},413)
    if path not in PUBLIC:
        user=await run_in_threadpool(accounts.identity,request)
        if user is None:
            if path.startswith("/api/"):
                return JSONResponse({"detail":"请先登录。"},401)
            target="/login.html?next="+path if path in ("/admin.html","/wallet.html") else "/login.html"
            return RedirectResponse(target,303,headers={"Cache-Control":"no-store"})
        if (path.startswith("/api/admin/") or path in ("/admin.html","/admin.js")) and user["role"]!="admin":
            return JSONResponse({"detail":"需要管理员权限。"},403)
        expected=request.headers.get("x-yanfolio-account")
        if expected and expected!=str(user["id"]):
            return JSONResponse({"detail":"登录账号已变更，请重新打开工作台。"},409)
        request.state.user=user
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Cache-Control"]="no-store"
    response.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


@app.get("/health")
def health():
    return {"service":"yanfolio","ok":True}


def desktop_binary():
    return Path(os.getenv("YANFOLIO_DESKTOP_FILE",store.ROOT/"dist"/"Yanfolio.exe"))


@app.get("/api/auth/options")
def public_options():
    return {"desktop":desktop_binary().is_file()}


@app.get("/desktop/download")
def desktop_download():
    binary=desktop_binary()
    if not binary.is_file():
        raise HTTPException(404,"运营方尚未提供桌面发行包。")
    return FileResponse(binary,filename="Yanfolio.exe",media_type="application/octet-stream")


@app.get("/api/status")
def status():
    return {"sources":literature.SOURCES}


@app.get("/api/search")
async def search(q: str, source: str = "all", year: int | None = None):
    q = q.strip()
    if not 1<=len(q)<=300 or source not in ("all",*literature.SOURCES) or (year and not 1500<=year<=2200):
        raise HTTPException(422,"请输入有效检索词、文献来源及起始年份。")
    return await literature.search(q, source, year)


async def read_file(file, allowed, limit=FILES_MAX):
    if not file:
        return None
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(422,"允许的文件类型为 " + "、".join(allowed))
    data = await file.read(limit+1)
    if len(data)>limit:
        raise HTTPException(413,f"单个文件最多 {limit//1024//1024} MB。")
    if not data:
        raise HTTPException(422,"文件为空。")
    return data


def read_instructions(filename, data):
    if filename.lower().endswith(".docx"):
        doc = formatting.Package(data)
        text = "\n".join(formatting.content(p) for p in doc.doc.xpath("/w:document/w:body//w:p",namespaces=formatting.NS))
    elif filename.lower().endswith(".pdf"):
        try:
            pdf = PdfReader(BytesIO(data))
            if pdf.is_encrypted or len(pdf.pages)>40:
                raise ValueError
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as exc:
            raise ValueError("请上传不超过 40 页的未加密文字型 PDF。") from exc
        if not text.strip():
            raise ValueError("PDF 中未提取到文字，可上传 TXT 或粘贴规则。")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = data.decode("gb18030")
            except UnicodeDecodeError as exc:
                raise ValueError("请将要求另存为 UTF-8 文本。") from exc
    if len(text)>30000:
        raise ValueError("要求文件超过 30,000 字，请只保留排版相关章节。")
    return text


@app.post("/api/format/{action}")
async def format_document(action: Literal["preview","apply"], manuscript: UploadFile = File(...), template: UploadFile | None = File(None),
                          requirements: UploadFile | None = File(None), instructions: str = Form("")):
    if len(instructions)>30000:
        raise HTTPException(422,"文字要求最多 30,000 字。")
    original = await read_file(manuscript,[".docx"])
    sample = await read_file(template,[".docx",".dotx"])
    req = await read_file(requirements,[".txt",".docx",".pdf"],6*1024*1024)
    try:
        if req:
            extracted = await run_in_threadpool(read_instructions,requirements.filename,req)
            instructions = extracted + "\n" + instructions
        if not sample and not instructions.strip():
            raise ValueError("请添加模板或格式要求。")
        report, data = await run_in_threadpool(formatting.process,original,sample,instructions,action=="preview")
        if action=="preview":
            return report
        if not report["changed"]:
            raise ValueError("没有可自动套用的规则，请先查看预检报告。")
        return download(data)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


def download(raw):
    return Response(raw,media_type=TYPES["docx"],headers={"Content-Disposition":'attachment; filename="manuscript.docx"'})


@app.post("/api/import")
async def import_manuscript(manuscript: UploadFile = File(...)):
    raw = await read_file(manuscript,[".docx"])
    def extract():
        pkg = formatting.Package(raw)
        title = Path(manuscript.filename).stem
        lines = []
        for role,p in formatting.classified(pkg):
            value = formatting.content(p)
            if role=="title" and not lines:
                title = value
            else:
                prefix = "#" * int(role[1]) + " " if role in {"h1","h2","h3"} else ""
                lines.append(prefix+value)
        if not lines:
            raise ValueError("未找到可导入的正文段落。")
        text = "\n\n".join(lines)
        if len(text)>500000:
            raise ValueError("手稿正文超过 500,000 字。")
        return {"title":title[:250],"text":text}
    try:
        return await run_in_threadpool(extract)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@app.post("/api/export")
def export(req: Manuscript):
    doc = Document()
    page = doc.sections[0]
    page.page_width,page.page_height = Cm(21),Cm(29.7)
    page.left_margin = page.right_margin = page.top_margin = page.bottom_margin = Cm(2.54)
    for name,size in (("Normal",12),("Title",20),("Heading 1",16),("Heading 2",14),("Heading 3",12)):
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string("202020")
        style.font.bold = name!="Normal"
        fonts = style.element.get_or_add_rPr().rFonts
        for key in ("asciiTheme","hAnsiTheme","eastAsiaTheme","cstheme"):
            fonts.attrib.pop(qn("w:"+key),None)
        fonts.set(qn("w:eastAsia"),"宋体" if name=="Normal" else "黑体")
        if name=="Title":
            style.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
            border = style.element.find("w:pPr/w:pBdr",formatting.NS)
            if border is not None:
                border.getparent().remove(border)
    doc.styles["Normal"].paragraph_format.line_spacing=1.5
    if req.title.strip():
        doc.add_paragraph(req.title.strip(),style="Title")
    for line in req.text.splitlines():
        heading = re.match(r"^(#{1,3})\s+(.+)",line)
        if heading:
            doc.add_heading(heading[2],level=len(heading[1]))
        else:
            doc.add_paragraph(line)
    if req.references:
        doc.add_heading("参考文献",level=1)
        for i,r in enumerate(req.references,1):
            parts = [", ".join(r.authors),r.title,r.journal,r.year,r.doi or r.url]
            doc.add_paragraph(f"[{i}] " + ". ".join(s for s in parts if s))
    stream = BytesIO()
    doc.save(stream)
    return download(stream.getvalue())


app.mount("/",StaticFiles(directory=Path(__file__).parent/"static",html=True),name="workspace")

