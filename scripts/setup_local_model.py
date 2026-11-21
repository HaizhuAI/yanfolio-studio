"""Download a hash-pinned, CPU-only Windows writing model into ignored local storage."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import shutil
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]/".local"
MODEL = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
REVISION = "91cad51170dc346986eccefdc2dd33a9da36ead9"
MODEL_SHA = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
MODEL_SIZE = 1117320736
BUILD = "b8241"
ASSET = f"llama-{BUILD}-bin-win-cpu-x64.zip"
RUNTIME_SHA = "527f0cd2315bfeb22adc46f562cf9f06b3c6a1288a27f5851e6e5e71eb058833"


def verified(path,digest):
    if not path.exists():
        return False
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()==digest


def download(url, name, size, digest, stride, workers):
    dest = ROOT/name
    if verified(dest,digest):
        return dest
    def part(start):
        end = min(start+stride,size)-1
        tmp = ROOT/(name+"."+str(start)+".part")
        for attempt in range(5):
            try:
                have = tmp.stat().st_size if tmp.exists() else 0
                if have==end-start+1:
                    return tmp
                if have>end-start+1:
                    tmp.unlink()
                    have=0
                pos = start+have
                headers = {"User-Agent":"Yanfolio-local-setup/1.0","Range":f"bytes={pos}-{end}"}
                req = Request(url+"?yanfolio_range="+str(pos),headers=headers)
                with urlopen(req,timeout=60) as response:
                    if response.headers.get("Content-Range","").split("/")[0]!=f"bytes {pos}-{end}":
                        raise ValueError("Download server returned an unexpected byte range")
                    with tmp.open("ab") as out:
                        shutil.copyfileobj(response,out,128*1024)
                if tmp.stat().st_size!=end-start+1:
                    raise ValueError("Incomplete model range")
                return tmp
            except Exception:
                if attempt==4:
                    raise
                time.sleep(attempt+1)
    with ThreadPoolExecutor(workers) as pool:
        chunks=list(pool.map(part,range(0,size,stride)))
    tmp = dest.with_suffix(".partial")
    with tmp.open("wb") as out:
        for chunk in chunks:
            with chunk.open("rb") as src:
                shutil.copyfileobj(src,out)
    if not verified(tmp,digest):
        for chunk in chunks:
            chunk.unlink()
        raise ValueError("Checksum mismatch for "+name)
    tmp.replace(dest)
    for chunk in chunks:
        chunk.unlink()
    print("Verified "+name,flush=True)
    return dest


def runtime():
    url = f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/{ASSET}"
    archive = download(url,ASSET,33712292,RUNTIME_SHA,1024*1024,8)
    with ZipFile(archive) as z:
        for item in z.infolist():
            path=ROOT/"llama"/item.filename
            if not path.is_file() or path.stat().st_size!=item.file_size:
                z.extract(item,ROOT/"llama")


def model(modelscope):
    url = (f"https://modelscope.cn/models/{REPO}/resolve/master/{MODEL}" if modelscope else
           f"https://huggingface.co/{REPO}/resolve/{REVISION}/{MODEL}")
    download(url,MODEL,MODEL_SIZE,MODEL_SHA,16*1024*1024,12)


if __name__=="__main__":
    if sys.platform!="win32":
        raise SystemExit("This runtime setup targets Windows x64.")
    parser=argparse.ArgumentParser()
    parser.add_argument("--modelscope",action="store_true",help="Use Qwen's ModelScope mirror with identical SHA-256 verification.")
    parser.add_argument("--with-fast",action="store_true",help="Also install the smaller writing model.")
    options=parser.parse_args()
    ROOT.mkdir(exist_ok=True)
    with ThreadPoolExecutor(2) as pool:
        jobs=[pool.submit(runtime),pool.submit(model,options.modelscope)]
        if options.with_fast:
            name = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
            url = ("https://modelscope.cn/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/master/" if options.modelscope else
                   "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/9217f5db79a29953eb74d5343926648285ec7e67/")+name
            jobs.append(pool.submit(download,url,name,491400032,"74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",16*1024*1024,12))
        for job in jobs:
            job.result()

