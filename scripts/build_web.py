"""Create the operator deployment archive from explicit, redistributable paths."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]


def build():
    output=ROOT/"dist"
    output.mkdir(exist_ok=True)
    inputs=[ROOT/x for x in (".dockerignore","LICENSE","requirements.txt","README.md","docs/architecture.md",
                             "docs/references.md","docs/technology.md","deploy/Dockerfile","deploy/Caddyfile","deploy/compose.yaml",
                             "scripts/create_admin.py")]
    inputs.extend(sorted((ROOT/"app").glob("*.py")))
    for suffix in ("*.html","*.js","*.css"):
        inputs.extend(sorted((ROOT/"app/static").glob(suffix)))
    if (output/"Yanfolio.exe").is_file():
        inputs.append(output/"Yanfolio.exe")
    target=output/"Yanfolio-Web.zip"
    with ZipFile(target.with_suffix(".part"),"w",compression=ZIP_DEFLATED) as archive:
        for path in inputs:
            archive.write(path,path.relative_to(ROOT).as_posix())
    target.with_suffix(".part").replace(target)
    print(target)


if __name__=="__main__":
    build()

