"""Build the redistributable x64 WebView2 client with the Windows Framework compiler."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/".local"/"webview2"
VERSION="1.0.4370.26"
DIGEST="1c0dacac84b70109b3fd42f90c53a0ba942abc3a87590d7a4e0ccd86e4a06cf4"
URL=f"https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/{VERSION}/microsoft.web.webview2.{VERSION}.nupkg"


def build(service):
    uri=urlsplit(service)
    if (uri.scheme!="https" and not(uri.scheme=="http" and uri.hostname in {"localhost","127.0.0.1","::1"})) or not uri.hostname or uri.username or uri.password or uri.path not in ("","/") or uri.query or uri.fragment:
        raise ValueError("Use an HTTPS or loopback origin without a path.")
    BUILD.mkdir(parents=True,exist_ok=True)
    dest=ROOT/"dist"
    dest.mkdir(exist_ok=True)
    archive=BUILD/"sdk.nupkg"
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest()!=DIGEST:
        urllib.request.urlretrieve(URL,archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=DIGEST:
        raise ValueError("WebView2 SDK checksum mismatch")
    parts=["lib/net462/Microsoft.Web.WebView2.Core.dll","lib/net462/Microsoft.Web.WebView2.WinForms.dll","runtimes/win-x64/native/WebView2Loader.dll","LICENSE.txt"]
    with zipfile.ZipFile(archive) as sdk:
        for part in parts:
            (BUILD/Path(part).name).write_bytes(sdk.read(part))
    config=BUILD/"Endpoint.cs"
    config.write_text("internal static class BuildConfig { public const string ServiceUrl = "+json.dumps(service.rstrip("/")+"/")+"; }")
    csc=Path(os.environ["WINDIR"])/"Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    switches=[str(csc),"/nologo","/target:winexe","/platform:x64","/optimize+","/codepage:65001","/r:System.Windows.Forms.dll","/r:System.Drawing.dll"]
    client=BUILD/"Yanfolio.Workspace.exe"
    subprocess.run([*switches,"/out:"+str(client),*["/r:"+str(BUILD/Path(p).name) for p in parts[:2]],str(config),str(ROOT/"desktop/Window.cs")],check=True)
    resources=[client.name,*[Path(p).name for p in parts]]
    binary=dest/"Yanfolio.exe"
    subprocess.run([*switches,"/out:"+str(binary),*["/resource:"+str(BUILD/n)+","+n for n in resources],str(ROOT/"desktop/Launcher.cs")],check=True)
    print(binary,hashlib.sha256(binary.read_bytes()).hexdigest())


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--service-url",default="http://127.0.0.1:8769")
    build(parser.parse_args().service_url)

