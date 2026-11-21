"""Install a pinned CPU runtime and an openly licensed text model into ignored local storage."""
import concurrent.futures
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]/".local"
MODEL = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
BUILD = "b8241"
ASSET = f"llama-{BUILD}-bin-win-cpu-x64.zip"


def fetch(url, headers=None):
    return urlopen(Request(url,headers={"User-Agent":"Yanfolio-local-setup/1.0",**(headers or {})}),timeout=75)


def verified(path,digest):
    if not path.exists():
        return False
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()==digest


def runtime():
    release = json.load(fetch("https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/"+BUILD))
    asset = next(a for a in release["assets"] if a["name"]==ASSET)
    digest = asset["digest"].removeprefix("sha256:")
    archive = ROOT/ASSET
    if not verified(archive,digest):
        with fetch(asset["browser_download_url"]) as r, archive.open("wb") as out:
            shutil.copyfileobj(r,out)
    if not verified(archive,digest):
        raise ValueError("Runtime checksum mismatch")
    with ZipFile(archive) as z:
        z.extractall(ROOT/"llama")
    print("CPU runtime verified.",flush=True)


def model():
    info = json.load(fetch("https://huggingface.co/api/models/"+REPO+"?blobs=true"))
    file = next(a for a in info["siblings"] if a["rfilename"]==MODEL)
    digest = file["lfs"]["sha256"]
    dest = ROOT/MODEL
    if verified(dest,digest):
        return
    url = "https://huggingface.co/"+REPO+"/resolve/"+info["sha"]+"/"+MODEL
    size = file["size"]
    stride = 16*1024*1024
    def part(start):
        end = min(start+stride,size)-1
        tmp = ROOT/(MODEL+"."+str(start)+".part")
        if tmp.exists() and tmp.stat().st_size==end-start+1:
            return tmp
        for attempt in range(4):
            try:
                with fetch(url+"?chunk="+str(start),{"Range":f"bytes={start}-{end}"}) as response:
                    if response.headers.get("Content-Range","").split("/")[0]!=f"bytes {start}-{end}":
                        raise ValueError("Range mismatch")
                    with tmp.open("wb") as out:
                        shutil.copyfileobj(response,out)
                if tmp.stat().st_size!=end-start+1:
                    raise ValueError("Incomplete model range")
                return tmp
            except Exception:
                if attempt==3:
                    raise
                time.sleep(2+attempt)
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        chunks=list(pool.map(part,range(0,size,stride)))
    tmp = dest.with_suffix(".partial")
    with tmp.open("wb") as out:
        for chunk in chunks:
            with chunk.open("rb") as src:
                shutil.copyfileobj(src,out)
    if not verified(tmp,digest):
        for chunk in chunks:
            chunk.unlink()
        raise ValueError("Model checksum mismatch")
    tmp.replace(dest)
    for chunk in chunks:
        chunk.unlink()
    print("Local model verified.",flush=True)


if __name__=="__main__":
    if sys.platform!="win32":
        raise SystemExit("The bundled CPU runtime setup targets Windows x64.")
    ROOT.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        jobs=[pool.submit(runtime),pool.submit(model)]
        for job in concurrent.futures.as_completed(jobs):
            job.result()

