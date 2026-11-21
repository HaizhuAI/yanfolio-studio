import json
from io import BytesIO
from pathlib import Path,PurePosixPath
from urllib.parse import quote
from uuid import UUID
from zipfile import BadZipFile,ZipFile
from lxml.etree import XMLSyntaxError

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from pptx import Presentation
from pptx.exc import PythonPptxError
from starlette.concurrency import run_in_threadpool

from . import deck_render as render,store as s
from .accounts import current
from .slide_content import Deck,Slide

router=APIRouter(prefix="/api/slides")
MIME="application/vnd.openxmlformats-officedocument.presentationml.presentation"
SCHEMA="""CREATE TABLE IF NOT EXISTS slide_decks(uid INTEGER NOT NULL REFERENCES users(id), id TEXT NOT NULL,
 title TEXT NOT NULL,template TEXT NOT NULL,version INTEGER NOT NULL,content TEXT NOT NULL,updated INTEGER NOT NULL,
 PRIMARY KEY(uid,id));"""


def check_theme(key):
    try:
        return render.template(key)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


def store_draft(c,uid,key,deck,expected=0):
    check_theme(deck.template)
    raw=deck.model_dump_json()
    row=c.execute("SELECT version,content FROM slide_decks WHERE uid=? AND id=?",(uid,key)).fetchone()
    if row and row["content"]==raw:
        return row["version"]
    if (row["version"] if row else 0)!=expected:
        raise HTTPException(409,"另一台设备已更新演示稿。可以将当前修改另存为副本。")
    count,size=c.execute("SELECT count(*),coalesce(sum(length(cast(content AS BLOB))),0) FROM slide_decks WHERE uid=? AND id!=?",(uid,key)).fetchone()
    if count>=250 or size+len(raw.encode())>12_000_000:
        raise HTTPException(413,"演示草稿空间已满，请先导出并清理不再使用的草稿。")
    version=expected+1
    c.execute("""INSERT INTO slide_decks VALUES(?,?,?,?,?,?,?) ON CONFLICT(uid,id) DO UPDATE SET
                 title=excluded.title,template=excluded.template,version=excluded.version,content=excluded.content,updated=excluded.updated""",
              (uid,key,deck.title,deck.template,version,raw,s.now()))
    return version


class Save(BaseModel):
    version:int=Field(ge=0)
    deck:Deck


class Preview(BaseModel):
    template:str
    slide:Slide
    title:str=Field(max_length=120)
    number:int=Field(ge=1,le=32)
    total:int=Field(ge=1,le=32)


@router.get("/templates")
def catalog():
    return {"templates":[{k:v for k,v in t.items() if k in {"id","name","description","source","source_url","license","colors","layouts"}}
                         for t in render.templates().values()]}


@router.get("/templates/{key}/thumbnail")
def thumbnail(key:str):
    t=check_theme(key)
    return FileResponse(render.ASSETS/t["thumbnail"],media_type="image/webp")


@router.get("/templates/{key}/download")
def download_template(key:str):
    t=check_theme(key)
    return Response(render.licensed((render.ASSETS/t["file"]).read_bytes(),key),media_type=MIME,
                    headers={"Content-Disposition":"attachment; filename*=UTF-8''"+quote(t["name"]+".pptx",safe="")})


@router.get("/drafts")
def drafts(req:Request):
    with s.db() as c:
        return {"items":[dict(r) for r in c.execute("""SELECT id,title,template,version,updated FROM slide_decks
                WHERE uid=? ORDER BY updated DESC,rowid DESC""",(current(req)["id"],))]}


@router.get("/drafts/{key}")
def read_draft(key:UUID,req:Request):
    with s.db() as c:
        row=c.execute("SELECT version,content FROM slide_decks WHERE uid=? AND id=?",(current(req)["id"],str(key))).fetchone()
    if not row:
        raise HTTPException(404,"演示稿不存在。")
    return {"id":str(key),"version":row["version"],"deck":json.loads(row["content"])}


@router.put("/drafts/{key}")
def save_draft(key:UUID,body:Save,req:Request):
    with s.db(True) as c:
        version=store_draft(c,current(req)["id"],str(key),body.deck,body.version)
    return {"version":version}


