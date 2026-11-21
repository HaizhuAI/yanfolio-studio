import hashlib
import os
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from starlette.concurrency import run_in_threadpool

from . import cloud_store as cs,store as s
from .accounts import current,admin,COOKIE

router=APIRouter()
GB=1_000_000_000


class Named(BaseModel):
    name:str=Field(min_length=1,max_length=160)


class Profile(BaseModel):
    name:str=Field(max_length=60)
    institution:str=Field(max_length=120)
    discipline:str=Field(max_length=80)


def device(c,token,req):
    ua=req.headers.get("user-agent","").lower()
    if "yanfoliodesktop/" in ua:
        label="砚稿 Windows 桌面端"
    else:
        browser="Edge" if "edg/" in ua else "Chrome" if "chrome/" in ua else "Firefox" if "firefox/" in ua else "Safari" if "safari/" in ua else "网页客户端"
        system=next((b for a,b in [("android","Android"),("iphone","iOS"),("windows","Windows"),("mac os","macOS"),("linux","Linux")] if a in ua),"")
        label=(browser+" · "+system).strip(" ·")
    c.execute("INSERT OR IGNORE INTO session_info VALUES(?,?,?,?)",(token,cs.new_id(),label,s.now()))


@router.get("/api/profile")
def profile(req:Request):
    user=current(req)
    with s.db(True) as c:
        card=c.execute("SELECT name,institution,discipline FROM profiles WHERE uid=?",(user["id"],)).fetchone()
        this=s.digest(req.cookies[COOKIE])
        device(c,this,req)
        # Sessions issued before device tracking acquire a neutral entry on first inspection.
        for r in c.execute("SELECT token FROM sessions WHERE uid=? AND expires>? AND token NOT IN (SELECT token FROM session_info)",(user["id"],s.now())).fetchall():
            c.execute("INSERT OR IGNORE INTO session_info VALUES(?,?,?,?)",(r[0],cs.new_id(),"原有登录会话",0))
        devices=[dict(x) for x in c.execute("""SELECT i.device,i.label,i.created,t.expires,t.token=? AS current
                  FROM sessions t JOIN session_info i ON t.token=i.token WHERE t.uid=? AND t.expires>? ORDER BY current DESC,i.created DESC""",(this,user["id"],s.now()))]
        count=c.execute("SELECT count(*) FROM cloud_files WHERE uid=? AND trashed IS NULL",(user["id"],)).fetchone()[0]
        return {**s.public_user(user),"created":user["created"],"profile":dict(card) if card else {"name":"","institution":"","discipline":""},
                "storage":cs.usage(c,user["id"]),"file_count":count,"devices":devices}


@router.put("/api/profile")
def edit_profile(body:Profile,req:Request):
    uid=current(req)["id"]
    with s.db(True) as c:
        c.execute("""INSERT INTO profiles(uid,name,institution,discipline) VALUES(?,?,?,?) ON CONFLICT(uid) DO UPDATE SET
                     name=excluded.name,institution=excluded.institution,discipline=excluded.discipline""",
                  (uid,body.name.strip(),body.institution.strip(),body.discipline.strip()))
    return {"ok":True}


@router.post("/api/profile/devices/{key}/revoke")
def revoke_device(key:str,req:Request):
    with s.db(True) as c:
        uid=current(req)["id"]
        token=c.execute("SELECT t.token FROM sessions t JOIN session_info i ON i.token=t.token WHERE t.uid=? AND i.device=?",(uid,key)).fetchone()
        if not token:
            raise HTTPException(404,"会话不存在。")
        if token[0]==s.digest(req.cookies[COOKIE]):
            raise HTTPException(409,"请通过退出按钮结束当前会话。")
        c.execute("DELETE FROM sessions WHERE token=?",(token[0],))
    return {"ok":True}


