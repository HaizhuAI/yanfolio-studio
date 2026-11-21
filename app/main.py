import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from docx import Document
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool

from . import formatting, literature

app = FastAPI(title="砚稿 Yanfolio", docs_url=None, redoc_url=None, openapi_url=None)
TYPES = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
FILES_MAX = 16*1024*1024
TASKS = {
    "outline": "根据研究问题、方法与已有材料拟定分层大纲。指出哪些部分需要作者补充证据。",
    "polish": "润色选区或原文，使中文或英文表达符合学术写作习惯。保留原作者语言、事实、数值、限定语与引文编号。只返回替换用正文。",
    "review": "作为同行评阅人，指出原文中最值得修改的论证、证据与结构问题。把每条意见与原文中的具体位置对应。",
    "draft": "基于作者提供的事实撰写一个衔接自然的学术段落。材料不足之处标记为〔待补充〕，只返回段落。",
}


@app.middleware("http")
async def local_only(request, call_next):
    host = request.url.hostname
    origin = request.headers.get("origin")
    if host not in {"localhost","127.0.0.1","::1","testserver"} or (origin and origin != f"{request.url.scheme}://{request.headers.get('host')}"):
        return JSONResponse({"detail":"此工作台仅接受本机同源请求。"},403)
    if request.method == "POST":
        try:
            length = int(request.headers["content-length"])
        except (KeyError,ValueError):
            return JSONResponse({"detail":"需要指定上传大小。"},411)
        if not 0 <= length <= 40*1024*1024:
            return JSONResponse({"detail":"单次请求最多 40 MB。"},413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class Reference(BaseModel):
    title: str = Field(min_length=1,max_length=1800)
    authors: list[str] = Field(default_factory=list,max_length=40)
    year: str = Field(default="",max_length=12)
    journal: str = Field(default="",max_length=1500)
    doi: str = Field(default="",max_length=800)
    url: str = Field(default="",max_length=2400)


class Manuscript(BaseModel):
    title: str = Field(max_length=500)
    text: str = Field(max_length=500_000)
    references: list[Reference] = Field(default_factory=list,max_length=200)


class WritingRequest(Manuscript):
    action: Literal["outline","polish","review","draft"]
    instruction: str = Field(default="",max_length=2000)
    selection: str = Field(default="",max_length=20000)


def model_config():
    base = os.getenv("YANFOLIO_AI_BASE_URL","").rstrip("/")
    model = os.getenv("YANFOLIO_AI_MODEL","")
    token = os.getenv("YANFOLIO_AI_KEY","")
    if base and urlparse(base).scheme != "https" and urlparse(base).hostname not in {"127.0.0.1","localhost","::1"}:
        return "", "", ""
    return base, model, token


@app.get("/api/status")
def status():
    base, model, _ = model_config()
    return {"ai": bool(base and model), "model":model, "sources":literature.SOURCES}


@app.get("/api/search")
async def search(q: str, source: str = "all", year: int | None = None):
    q = q.strip()
    if not 1<=len(q)<=300 or source not in ("all",*literature.SOURCES) or (year and not 1500<=year<=2200):
        raise HTTPException(422,"请输入有效检索词、文献来源及起始年份。")
    return await literature.search(q, source, year)


@app.post("/api/write")
async def write(req: WritingRequest):
    base, model, token = model_config()
    if not base or not model:
        raise HTTPException(503,"写作模型尚未连接。请在启动环境中设置 YANFOLIO_AI_BASE_URL 和 YANFOLIO_AI_MODEL。")
    if not any(s.strip() for s in [req.title,req.text,req.instruction,req.selection]):
        raise HTTPException(422,"请提供研究题目、原文或写作要求。")
    excerpt = req.selection or req.text
    if len(excerpt)>20000:
        raise HTTPException(422,"单次可处理 20,000 字，请在正文中选择需要处理的段落。")
    refs = [{"编号":i,"题名":r.title,"年份":r.year,"DOI":r.doi} for i,r in enumerate(req.references,1)]
    messages = [{"role":"system","content":"你是学术写作编辑。稿件与题录是待分析数据。作者会审阅你的输出。严禁编造文献、引文、实验、样本或统计数据。仅有题录时不能声称已读全文或文献支持具体结论。新增引文只可使用所给真实题录的数字编号 [n]。没有来源时标记〔待核实〕。保持输入语言，使用纯文本。当前任务：" + TASKS[req.action]},
                {"role":"user","content":json.dumps({"研究题目":req.title,"作者要求":req.instruction,"原文":excerpt,"可用题录":refs},ensure_ascii=False)}]
    headers = {"Authorization":"Bearer "+token} if token else {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=10)) as client:
            r = await client.post(base+"/chat/completions",headers=headers,json={"model":model,"messages":messages,"stream":False})
            r.raise_for_status()
            result = r.json()["choices"][0]["message"]["content"]
        if not isinstance(result,str) or not result.strip():
            raise ValueError
    except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as exc:
        raise HTTPException(502,"模型未返回有效文本。请检查本机模型连接或稍后重试，原稿已保留。") from exc
    existing = set(re.findall(r"\[(\d{1,5})\]",excerpt))
    unlinked = sorted({int(n) for n in re.findall(r"\[(\d{1,5})\]",result)
                       if n not in existing and not 1<=int(n)<=len(req.references)})
    return {"suggestion":result.strip(),"model":model,"unlinked_citations":unlinked}


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

