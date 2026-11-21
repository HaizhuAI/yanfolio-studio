import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import store as s

router=APIRouter()
COOKIE="yanfolio_session"
DUMMY=base64.b64encode(b"\0"*48).decode()


def email(value):
    value=value.strip().casefold()
    if len(value)>254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_\x60{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+",value):
        raise HTTPException(422,"请输入有效邮箱。")
    return value


def peer(req):
    return s.digest(req.client.host if req.client else "unknown")


def identity(req):
    token=req.cookies.get(COOKIE,"")
    if not token:
        return None
    with s.db() as c:
        return c.execute("SELECT u.* FROM sessions t JOIN users u ON t.uid=u.id WHERE t.token=? AND t.expires>? AND u.active=1",
                         (s.digest(token),s.now())).fetchone()


def current(req):
    user=getattr(req.state,"user",None) or identity(req)
    if not user:
        raise HTTPException(401,"请先登录。")
    return user


def admin(req):
    user=current(req)
    if user["role"]!="admin":
        raise HTTPException(403,"需要管理员权限。")
    return user


def start_session(c,uid,response):
    token=s.opaque()
    c.execute("DELETE FROM sessions WHERE expires<=?",(s.now(),))
    c.execute("INSERT INTO sessions VALUES(?,?,?)",(s.digest(token),uid,s.now()+7*86400))
    response.set_cookie(COOKIE,token,max_age=7*86400,httponly=True,secure=s.public_origin().startswith("https://"),samesite="lax",path="/")


def password_ok(value,stored):
    salt=base64.b64decode(stored)[:16]
    return hmac.compare_digest(s.password_hash(value,salt),stored)


class Credentials(BaseModel):
    email:str=Field(max_length=254)
    password:str=Field(min_length=1,max_length=256)


class Verify(Credentials):
    code:str=Field(pattern=r"^[0-9]{8}$")


class Code(BaseModel):
    email:str=Field(max_length=254)
    purpose:Literal["register","reset"]="register"


def code_hash(addr,purpose,code):
    return hmac.new(s.key(),f"{addr}|{purpose}|{code}".encode(),hashlib.sha256).hexdigest()


def deliver(addr,code,purpose):
    subject="邮箱注册" if purpose=="register" else "重设密码"
    if os.getenv("YANFOLIO_SMTP_HOST"):
        msg=EmailMessage()
        msg["Subject"]="砚稿 · "+subject+"验证码"
        msg["From"]=os.environ["YANFOLIO_MAIL_FROM"]
        msg["To"]=addr
        msg.set_content(f"你的{subject}验证码为 {code}，10 分钟内有效。")
        port=int(os.getenv("YANFOLIO_SMTP_PORT","465"))
        with (smtplib.SMTP_SSL(os.environ["YANFOLIO_SMTP_HOST"],port,timeout=12,context=ssl.create_default_context()) if port==465 else
              smtplib.SMTP(os.environ["YANFOLIO_SMTP_HOST"],port,timeout=12)) as smtp:
            if port!=465:
                smtp.starttls(context=ssl.create_default_context())
            if os.getenv("YANFOLIO_SMTP_USER"):
                smtp.login(os.environ["YANFOLIO_SMTP_USER"],os.environ["YANFOLIO_SMTP_PASSWORD"])
            smtp.send_message(msg)
    elif urlparse(s.public_origin()).hostname in ("127.0.0.1","localhost","::1"):
        out=s.directory()/"mail"
        out.mkdir(exist_ok=True)
        path=out/(s.digest(addr+"|"+purpose)[:18]+".txt")
        path.write_text(f"收件人 {addr}\n用途 {subject}\n验证码 {code}\n",encoding="utf-8")
        os.chmod(path,0o600)
    else:
        raise RuntimeError("SMTP unavailable")


@router.post("/api/auth/code")
def send_code(body:Code,req:Request):
    addr=email(body.email)
    s.rate("mail-ip:"+peer(req),30,3600)
    s.rate("mail:"+s.digest(addr+body.purpose),1,60)
    value=f"{secrets.randbelow(10**8):08d}"
    with s.db(True) as c:
        exists=c.execute("SELECT 1 FROM users WHERE email=?",(addr,)).fetchone()
        if bool(exists)==(body.purpose=="reset"):
            c.execute("INSERT OR REPLACE INTO challenges VALUES(?,?,?,?)",(addr,body.purpose,code_hash(addr,body.purpose,value),s.now()+600))
        else:
            return {"sent":True}
    try:
        deliver(addr,value,body.purpose)
    except (RuntimeError,OSError,ValueError,KeyError,smtplib.SMTPException) as exc:
        with s.db(True) as c:
            c.execute("DELETE FROM challenges WHERE email=? AND purpose=? AND hash=?",(addr,body.purpose,code_hash(addr,body.purpose,value)))
        raise HTTPException(503,"邮件发送失败，请由管理员检查发信服务。") from exc
    return {"sent":True}


def consume(c,addr,purpose,code):
    row=c.execute("DELETE FROM challenges WHERE email=? AND purpose=? AND hash=? AND expires>?",
                  (addr,purpose,code_hash(addr,purpose,code),s.now()))
    if row.rowcount!=1:
        raise HTTPException(400,"验证码无效或已过期。")


def verify_limit(req,addr):
    s.rate("verify:"+peer(req)+":"+s.digest(addr),12,600)


@router.post("/api/auth/register")
def register(body:Verify,req:Request,response:Response):
    addr=email(body.email)
    verify_limit(req,addr)
    if len(body.password)<10:
        raise HTTPException(422,"密码至少需 10 个字符。")
    with s.db(True) as c:
        consume(c,addr,"register",body.code)
        if c.execute("SELECT 1 FROM users WHERE email=?",(addr,)).fetchone():
            raise HTTPException(409,"该邮箱已注册。")
        uid=c.execute("INSERT INTO users(email,password,created) VALUES(?,?,?)",(addr,s.password_hash(body.password),s.now())).lastrowid
        start_session(c,uid,response)
        return s.public_user(c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone())


@router.post("/api/auth/login")
def login(body:Credentials,req:Request,response:Response):
    addr=email(body.email)
    s.rate("login-ip:"+peer(req),100,600)
    s.rate("login-account:"+s.digest(addr),20,600)
    with s.db() as c:
        row=c.execute("SELECT * FROM users WHERE email=?",(addr,)).fetchone()
    if not password_ok(body.password,row["password"] if row else DUMMY) or not row or not row["active"]:
        raise HTTPException(401,"邮箱或密码无效，或账号已停用。")
    with s.db(True) as c:
        # A reset or suspension between verification and issuance invalidates this login.
        fresh=c.execute("SELECT * FROM users WHERE id=? AND password=? AND active=1",(row["id"],row["password"])).fetchone()
        if not fresh:
            raise HTTPException(401,"账号状态已变更，请重新登录。")
        start_session(c,row["id"],response)
    return s.public_user(row)


@router.post("/api/auth/reset")
def reset(body:Verify,req:Request):
    addr=email(body.email)
    verify_limit(req,addr)
    if len(body.password)<10:
        raise HTTPException(422,"密码至少需 10 个字符。")
    with s.db(True) as c:
        consume(c,addr,"reset",body.code)
        c.execute("UPDATE users SET password=? WHERE email=?",(s.password_hash(body.password),addr))
        c.execute("DELETE FROM sessions WHERE uid=(SELECT id FROM users WHERE email=?)",(addr,))
    return {"ok":True}


@router.post("/api/auth/logout")
def logout(req:Request,response:Response):
    with s.db(True) as c:
        c.execute("DELETE FROM sessions WHERE token=?",(s.digest(req.cookies.get(COOKIE,"")),))
    response.delete_cookie(COOKIE,path="/")
    return {"ok":True}


@router.get("/api/me")
def me(req:Request):
    return s.public_user(current(req))


@router.get("/api/workspace")
def workspace(req:Request):
    with s.db() as c:
        row=c.execute("SELECT * FROM workspaces WHERE uid=?",(current(req)["id"],)).fetchone()
    return {"version":row["version"],"content":json.loads(row["content"])} if row else {"version":0,"content":None}


class Workspace(BaseModel):
    version:int=Field(ge=0)
    content:dict


@router.put("/api/workspace")
def save_workspace(body:Workspace,req:Request):
    uid=current(req)["id"]
    obj=body.content
    docs=obj.get("docs")
    if not isinstance(docs,list) or not docs or len(docs)>500 or not isinstance(obj.get("library"),list):
        raise HTTPException(422,"手稿工作区格式无效。")
    for doc in docs:
        if not isinstance(doc,dict) or not all(isinstance(doc.get(k),str) for k in ("id","title","text")) or not isinstance(doc.get("references"),list):
            raise HTTPException(422,"手稿内容无效。")
    content=json.dumps(obj,ensure_ascii=False,separators=(",",":"))
    if len(content.encode())>8_000_000:
        raise HTTPException(413,"此账号的工作区已达到 8 MB 上限。")
    with s.db(True) as c:
        old=c.execute("SELECT version FROM workspaces WHERE uid=?",(uid,)).fetchone()
        if (old[0] if old else 0)!=body.version:
            raise HTTPException(409,"另一客户端已更新工作区。请先导出本地手稿，再载入云端版本。")
        c.execute("INSERT OR REPLACE INTO workspaces VALUES(?,?,?)",(uid,body.version+1,content))
    return {"version":body.version+1}

