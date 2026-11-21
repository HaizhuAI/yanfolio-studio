"""Debounced source-only sync to this checkout's private origin. No force pushes."""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "GIT_TERMINAL_PROMPT":"0", "GCM_INTERACTIVE":"Never"}
LOG = ROOT/".git"/"yanfolio-sync.log"
PATHS = ["desktop/app.manifest","app/static/yanfolio-optic.webp","app/static/geist.woff2","app/static/geist-license.txt","app/static/yanfolio.ico","app/static/yanfolio-field.webp",".dockerignore","deploy/Dockerfile","deploy/Caddyfile","deploy/compose.yaml",":(glob)desktop/*.cs",".gitignore",".gitattributes","README.md","LICENSE","requirements.txt","start.ps1",
         ":(glob)app/*.py",":(glob)app/static/*.html",":(glob)app/static/*.js",":(glob)app/static/*.css",
         ":(glob)scripts/*.py",":(glob)scripts/*.ps1",":(glob)docs/*.md",":(glob)tests/*.py"]


def run(args, *, data=None, check=True):
    result = subprocess.run(args,cwd=ROOT,env=ENV,input=data,text=True,encoding="utf-8",errors="replace",
                            capture_output=True,timeout=50,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed ({result.returncode})")
    return result


def git(*args,check=True):
    return run(["git",*args],check=check).stdout.strip()


def private_origin():
    url = git("remote","get-url","--push","origin")
    match = re.fullmatch(r"https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?",url)
    if not match:
        raise RuntimeError("Expected a GitHub HTTPS origin.")
    owner,repo = match.groups()
    creds = run(["git","credential","fill"],data=f"protocol=https\nhost=github.com\nusername={owner}\n\n",check=False)
    fields = dict(s.split("=",1) for s in creds.stdout.splitlines() if "=" in s)
    if fields.get("password"):
        auth = "Basic " + base64.b64encode((fields.get("username",owner)+":"+fields["password"]).encode()).decode()
    else:
        auth = "Bearer "+run(["gh","auth","token"]).stdout.strip()
    req = Request(f"https://api.github.com/repos/{owner}/{repo}",headers={"Authorization":auth,"User-Agent":"Yanfolio-private-sync"})
    with urlopen(req,timeout=18) as response:
        remote = json.load(response)
    if remote.get("private") is not True or remote["full_name"].casefold()!=f"{owner}/{repo}".casefold():
        raise RuntimeError("Remote is not the configured private repository.")


def changed():
    return git("status","--porcelain","--untracked-files=all","--",*PATHS)


def sync():
    if git("branch","--show-current")!="main":
        raise RuntimeError("Automatic sync waits for main.")
    gd = ROOT/".git"
    if any((gd/name).exists() for name in ("MERGE_HEAD","CHERRY_PICK_HEAD","rebase-merge","rebase-apply","index.lock")):
        raise RuntimeError("Automatic sync waits for the active Git operation.")
    if git("diff","--cached","--name-only"):
        raise RuntimeError("Automatic sync waits for manually staged edits.")
    edit = changed()
    head = git("rev-parse","--verify","HEAD",check=False)
    remote = git("rev-parse","--verify","refs/remotes/origin/main",check=False)
    if not edit and head and head==remote:
        return
    private_origin()
    if edit:
        candidates = git("-c","core.quotepath=false","ls-files","-co","--exclude-standard","-z","--",*PATHS).split("\0")
        files = sorted({f for f in candidates if f})
        if not files:
            return
        # Intent-to-add makes new paths eligible for an atomic, path-limited commit.
        new_files = [f for f in git("-c","core.quotepath=false","ls-files","--others","--exclude-standard","-z","--",*PATHS).split("\0") if f]
        if new_files:
            git("add","--intent-to-add","--",*new_files)
        git("commit","--only","-m","Sync workspace source "+datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"--",*files)
    git("push","--set-upstream","origin","refs/heads/main:refs/heads/main")
    log("Pushed "+git("rev-parse","--short","HEAD"))


def log(message):
    if LOG.exists() and LOG.stat().st_size>150_000:
        LOG.replace(LOG.with_suffix(".old"))
    with LOG.open("a",encoding="utf-8") as f:
        f.write(datetime.now().isoformat(timespec="seconds")+" "+message+"\n")


def watch():
    # Debounce until source mtimes settle. Reattempt failed pushes even without new edits.
    stamp = None
    due = 0
    while True:
        try:
            files = git("ls-files","-co","--exclude-standard","--",*PATHS).splitlines()
            state = tuple((f,(ROOT/f).stat().st_mtime_ns) for f in files if (ROOT/f).is_file())
            if state!=stamp:
                stamp = state
                due = time.monotonic()+3
            elif time.monotonic()>=due:
                sync()
                due = time.monotonic()+30
        except Exception as exc:
            log(str(exc))
            time.sleep(20)
        time.sleep(2)


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch",action="store_true")
    args = parser.parse_args()
    if args.watch:
        watch()
    else:
        try:
            sync()
        except Exception as exc:
            print(str(exc),file=sys.stderr)
            sys.exit(1)

