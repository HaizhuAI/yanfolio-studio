import secrets
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import store as s
from .accounts import admin

router=APIRouter(prefix="/api/admin")


class ModelConfig(BaseModel):
    id:int|None=None
    label:str=Field(min_length=1,max_length=80)
    model:str=Field(min_length=1,max_length=160)
    base:str=Field(min_length=8,max_length=1000)
    secret:str|None=Field(default=None,max_length=8192)
    fee:int=Field(ge=1,le=100000)
    input_rate:int=Field(ge=0,le=10000)
    output_rate:int=Field(ge=0,le=10000)
    max_output:int=Field(ge=64,le=8192)
    enabled:bool=True


@router.post("/models")
def save_model(body:ModelConfig,req:Request):
    uid=admin(req)["id"]
    url=urlparse(body.base)
    if (not url.hostname or url.username or url.password or url.query or url.fragment or
        (url.scheme!="https" and not (url.scheme=="http" and url.hostname in ("localhost","127.0.0.1","::1")))):
        raise HTTPException(422,"使用 HTTPS 接口地址；本机模型也可用回环 HTTP 地址。")
    with s.db(True) as c:
        values=(body.label.strip(),body.model.strip(),body.base.strip().rstrip("/"),body.fee,body.input_rate,body.output_rate,body.max_output,body.enabled)
        if body.id is None:
            mid=c.execute("INSERT INTO models(label,model,base,fee,input_rate,output_rate,max_output,enabled,secret) VALUES(?,?,?,?,?,?,?,?,?)",(*values,s.protect(body.secret or ""))).lastrowid
        else:
            mid=body.id
            before=c.execute("SELECT base,secret FROM models WHERE id=?",(mid,)).fetchone()
            if before and before["secret"] and urlparse(before["base"]).netloc!=url.netloc and body.secret is None:
                raise HTTPException(422,"切换接口主机时请重新填写密钥，或明确选择清除密钥。")
            if not c.execute("UPDATE models SET label=?,model=?,base=?,fee=?,input_rate=?,output_rate=?,max_output=?,enabled=? WHERE id=?",(*values,mid)).rowcount:
                raise HTTPException(404,"模型不存在。")
            if body.secret is not None:
                c.execute("UPDATE models SET secret=? WHERE id=?",(s.protect(body.secret),mid))
        s.audit(c,uid,"保存模型",mid)
    return {"id":mid}


@router.post("/models/{mid}/test")
async def test_model(mid:int,req:Request):
    admin(req)
    with s.db() as c:
        row=c.execute("SELECT base,secret,model FROM models WHERE id=?",(mid,)).fetchone()
    if not row:
        raise HTTPException(404,"模型不存在。")
    token=s.reveal(row["secret"])
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response=await client.get(row["base"]+"/models",headers={"Authorization":"Bearer "+token} if token else {})
            response.raise_for_status()
            found=any(m.get("id")==row["model"] for m in response.json()["data"] if isinstance(m,dict))
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
        raise HTTPException(502,"未能读取模型列表，请核对接口、鉴权及提供方的 /models 支持。") from exc
    return {"found":found}


class Pack(BaseModel):
    id:int|None=None
    label:str=Field(min_length=1,max_length=60)
    points:int=Field(gt=0,le=10000000)
    cents:int=Field(ge=0,le=100000000)
    enabled:bool=True


@router.post("/packs")
def pack(body:Pack,req:Request):
    uid=admin(req)["id"]
    with s.db(True) as c:
        values=(body.label.strip(),body.points,body.cents,body.enabled)
        if body.id is None:
            pk=c.execute("INSERT INTO packs(label,points,cents,enabled) VALUES(?,?,?,?)",values).lastrowid
        else:
            pk=body.id
            if not c.execute("UPDATE packs SET label=?,points=?,cents=?,enabled=? WHERE id=?",(*values,pk)).rowcount:
                raise HTTPException(404,"套餐不存在。")
        s.audit(c,uid,"保存套餐",pk)
    return {"id":pk}


class Issue(BaseModel):
    pack:int
    count:int=Field(ge=1,le=100)


@router.post("/vouchers")
def issue(body:Issue,req:Request):
    uid=admin(req)["id"]
    batch=secrets.token_hex(6)
    codes=["YG-"+secrets.token_hex(16).upper() for _ in range(body.count)]
    with s.db(True) as c:
        pack=c.execute("SELECT * FROM packs WHERE id=? AND enabled=1",(body.pack,)).fetchone()
        if not pack:
            raise HTTPException(404,"请选择启用的套餐。")
        c.executemany("INSERT INTO vouchers(hash,points,created,issuer,batch,label,cents) VALUES(?,?,?,?,?,?,?)",
                      [(s.digest(code),pack["points"],s.now(),uid,batch,pack["label"],pack["cents"]) for code in codes])
        s.audit(c,uid,"发行兑换码",batch+" × "+str(body.count))
    return {"batch":batch,"codes":codes,"points":pack["points"]}


@router.post("/batches/{batch}/revoke")
def revoke(batch:str,req:Request):
    uid=admin(req)["id"]
    with s.db(True) as c:
        n=c.execute("UPDATE vouchers SET revoked=1 WHERE batch=? AND uid IS NULL AND revoked=0",(batch,)).rowcount
        s.audit(c,uid,"停用未兑码",batch+" × "+str(n))
    return {"revoked":n}


class UserState(BaseModel):
    active:bool


@router.post("/users/{target}/state")
def account_state(target:int,body:UserState,req:Request):
    uid=admin(req)["id"]
    with s.db(True) as c:
        if not c.execute("UPDATE users SET active=? WHERE id=? AND role='user'",(body.active,target)).rowcount:
            raise HTTPException(400,"可操作对象为普通用户。")
        if not body.active:
            c.execute("DELETE FROM sessions WHERE uid=?",(target,))
        s.audit(c,uid,"启用用户" if body.active else "停用用户",target)
    return {"ok":True}


@router.get("/overview")
def overview(req:Request,q:str=""):
    admin(req)
    with s.db() as c:
        def rows(sql,args=()):
            return [dict(r) for r in c.execute(sql,args)]
        return {"metrics":dict(c.execute("SELECT (SELECT count(*) FROM users WHERE role='user') users,(SELECT coalesce(sum(points),0) FROM vouchers WHERE uid IS NOT NULL) redeemed,(SELECT coalesce(sum(charged),0) FROM jobs WHERE status='done') consumed,(SELECT count(*) FROM jobs WHERE status='done') jobs").fetchone()),
                "models":rows("SELECT id,label,model,base,fee,input_rate,output_rate,max_output,enabled,(secret!='') has_secret FROM models ORDER BY id"),
                "packs":rows("SELECT * FROM packs ORDER BY id"),
                "batches":rows("SELECT batch,label,points,cents,count(*) issued,count(uid) redeemed,sum(revoked) revoked,max(created) created FROM vouchers GROUP BY batch ORDER BY created DESC LIMIT 100"),
                "users":rows("SELECT id,email,role,active,balance,created FROM users WHERE instr(email,?)>0 ORDER BY id DESC LIMIT 100",(q.strip().casefold()[:254],)),
                "audit":rows("SELECT a.action,a.subject,a.created,u.email FROM audit a LEFT JOIN users u ON a.uid=u.id ORDER BY a.id DESC LIMIT 60")}