@router.get("/api/drive")
def directory(req:Request,folder:str="",trash:bool=False,q:str="",page:int=1):
    uid=current(req)["id"]
    if page<1 or len(q)>160:
        raise HTTPException(422,"检索条件无效。")
    with s.db() as c:
        cs.check_folder(c,uid,folder)
        where="f.uid=? AND "+("f.trashed IS NOT NULL" if trash else "f.trashed IS NULL")
        args=[uid]
        if not trash and (folder or not q.strip()):
            where+=" AND f.folder=?"
            args.append(folder)
        if q.strip():
            where+=" AND instr(f.folded,?)>0"
            args.append(q.strip().casefold())
        total=c.execute("SELECT count(*) FROM cloud_files f WHERE "+where,args).fetchone()[0]
        files=[dict(r) for r in c.execute("""SELECT f.id,f.name,f.folder,f.head,f.modified,f.trashed,v.bytes,v.seq,
                 (SELECT count(*) FROM cloud_versions h WHERE h.file_id=f.id) versions
                 FROM cloud_files f JOIN cloud_versions v ON f.head=v.id WHERE """+where+" ORDER BY f.modified DESC,f.id LIMIT 60 OFFSET ?",(*args,(page-1)*60))]
        folders=[dict(r) for r in c.execute("SELECT id,name FROM cloud_folders WHERE uid=? ORDER BY folded",(uid,))]
        return {"files":files,"folders":folders,"total":total,"page":page,"storage":cs.usage(c,uid),"chunk_bytes":cs.CHUNK_BYTES}


@router.post("/api/drive/folders")
def create_folder(body:Named,req:Request):
    uid=current(req)["id"]
    name=cs.clean_name(body.name)
    with s.db(True) as c:
        if c.execute("SELECT 1 FROM cloud_folders WHERE uid=? AND folded=?",(uid,name.casefold())).fetchone():
            raise HTTPException(409,"文件夹已存在。")
        if c.execute("SELECT count(*) FROM cloud_folders WHERE uid=?",(uid,)).fetchone()[0]>=500:
            raise HTTPException(409,"文件夹数量已达上限。")
        key=cs.new_id()
        c.execute("INSERT INTO cloud_folders VALUES(?,?,?,?)",(key,uid,name,name.casefold()))
    return {"id":key}


class Upload(Named):
    size:int=Field(ge=1,le=5_000_000_000)
    client_id:UUID
    folder:str=Field(default="",max_length=32)
    file_id:str|None=Field(default=None,max_length=32)
    base_version:str|None=Field(default=None,max_length=32)


def transfer(row):
    return {"id":row["id"],"name":row["name"],"size":row["total"],"offset":row["received"],"file_id":row["completed"],
            "expires":row["expires"],"chunk_bytes":cs.CHUNK_BYTES}


@router.post("/api/drive/uploads")
def begin(body:Upload,req:Request):
    uid=current(req)["id"]
    name=cs.clean_name(body.name,True)
    with s.db(True) as c:
        existing=c.execute("SELECT * FROM cloud_uploads WHERE uid=? AND client_id=?",(uid,str(body.client_id))).fetchone()
        if existing:
            if existing["expires"]<=s.now():
                raise HTTPException(410,"上传已过期。")
            if (existing["name"],existing["total"],existing["target"],existing["base"])!=(name,body.size,body.file_id,body.base_version) or (not body.file_id and existing["folder"]!=body.folder):
                raise HTTPException(409,"同一传输编号对应了不同文件。")
            return transfer(existing)
        quota=cs.usage(c,uid)
        if not quota["uploads_enabled"]:
            raise HTTPException(503,"运营方已暂停上传，现有文档仍可下载。")
        if body.size>quota["available"]:
            raise HTTPException(413,"剩余空间不足，可清理回收站或历史版本。")
        folder=body.folder
        if body.file_id:
            f=cs.file_row(c,uid,body.file_id,True)
            if f["head"]!=body.base_version:
                raise HTTPException(409,"文件版本已变化，请刷新。")
            if Path(f["name"]).suffix.lower()!=Path(name).suffix.lower():
                raise HTTPException(422,"新版本须使用相同的文件类型。")
            folder=f["folder"]
        else:
            cs.check_folder(c,uid,folder)
            cs.ensure_unique(c,uid,folder,name)
        if c.execute("SELECT count(*) FROM cloud_uploads WHERE uid=? AND completed IS NULL AND expires>?",(uid,s.now())).fetchone()[0]>=10:
            raise HTTPException(429,"请先完成或取消其他上传。")
        reserved=c.execute("SELECT coalesce(sum(total-received),0) FROM cloud_uploads WHERE completed IS NULL AND expires>?",(s.now(),)).fetchone()[0]
        if body.size+reserved+64*1024*1024>cs.available_volume():
            raise HTTPException(507,"服务器磁盘空间不足，请联系运营方。")
        key=cs.new_id()
        c.execute("""INSERT INTO cloud_uploads(id,uid,name,folder,target,base,total,expires,client_id)
                  VALUES(?,?,?,?,?,?,?,?,?)""",(key,uid,name,folder,body.file_id,body.base_version,body.size,s.now()+cs.UPLOAD_TTL,str(body.client_id)))
        return transfer(cs.upload_row(c,uid,key))


