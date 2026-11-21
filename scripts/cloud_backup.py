"""Snapshot a single-node Yanfolio service; restore only into a new directory."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
from zipfile import ZipFile,ZIP_STORED

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import cloud_store as cs,store as s


def read_key(file=None):
    if file:
        return Path(file).read_bytes().strip()
    env=os.getenv("YANFOLIO_MASTER_KEY")
    return env.encode() if env else (s.directory()/"master.key").read_bytes().strip()


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def copy_object(source,dest,chunk_size):
    length=0
    digest=hashlib.sha256()
    while data:=source.read(chunk_size):
        dest.write(data)
        length+=len(data)
        digest.update(hashlib.sha256(data).digest())
    return length,digest.hexdigest()


def backup(output):
    output=Path(output).resolve()
    if output.exists():
        raise ValueError("Choose a new backup filename.")
    if not (s.directory()/"yanfolio.sqlite3").is_file():
        raise ValueError("Service database not found.")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".snapshot-",dir=cs.objects()) as temp, tempfile.TemporaryDirectory(dir=output.parent) as delivery:
        stage=Path(temp)
        db_path=stage/"yanfolio.sqlite3"
        # Link immutable versions under the write lock, then release it before reading their bytes.
        with s.db(True):
            with s.db() as source,closing(sqlite3.connect(db_path)) as saved:
                source.backup(saved)
                saved.execute("PRAGMA foreign_keys=ON")
                for table in ("sessions","challenges","limits","cloud_parts","cloud_uploads","cloud_gc"):
                    saved.execute("DELETE FROM "+table)
                saved.execute("UPDATE jobs SET created=0 WHERE status='pending'")
                saved.commit()
                rows=saved.execute("SELECT v.id,v.bytes,h.chunk_size,h.digest FROM cloud_versions v LEFT JOIN cloud_hashes h ON h.version=v.id").fetchall()
                saved.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            for key,size,_,_ in rows:
                original=cs.object_path(key)
                if original.stat().st_size!=size:
                    raise ValueError("Object length mismatch: "+key)
                try:
                    os.link(original,stage/key)
                except OSError:
                    shutil.copyfile(original,stage/key)
        packed=Path(delivery)/"snapshot.zip"
        manifest={"format":1,"created":s.now(),"database_sha256":sha(db_path),"key_fingerprint":hashlib.sha256(read_key()).hexdigest(),"objects":[]}
        with ZipFile(packed,"w",compression=ZIP_STORED,allowZip64=True) as out:
            out.write(db_path,"yanfolio.sqlite3")
            for key,size,chunk,expected in rows:
                chunk=chunk or cs.CHUNK_BYTES
                with (stage/key).open("rb") as src,out.open("objects/"+key,"w",force_zip64=True) as target:
                    n,digest=copy_object(src,target,chunk)
                if n!=size or (expected and digest!=expected):
                    raise ValueError("Object integrity mismatch: "+key)
                manifest["objects"].append({"id":key,"bytes":n,"chunk_size":chunk,"digest":digest})
            out.writestr("manifest.json",json.dumps(manifest,separators=(",",":")))
        os.chmod(packed,0o600)
        os.link(packed,output)
    return len(rows)


def restore(archive,target,key_file=None):
    target=Path(target).resolve()
    if target.exists():
        raise ValueError("Restore destination must be a new directory.")
    target.parent.mkdir(parents=True,exist_ok=True)
    key=read_key(key_file)
    with tempfile.TemporaryDirectory(prefix=".restore-",dir=target.parent) as temp,ZipFile(archive) as z:
        stage=Path(temp)/"service"
        stage.mkdir(mode=0o700)
        m=json.loads(z.read("manifest.json"))
        if m.get("format")!=1 or hashlib.sha256(key).hexdigest()!=m.get("key_fingerprint"):
            raise ValueError("Wrong master key or backup format.")
        db_path=stage/"yanfolio.sqlite3"
        with z.open("yanfolio.sqlite3") as src, db_path.open("xb") as out:
            shutil.copyfileobj(src,out)
        if sha(db_path)!=m["database_sha256"]:
            raise ValueError("Database checksum mismatch.")
        with closing(sqlite3.connect(db_path)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or db.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Database integrity check failed.")
            versions=dict(db.execute("SELECT id,bytes FROM cloud_versions"))
        if versions!={o["id"]:o["bytes"] for o in m["objects"]}:
            raise ValueError("Object index mismatch.")
        for obj in m["objects"]:
            k=obj["id"]
            if not re.fullmatch(r"[a-f0-9]{32}",k) or not 1<=obj["chunk_size"]<=8*1024*1024:
                raise ValueError("Invalid object metadata.")
            path=stage/"objects"/k[:2]/k
            path.parent.mkdir(parents=True,exist_ok=True)
            with z.open("objects/"+k) as src,path.open("xb") as out:
                length,digest=copy_object(src,out,obj["chunk_size"])
            if length!=obj["bytes"] or digest!=obj["digest"]:
                raise ValueError("Restored object checksum mismatch: "+k)
        if key_file or not os.getenv("YANFOLIO_MASTER_KEY"):
            path=stage/"master.key"
            path.write_bytes(key)
            os.chmod(path,0o600)
        if target.exists() or target.parent!=stage.parent.parent:
            raise ValueError("Restore destination changed.")
        stage.rename(target)
    return len(versions)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    commands=p.add_subparsers(dest="command",required=True)
    b=commands.add_parser("backup");b.add_argument("archive",type=Path)
    r=commands.add_parser("restore");r.add_argument("archive",type=Path);r.add_argument("target",type=Path);r.add_argument("--key-file",type=Path)
    args=p.parse_args()
    count=backup(args.archive) if args.command=="backup" else restore(args.archive,args.target,args.key_file)
    print(f"Completed {args.command}: {count} document version(s).")

