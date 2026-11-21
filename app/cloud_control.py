from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import cloud_store as cs,store as s
from .accounts import admin

router=APIRouter(prefix="/api/admin/cloud")


@router.get("")
def overview(req:Request,q:str=""):
    admin(req)
    with s.db() as c:
        totals=c.execute("SELECT coalesce(sum(bytes),0),count(*) FROM cloud_versions").fetchone()
        users=[{"id":r["id"],"email":r["email"],**cs.usage(c,r["id"])} for r in c.execute(
            "SELECT id,email FROM users WHERE instr(email,?)>0 ORDER BY id DESC LIMIT 80",(q.strip().casefold()[:254],))]
        config=dict(c.execute("SELECT free_bytes,uploads_enabled FROM cloud_config WHERE id=1").fetchone())
        return {"config":config,"stored":totals[0],"versions":totals[1],"disk_available":cs.available_volume(),"users":users}


class Switch(BaseModel):
    enabled:bool


@router.put("/uploads")
def switch(body:Switch,req:Request):
    uid=admin(req)["id"]
    with s.db(True) as c:
        c.execute("UPDATE cloud_config SET uploads_enabled=? WHERE id=1",(body.enabled,))
        s.audit(c,uid,"开放云文档上传" if body.enabled else "暂停云文档上传","cloud")
    return {"ok":True}


class Quota(BaseModel):
    bytes:int|None=Field(default=None,ge=0,le=1_000_000_000_000)


@router.put("/users/{target}")
def quota(target:int,body:Quota,req:Request):
    uid=admin(req)["id"]
    with s.db(True) as c:
        if not c.execute("SELECT 1 FROM users WHERE id=?",(target,)).fetchone():
            raise HTTPException(404,"账号不存在。")
        u=cs.usage(c,target)
        limit=body.bytes if body.bytes is not None else cs.FREE_BYTES
        if limit<u["used"]+u["reserved"]:
            raise HTTPException(409,"配额不能低于已保存和上传中预留空间之和。")
        c.execute("INSERT INTO profiles(uid,quota) VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET quota=excluded.quota",(target,body.bytes))
        s.audit(c,uid,"调整文档配额",f"{target} / {limit} bytes")
    return {"quota":limit}