@router.get("/api/drive/uploads/{key}")
def upload_status(key:str,req:Request):
    with s.db() as c:
        return transfer(cs.upload_row(c,current(req)["id"],key))


def append_chunk(uid,key,offset,data,sha):
    actual=hashlib.sha256(data).hexdigest()
    if sha!=actual:
        raise HTTPException(422,"分片校验失败，请重试。")
    with s.db(True) as c:
        u=cs.upload_row(c,uid,key)
        if u["completed"]:
            return transfer(u)
        if not c.execute("SELECT uploads_enabled FROM cloud_config WHERE id=1").fetchone()[0]:
            raise HTTPException(503,"运营方已暂停上传。")
        if offset<u["received"]:
            prior=c.execute("SELECT sha,bytes FROM cloud_parts WHERE upload=? AND offset=?",(key,offset)).fetchone()
            if prior and prior["sha"]==actual and prior["bytes"]==len(data):
                return transfer(u)
        if offset!=u["received"] or len(data)!=min(cs.CHUNK_BYTES,u["total"]-offset):
            raise HTTPException(409,"分片位置或大小不匹配，请同步传输进度。")
        path=cs.object_path(key)
        try:
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with path.open("r+b" if path.exists() else "xb") as out:
                if out.seek(0,2)<offset:
                    raise HTTPException(503,"服务器文件不完整，请取消后重传。")
                out.truncate(offset)
                out.seek(offset)
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
        except OSError as exc:
            raise HTTPException(507,"服务器暂时无法写入文件。") from exc
        c.execute("INSERT INTO cloud_parts VALUES(?,?,?,?)",(key,offset,len(data),actual))
        c.execute("UPDATE cloud_uploads SET received=received+?,expires=? WHERE id=?",(len(data),s.now()+cs.UPLOAD_TTL,key))
        return transfer(cs.upload_row(c,uid,key))


@router.put("/api/drive/uploads/{key}/part")
async def part(key:str,offset:int,req:Request):
    length=int(req.headers["content-length"])
    if offset<0 or not 0<length<=cs.CHUNK_BYTES:
        raise HTTPException(413,"分片超出范围。")
    return await run_in_threadpool(append_chunk,current(req)["id"],key,offset,await req.body(),req.headers.get("x-chunk-sha256",""))


@router.post("/api/drive/uploads/{key}/finish")
def finish(key:str,req:Request):
    uid=current(req)["id"]
    with s.db(True) as c:
        u=cs.upload_row(c,uid,key)
        if u["completed"]:
            return {"file_id":u["completed"],"version":key}
        if not c.execute("SELECT uploads_enabled FROM cloud_config WHERE id=1").fetchone()[0]:
            raise HTTPException(503,"运营方已暂停上传。")
        path=cs.object_path(key)
        if u["total"]!=u["received"] or not path.is_file() or path.stat().st_size!=u["total"]:
            raise HTTPException(409,"文件尚未完整上传。")
        if u["target"]:
            f=cs.file_row(c,uid,u["target"],True)
            if f["head"]!=u["base"]:
                raise HTTPException(409,"另一个客户端已提交新版本，请取消此传输后重新选择。")
            fid=f["id"]
            seq=c.execute("SELECT max(seq)+1 FROM cloud_versions WHERE file_id=?",(fid,)).fetchone()[0]
            c.execute("UPDATE cloud_files SET head=?,modified=? WHERE id=?",(key,s.now(),fid))
        else:
            cs.check_folder(c,uid,u["folder"])
            cs.ensure_unique(c,uid,u["folder"],u["name"])
            fid,seq=cs.new_id(),1
            c.execute("INSERT INTO cloud_files VALUES(?,?,?,?,?,?,?,NULL)",(fid,uid,u["folder"],u["name"],u["name"].casefold(),key,s.now()))
        c.execute("INSERT INTO cloud_versions VALUES(?,?,?,?,?)",(key,fid,seq,u["total"],s.now()))
        c.execute("UPDATE cloud_uploads SET completed=?,expires=? WHERE id=?",(fid,s.now()+cs.UPLOAD_TTL,key))
        c.execute("DELETE FROM cloud_parts WHERE upload=?",(key,))
        return {"file_id":fid,"version":key}