@router.delete("/drafts/{key}")
def delete_draft(key:UUID,version:int,req:Request):
    with s.db(True) as c:
        changed=c.execute("DELETE FROM slide_decks WHERE uid=? AND id=? AND version=?",(current(req)["id"],str(key),version))
        if not changed.rowcount:
            raise HTTPException(409,"草稿版本已变化，请刷新列表后重试。")
    return {"ok":True}


@router.post("/preview")
def preview(body:Preview):
    check_theme(body.template)
    svg,warnings=render.preview(body.template,body.slide.layout,body.slide,body.number,body.total,body.title)
    return {"svg":svg,"overflow":warnings}


@router.post("/export")
def export(body:Deck):
    check_theme(body.template)
    try:
        raw=render.export(body)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return Response(raw,media_type=MIME,headers={"Content-Disposition":"attachment; filename*=UTF-8''"+quote(body.title+".pptx",safe="")})


def _import(raw,filename,theme):
    try:
        with ZipFile(BytesIO(raw)) as z:
            entries=z.infolist()
            if (len(entries)>4000 or len(entries)!=len(set(i.filename for i in entries)) or sum(i.file_size for i in entries)>90_000_000 or
                any(i.file_size>25_000_000 or i.flag_bits&1 or ".." in PurePosixPath(i.filename).parts or
                    "vbaproject" in i.filename.lower() for i in entries)):
                raise ValueError("PPTX 包过大、已加密或含有宏。")
            if "ppt/presentation.xml" not in z.namelist():
                raise ValueError("文件没有演示文稿主部件。")
        prs=Presentation(BytesIO(raw))
        if not 1<=len(prs.slides)<=32:
            raise ValueError("可导入 1 至 32 页的演示稿。")
        old=(prs.core_properties.keywords or "").removeprefix("Yanfolio:")
        native=old in render.templates()
        if native:
            theme=old
        slides=[]
        for i,page in enumerate(prs.slides):
            layout=page._element.cSld.get("name","").removeprefix("Yanfolio:")
            notes=page.notes_slide.notes_text_frame.text.replace("\v","\n") if page.has_notes_slide and page.notes_slide.notes_text_frame else ""
            named=[sh.name for sh in page.shapes if sh.has_text_frame and sh.text.strip()]
            if native and layout in render.LAYOUTS and set(named)<=render.SLOTS and len(named)==len(set(named)):
                fields={sh.name:"\n".join("".join(run.text for run in p.runs) for p in sh.text_frame.paragraphs)
                        for sh in page.shapes if sh.has_text_frame and sh.name in render.SLOTS and sh.name!="footer"}
                slides.append(Slide(layout=layout,notes=notes,**fields))
            else:
                boxes=[sh.text.strip().replace("\v"," ") for sh in page.shapes if sh.has_text_frame and sh.text.strip()]
                heading=page.shapes.title
                title=heading.text.strip().replace("\v"," ") if heading is not None and heading.text.strip() else (boxes[0] if boxes else f"第 {i+1} 页")
                if title in boxes:
                    boxes.remove(title)
                slides.append(Slide(layout="content",title=title,body="\n".join(boxes),notes=notes))
        return Deck(title=(prs.core_properties.title or Path(filename).stem)[:120],template=theme,slides=slides)
    except ValidationError as exc:
        raise ValueError("原页文字超过可编辑页的容量，请先在 PowerPoint 中拆分过密的页面。") from exc
    except (BadZipFile,KeyError,AttributeError,IndexError,TypeError,RuntimeError,XMLSyntaxError,PythonPptxError) as exc:
        raise ValueError("无法读取该 PPTX，请另存为标准 PowerPoint 演示文稿后再试。") from exc


@router.post("/import")
async def import_presentation(template:str,presentation:UploadFile=File(...)):
    check_theme(template)
    if not (presentation.filename or "").lower().endswith(".pptx"):
        raise HTTPException(422,"请选择 PPTX 文件。")
    raw=await presentation.read(16*1024*1024+1)
    if not raw or len(raw)>16*1024*1024:
        raise HTTPException(413,"请选择 16 MB 以内的非空 PPTX。")
    try:
        return await run_in_threadpool(_import,raw,presentation.filename,template)
    except (ValueError,OSError) as exc:
        raise HTTPException(422,str(exc)) from exc

