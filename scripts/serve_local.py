"""Run the local service and own only model processes created by this invocation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
import uvicorn

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def read_url(url):
    try:
        with urlopen(url,timeout=2) as r:
            return json.load(r)
    except OSError:
        return {}


def serve(port):
    owned=[]
    os.environ.setdefault("YANFOLIO_PUBLIC_URL",f"http://127.0.0.1:{port}")
    try:
        for size,model_port,setting in [("1.5",18769,"YANFOLIO_AI_BASE_URL"),("0.5",18770,"YANFOLIO_FAST_BASE_URL")]:
            model=ROOT/".local"/f"qwen2.5-{size}b-instruct-q4_k_m.gguf"
            if os.getenv(setting) or not model.is_file():
                continue
            alias=f"Yanfolio-Qwen2.5-{size}B"
            api=f"http://127.0.0.1:{model_port}"
            existing=read_url(api+"/v1/models")
            if existing and alias not in [r["id"] for r in existing.get("data",[])]:
                raise RuntimeError(f"Port {model_port} already serves a different model.")
            if not existing:
                binary=next((ROOT/".local/llama").rglob("llama-server.exe"))
                proc=subprocess.Popen([str(binary),"-m",str(model),"--host","127.0.0.1","--port",str(model_port),"--alias",alias,"--ctx-size","8192","--parallel","1","--threads","4","--n-gpu-layers","0"],
                                      creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                owned.append(proc)
                for _ in range(65):
                    if proc.poll() is not None:
                        raise RuntimeError("Model process stopped: "+alias)
                    if read_url(api+"/health").get("status")=="ok":
                        break
                    time.sleep(.5)
                else:
                    raise RuntimeError("Model did not become ready: "+alias)
            os.environ[setting]=api+"/v1"
            if size=="1.5":
                os.environ["YANFOLIO_AI_MODEL"]=alias
        uvicorn.run("app.main:app",host="127.0.0.1",port=port)
    finally:
        for proc in owned:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8769)
    serve(parser.parse_args().port)

