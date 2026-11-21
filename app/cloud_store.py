"""Private immutable file versions on an operator volume, indexed in the account database."""
import os
import re
import shutil
import unicodedata
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from . import store as s

FREE_BYTES = 5_000_000_000
CHUNK_BYTES = 4 * 1024 * 1024
UPLOAD_TTL = 24 * 3600
TRASH_TTL = 30 * 86400
EXTENSIONS = frozenset("doc docx dotx pdf txt md rtf odt tex bib ris csv tsv xls xlsx ppt pptx png jpg jpeg webp".split())

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles(uid INTEGER PRIMARY KEY REFERENCES users(id), name TEXT NOT NULL DEFAULT '',
 institution TEXT NOT NULL DEFAULT '', discipline TEXT NOT NULL DEFAULT '', quota INTEGER CHECK(quota>=0));
CREATE TABLE IF NOT EXISTS cloud_config(id INTEGER PRIMARY KEY CHECK(id=1),free_bytes INTEGER NOT NULL,uploads_enabled INTEGER NOT NULL);
INSERT OR IGNORE INTO cloud_config VALUES(1,5000000000,1);
CREATE TABLE IF NOT EXISTS cloud_folders(id TEXT PRIMARY KEY,uid INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,
 folded TEXT NOT NULL,UNIQUE(uid,folded));
