"""Create a verified operator account from the server console."""
import argparse
import getpass
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import accounts,store


def create(address,write_secret):
    address=accounts.email(address)
    store.init()
    password=secrets.token_urlsafe(24) if write_secret else getpass.getpass("New admin password (min 14 characters): ")
    if len(password)<14:
        raise SystemExit("Password must have at least 14 characters.")
    path=store.directory()/"admin-access.txt"
    with store.db(True) as c:
        if c.execute("SELECT 1 FROM users WHERE email=?",(address,)).fetchone():
            raise SystemExit("Account already exists; no changes made.")
        uid=c.execute("INSERT INTO users(email,password,role,created) VALUES(?,?,'admin',?)",(address,store.password_hash(password),store.now())).lastrowid
        store.audit(c,uid,"创建管理员",address)
        if write_secret:
            with path.open("x",encoding="utf-8") as handle:
                os.chmod(path,0o600)
                handle.write(f"管理后台 {store.public_origin()}/admin.html\n邮箱 {address}\n密码 {password}\n")
    print("Administrator created.",str(path) if write_secret else address)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--email",required=True)
    p.add_argument("--save-local-credentials",action="store_true")
    args=p.parse_args()
    create(args.email,args.save_local_credentials)