@router.post("/api/drive/uploads/{key}/cancel")
def cancel(key:str,req:Request):
    with s.db(True) as c:
        u=cs.upload_row(c,current(req)["id"],key,False)
        if u["completed"]:
            raise HTTPException(409,"文件已经保存。")
        c.execute("INSERT OR IGNORE INTO cloud_gc VALUES(?)",(key,))
        c.execute("DELETE FROM cloud_uploads WHERE id=?",(key,))
    cs.collect()
    return {"ok":True}


@router.get("/api/drive/files/{key}/versions")
def versions(key:str,req:Request):
    with s.db() as c:
        f=cs.file_row(c,current(req)["id"],key)
        rows=[dict(r) for r in c.execute("SELECT id,seq,bytes,created FROM cloud_versions WHERE file_id=? ORDER BY seq DESC",(key,))]
    return {"file":dict(f),"versions":rows}


class FileUpdate(BaseModel):
    action:Literal["rename","move","trash","restore","purge","restore_version","delete_version"]
    value:str=Field(default="",max_length=160)
    expected:str=Field(min_length=32,max_length=32)


@router.post("/api/drive/files/{key}")
def update_file(key:str,body:FileUpdate,req:Request):
    uid=current(req)["id"]
    with s.db(True) as c:
        f=cs.file_row(c,uid,key)
        if f["head"]!=body.expected:
            raise HTTPException(409,"文件已被更新，请刷新后重试。")
        if body.action in ("restore","purge"):
            if f["trashed"] is None:
                raise HTTPException(409,"请先将文件移入回收站。")
            if body.action=="purge":
                cs.discard_file(c,key)
            else:
                name=cs.clean_name(body.value or f["name"],True)
                if Path(name).suffix.lower()!=Path(f["name"]).suffix.lower():
                    raise HTTPException(422,"请保留原文件扩展名。")
                cs.ensure_unique(c,uid,f["folder"],name,key)
                c.execute("UPDATE cloud_files SET trashed=NULL,name=?,folded=?,modified=? WHERE id=?",(name,name.casefold(),s.now(),key))
        elif f["trashed"] is not None:
            raise HTTPException(409,"请先还原文件。")
        elif body.action=="trash":
            c.execute("UPDATE cloud_files SET trashed=?,modified=? WHERE id=?",(s.now(),s.now(),key))
        elif body.action in ("rename","move"):
            name=cs.clean_name(body.value,True) if body.action=="rename" else f["name"]
            if Path(name).suffix.lower()!=Path(f["name"]).suffix.lower():
                raise HTTPException(422,"请保留原文件扩展名。")
            folder=body.value if body.action=="move" else f["folder"]
            cs.check_folder(c,uid,folder)
            cs.ensure_unique(c,uid,folder,name,key)
            c.execute("UPDATE cloud_files SET name=?,folded=?,folder=?,modified=? WHERE id=?",(name,name.casefold(),folder,s.now(),key))
        else:
            v=c.execute("SELECT id FROM cloud_versions WHERE file_id=? AND id=?",(key,body.value)).fetchone()
            if not v:
                raise HTTPException(404,"版本不存在。")
            if body.action=="restore_version":
                c.execute("UPDATE cloud_files SET head=?,modified=? WHERE id=?",(v[0],s.now(),key))
            else:
                if v[0]==f["head"]:
                    raise HTTPException(409,"当前版本不能单独移除。")
                c.execute("INSERT OR IGNORE INTO cloud_gc VALUES(?)",(v[0],))
                c.execute("DELETE FROM cloud_versions WHERE id=?",(v[0],))
    cs.collect()
    return {"ok":True}


@router.get("/api/drive/files/{key}/download")
def download(key:str,req:Request,version:str=""):
    with s.db() as c:
        f=cs.file_row(c,current(req)["id"],key,True)
        v=c.execute("SELECT * FROM cloud_versions WHERE file_id=? AND id=?",(key,version or f["head"])).fetchone()
        if not v:
            raise HTTPException(404,"版本不存在。")
        try:
            stream=cs.object_path(v["id"]).open("rb")
        except OSError as exc:
            raise HTTPException(503,"文件对象暂不可读。") from exc
    def blocks():
        try:
            while piece:=stream.read(256*1024):
                yield piece
        finally:
            stream.close()
    return StreamingResponse(blocks(),media_type="application/octet-stream",headers={
        "Content-Disposition":"attachment; filename*=UTF-8''"+quote(f["name"],safe=""),"Content-Length":str(v["bytes"]),"ETag":'"'+v["id"]+'"'})