CREATE TABLE IF NOT EXISTS cloud_files(id TEXT PRIMARY KEY,uid INTEGER NOT NULL REFERENCES users(id),folder TEXT NOT NULL,
 name TEXT NOT NULL,folded TEXT NOT NULL,head TEXT NOT NULL,modified INTEGER NOT NULL,trashed INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS cloud_names ON cloud_files(uid,folder,folded) WHERE trashed IS NULL;
CREATE INDEX IF NOT EXISTS cloud_by_user ON cloud_files(uid,trashed,modified);
CREATE TABLE IF NOT EXISTS cloud_versions(id TEXT PRIMARY KEY,file_id TEXT NOT NULL REFERENCES cloud_files(id) ON DELETE CASCADE,
 seq INTEGER NOT NULL,bytes INTEGER NOT NULL CHECK(bytes>=0),created INTEGER NOT NULL,UNIQUE(file_id,seq));
CREATE TABLE IF NOT EXISTS cloud_uploads(id TEXT PRIMARY KEY,uid INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,
 folder TEXT NOT NULL,target TEXT,base TEXT,total INTEGER NOT NULL,received INTEGER NOT NULL DEFAULT 0,
 expires INTEGER NOT NULL,completed TEXT,client_id TEXT NOT NULL,UNIQUE(uid,client_id));
CREATE INDEX IF NOT EXISTS cloud_pending ON cloud_uploads(uid,expires);
CREATE TABLE IF NOT EXISTS cloud_parts(upload TEXT REFERENCES cloud_uploads(id) ON DELETE CASCADE,offset INTEGER NOT NULL,
 bytes INTEGER NOT NULL,sha TEXT NOT NULL,PRIMARY KEY(upload,offset));
CREATE TABLE IF NOT EXISTS cloud_gc(id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS session_info(token TEXT PRIMARY KEY REFERENCES sessions(token) ON DELETE CASCADE,
 device TEXT NOT NULL UNIQUE,label TEXT NOT NULL,created INTEGER NOT NULL);
"""


def objects():
    return Path(os.environ.get("YANFOLIO_OBJECT_DIR",s.directory()/"objects"))


def object_path(key):
    if not re.fullmatch(r"[a-f0-9]{32}",key):
        raise ValueError("Invalid internal object identifier.")
    return objects()/key[:2]/key


def clean_name(value,file=False):
    name=unicodedata.normalize("NFC",value.strip())
    if (not name or name in {".",".."} or name.endswith(".") or len(name)>160 or
        any(unicodedata.category(ch) in ("Cc","Cf") or ch in '/\\:*?"<>|' for ch in name)):
        raise HTTPException(422,"名称无效，请使用不含路径分隔符的文件名。")
    if file and Path(name).suffix.lower().lstrip(".") not in EXTENSIONS:
        raise HTTPException(415,"请选择受支持的论文、题录、表格或图片文件。")
    return name


def usage(c,uid):
    config=c.execute("SELECT * FROM cloud_config WHERE id=1").fetchone()
    p=c.execute("SELECT quota FROM profiles WHERE uid=?",(uid,)).fetchone()
    quota=p["quota"] if p and p["quota"] is not None else config["free_bytes"]
    sizes=c.execute("""SELECT coalesce(sum(v.bytes),0),coalesce(sum(CASE WHEN f.trashed IS NOT NULL THEN v.bytes ELSE 0 END),0)
                       FROM cloud_files f JOIN cloud_versions v ON f.id=v.file_id WHERE f.uid=?""",(uid,)).fetchone()
    reserved=c.execute("SELECT coalesce(sum(total),0) FROM cloud_uploads WHERE uid=? AND completed IS NULL AND expires>?",(uid,s.now())).fetchone()[0]
    return {"quota":quota,"used":sizes[0],"trash":sizes[1],"reserved":reserved,"available":max(0,quota-sizes[0]-reserved),
            "uploads_enabled":bool(config["uploads_enabled"])}


def check_folder(c,uid,folder):
    if folder and not c.execute("SELECT 1 FROM cloud_folders WHERE uid=? AND id=?",(uid,folder)).fetchone():
        raise HTTPException(404,"文件夹不存在。")


def file_row(c,uid,key,live=False):
    row=c.execute("SELECT * FROM cloud_files WHERE id=? AND uid=?",(key,uid)).fetchone()
    if not row or (live and row["trashed"] is not None):
        raise HTTPException(404,"文件不存在。")
    return row


def upload_row(c,uid,key,check_expiry=True):
    row=c.execute("SELECT * FROM cloud_uploads WHERE id=? AND uid=?",(key,uid)).fetchone()
    if not row:
        raise HTTPException(404,"上传任务不存在。")
    if check_expiry and row["expires"]<=s.now():
        raise HTTPException(410,"上传已过期，请重新选择文件。")
    return row


def ensure_unique(c,uid,folder,name,exclude=""):
    if c.execute("SELECT 1 FROM cloud_files WHERE uid=? AND folder=? AND folded=? AND id!=? AND trashed IS NULL",
                 (uid,folder,name.casefold(),exclude)).fetchone():
        raise HTTPException(409,"文件夹中已有同名文件，可改名或上传为新版本。")


def discard_file(c,key):
    c.execute("INSERT OR IGNORE INTO cloud_gc SELECT id FROM cloud_versions WHERE file_id=?",(key,))
    c.execute("DELETE FROM cloud_files WHERE id=?",(key,))


def expire():
    now=s.now()
    with s.db(True) as c:
        c.execute("INSERT OR IGNORE INTO cloud_gc SELECT id FROM cloud_uploads WHERE expires<=? AND completed IS NULL",(now,))
        c.execute("DELETE FROM cloud_uploads WHERE expires<=?",(now,))
        for row in c.execute("SELECT id FROM cloud_files WHERE trashed IS NOT NULL AND trashed<=?",(now-TRASH_TTL,)).fetchall():
            discard_file(c,row[0])
    collect()


def collect():
    with s.db() as c:
        entries=c.execute("SELECT id FROM cloud_gc LIMIT 128").fetchall()
    done=[]
    for row in entries:
        try:
            object_path(row[0]).unlink(missing_ok=True)
            done.append((row[0],))
        except OSError:
            continue
    if done:
        with s.db(True) as c:
            c.executemany("DELETE FROM cloud_gc WHERE id=?",done)


def available_volume():
    return shutil.disk_usage(objects()).free


def new_id():
    return uuid4().hex

