"""Single-host transactional store for identity, wallets, jobs and service configuration."""
import base64
import hashlib
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


def directory():
    return Path(os.environ.get("YANFOLIO_DATA", ROOT/".local"/"service"))


def now():
    return int(time.time())


def opaque():
    return secrets.token_urlsafe(32)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def key():
    explicit = os.getenv("YANFOLIO_MASTER_KEY")
    if explicit:
        return explicit.encode()
    d = directory()
    d.mkdir(parents=True, exist_ok=True)
    f = d/"master.key"
    if not f.exists():
        temp = d/("key-"+secrets.token_hex(8)+".tmp")
        with temp.open("xb") as handle:
            os.chmod(temp,0o600)
            handle.write(Fernet.generate_key())
        try:
            os.link(temp,f)
        except FileExistsError:
            pass
        finally:
            temp.unlink()
    return f.read_bytes().strip()


def protect(text):
    return Fernet(key()).encrypt(text.encode()).decode() if text else ""


def reveal(text):
    return Fernet(key()).decrypt(text.encode()).decode() if text else ""


@contextmanager
def db(write=False):
    c = sqlite3.connect(directory()/"yanfolio.sqlite3",timeout=12,isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        if write:
            c.execute("BEGIN IMMEDIATE")
        yield c
        if c.in_transaction:
            c.commit()
    except BaseException:
        if c.in_transaction:
            c.rollback()
        raise
    finally:
        c.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
 active INTEGER NOT NULL DEFAULT 1,balance INTEGER NOT NULL DEFAULT 0 CHECK(balance>=0), created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,uid INTEGER NOT NULL REFERENCES users(id),expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS sessions_uid ON sessions(uid);
CREATE TABLE IF NOT EXISTS challenges(email TEXT,purpose TEXT,hash TEXT NOT NULL,expires INTEGER NOT NULL,PRIMARY KEY(email,purpose));
CREATE TABLE IF NOT EXISTS limits(bucket TEXT PRIMARY KEY,started INTEGER NOT NULL,n INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces(uid INTEGER PRIMARY KEY REFERENCES users(id),version INTEGER NOT NULL,content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS models(id INTEGER PRIMARY KEY,label TEXT NOT NULL,model TEXT NOT NULL,base TEXT NOT NULL,secret TEXT NOT NULL DEFAULT '',
 fee INTEGER NOT NULL,input_rate INTEGER NOT NULL,output_rate INTEGER NOT NULL,max_output INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,uid INTEGER NOT NULL REFERENCES users(id),delta INTEGER NOT NULL,after INTEGER NOT NULL,
 kind TEXT NOT NULL,ref TEXT NOT NULL,note TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(uid,kind,ref));
CREATE TABLE IF NOT EXISTS jobs(id TEXT NOT NULL,uid INTEGER NOT NULL REFERENCES users(id),fingerprint TEXT NOT NULL,status TEXT NOT NULL,
 reserved INTEGER NOT NULL,charged INTEGER NOT NULL DEFAULT 0,result TEXT,created INTEGER NOT NULL,PRIMARY KEY(uid,id));
CREATE TABLE IF NOT EXISTS vouchers(hash TEXT PRIMARY KEY,points INTEGER NOT NULL CHECK(points>0),uid INTEGER REFERENCES users(id),
 created INTEGER NOT NULL,redeemed INTEGER,issuer INTEGER NOT NULL REFERENCES users(id),batch TEXT NOT NULL,label TEXT NOT NULL,cents INTEGER NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS packs(id INTEGER PRIMARY KEY,label TEXT NOT NULL,points INTEGER NOT NULL,cents INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,uid INTEGER REFERENCES users(id),action TEXT NOT NULL,subject TEXT NOT NULL,created INTEGER NOT NULL);
"""


def init():
    directory().mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name!="nt":
        directory().chmod(0o700)
    Fernet(key())
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
    with db(True) as c:
        if not c.execute("SELECT 1 FROM models").fetchone():
            base=os.getenv("YANFOLIO_AI_BASE_URL","http://127.0.0.1:18769/v1").rstrip("/")
            model=os.getenv("YANFOLIO_AI_MODEL","Yanfolio-Qwen2.5-1.5B")
            c.execute("INSERT INTO models(label,model,base,secret,fee,input_rate,output_rate,max_output) VALUES(?,?,?,?,?,?,?,?)",
                      ("研究写作 · 标准",model,base,protect(os.getenv("YANFOLIO_AI_KEY","")),2,0,0,768))
            if os.getenv("YANFOLIO_FAST_BASE_URL"):
                c.execute("INSERT INTO models(label,model,base,fee,input_rate,output_rate,max_output) VALUES(?,?,?,1,0,0,384)",
                          ("快速润色 · 轻量", "Yanfolio-Qwen2.5-0.5B",os.environ["YANFOLIO_FAST_BASE_URL"]))
        if not c.execute("SELECT 1 FROM packs").fetchone():
            c.executemany("INSERT INTO packs(label,points,cents) VALUES(?,?,?)",[("研究入门",100,1000),("论文写作",550,5000),("课题研究",1200,10000)])


def public_origin():
    return os.getenv("YANFOLIO_PUBLIC_URL","http://127.0.0.1:8769").rstrip("/")


def public_user(row):
    return {k:row[k] for k in ("id","email","role","balance")}


def audit(c,uid,action,subject):
    c.execute("INSERT INTO audit(uid,action,subject,created) VALUES(?,?,?,?)",(uid,action,str(subject),now()))


def post_points(c,uid,delta,kind,ref,note):
    updated=c.execute("UPDATE users SET balance=balance+? WHERE id=? AND balance+?>=0",(delta,uid,delta))
    if updated.rowcount!=1:
        raise HTTPException(402,"账户点数不足，请充值或选择价格较低的模型。")
    balance=c.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone()[0]
    c.execute("INSERT INTO ledger(uid,delta,after,kind,ref,note,created) VALUES(?,?,?,?,?,?,?)",
              (uid,delta,balance,kind,ref,note,now()))
    return balance


def rate(bucket,limit,seconds):
    moment=now()
    with db(True) as c:
        c.execute("DELETE FROM limits WHERE started < ?",(moment-172800,))
        row=c.execute("SELECT * FROM limits WHERE bucket=?",(bucket,)).fetchone()
        if row and row["started"]+seconds>moment:
            if row["n"]>=limit:
                raise HTTPException(429,"操作太频繁，请稍后再试。")
            c.execute("UPDATE limits SET n=n+1 WHERE bucket=?",(bucket,))
        else:
            c.execute("INSERT OR REPLACE INTO limits VALUES(?,?,1)",(bucket,moment))


def password_hash(password,salt=None):
    salt=salt or secrets.token_bytes(16)
    raw=hashlib.scrypt(password.encode(),salt=salt,n=32768,r=8,p=1,maxmem=80*1024*1024,dklen=32)
    return base64.b64encode(salt+raw).decode()

