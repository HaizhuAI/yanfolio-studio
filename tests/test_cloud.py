import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from app import cloud_store as cs, store as s
from conftest import new_client,seed


def spec(name,data,**kwargs):
    return {"name":name,"size":len(data),"client_id":str(uuid4()),**kwargs}


def chunk(cli,key,offset,data):
    return cli.put(f"/api/drive/uploads/{key}/part?offset={offset}",content=data,
                   headers={"X-Chunk-SHA256":hashlib.sha256(data).hexdigest()})


def create(cli,name,data,**kwargs):
    start=cli.post("/api/drive/uploads",json=spec(name,data,**kwargs))
    assert start.status_code==200,start.text
    key=start.json()["id"]
    for offset in range(0,len(data),cs.CHUNK_BYTES):
        r=chunk(cli,key,offset,data[offset:offset+cs.CHUNK_BYTES])
        assert r.status_code==200,r.text
    result=cli.post(f"/api/drive/uploads/{key}/finish",json={})
    assert result.status_code==200,result.text
    return result.json()


def test_public_page_private_account_and_sessions():
    guest=new_client()
    assert "从文献笔记" in guest.get("/").text
    assert guest.get("/yanfolio-field.webp").headers["content-type"]=="image/webp"
    assert guest.get("/profile.html",follow_redirects=False).status_code==303
    assert guest.get("/api/drive").status_code==401
    user=seed()
    user.put("/api/profile",json={"name":"张研","institution":"研究院","discipline":"史学"})
    second=new_client()
    second.post("/api/auth/login",json={"email":"editor@example.org","password":"secure-example-password"})
    profile=second.get("/api/profile").json()
    assert profile["profile"]["name"]=="张研" and profile["storage"]["quota"]==5_000_000_000
    other=next(d for d in profile["devices"] if not d["current"])
    assert second.post("/api/profile/devices/"+other["device"]+"/revoke",json={}).status_code==200
    assert user.get("/api/drive").status_code==401
    assert second.get("/api/drive").status_code==200


def test_upload_resume_two_clients_private_download_and_orphan_tail(monkeypatch):
    monkeypatch.setattr(cs,"CHUNK_BYTES",4)
    a=seed()
    b=seed("other@example.org")
    second=new_client()
    second.post("/api/auth/login",json={"email":"editor@example.org","password":"secure-example-password"})
    data=b"123456789"
    folder=a.post("/api/drive/folders",json={"name":"研究项目"}).json()["id"]
    body=spec("甲.txt",data,folder=folder)
    u=a.post("/api/drive/uploads",json=body).json()["id"]
    assert second.post("/api/drive/uploads",json=body).json()["id"]==u
    assert a.post(f"/api/drive/uploads/{u}/finish",json={}).status_code==409
    assert chunk(a,u,4,b"5678").status_code==409
    assert chunk(a,u,0,b"1234").status_code==200
    assert chunk(second,u,0,b"1234").json()["offset"]==4
    assert chunk(a,u,0,b"abcd").status_code==409
    assert b.get("/api/drive/uploads/"+u).status_code==404
    with cs.object_path(u).open("ab") as handle:
        handle.write(b"uncommitted tail")
    assert second.get("/api/drive/uploads/"+u).json()["parts"][0]["sha"]==hashlib.sha256(b"1234").hexdigest()
    assert chunk(second,u,4,b"5678").status_code==200
    assert chunk(second,u,8,b"9").status_code==200
    f=second.post(f"/api/drive/uploads/{u}/finish",json={}).json()
    assert a.post(f"/api/drive/uploads/{u}/finish",json={}).json()==f
    path="/api/drive/files/"+f["file_id"]
    assert a.get(path+"/download").content==data
    assert a.get("/api/drive?folder="+folder).json()["storage"]["used"]==len(data)
    assert b.get(path+"/download").status_code==404
    assert b.get(path+"/versions").status_code==404
    assert b.post(path,json={"action":"trash","expected":u}).status_code==404
    assert b.get("/api/drive?q=甲").json()["total"]==0


def test_quota_atomic_reservations_and_upload_pause():
    op=seed("admin@example.org","admin")
    a=seed()
    uid=a.get("/api/me").json()["id"]
    assert op.put(f"/api/admin/cloud/users/{uid}",json={"bytes":10}).status_code==200
    def reserve(i):
        c=new_client()
        c.cookies.update(a.cookies)
        return c.post("/api/drive/uploads",json=spec(str(i)+".txt",b"1234567"))
    with ThreadPoolExecutor(2) as pool:
        replies=list(pool.map(reserve,[1,2]))
    assert sorted(x.status_code for x in replies)==[200,413]
    key=next(x for x in replies if x.status_code==200).json()["id"]
    assert op.put(f"/api/admin/cloud/users/{uid}",json={"bytes":6}).status_code==409
    assert a.get("/api/admin/cloud").status_code==403
    op.put("/api/admin/cloud/uploads",json={"enabled":False})
    assert chunk(a,key,0,b"1234567").status_code==503
    op.put("/api/admin/cloud/uploads",json={"enabled":True})
    assert chunk(a,key,0,b"1234567").status_code==200
    a.post(f"/api/drive/uploads/{key}/cancel",json={})
    assert a.get("/api/profile").json()["storage"]["available"]==10
    assert not cs.object_path(key).exists()


def test_versions_trash_conflict_and_release():
    a=seed()
    original=create(a,"现场.md",b"one")
    fid,v1=original["file_id"],original["version"]
    new=create(a,"第二稿.md",b"two!",file_id=fid,base_version=v1)
    v2=new["version"]
    assert a.post("/api/drive/uploads",json=spec("过时.md",b"bad",file_id=fid,base_version=v1)).status_code==409
    url="/api/drive/files/"+fid
    def action(op,head,value=""):
        return a.post(url,json={"action":op,"expected":head,"value":value})
    assert action("restore_version",v2,v1).status_code==200
    assert a.get(url+"/download").content==b"one"
    assert action("delete_version",v1,v1).status_code==409
    assert action("trash",v1).status_code==200
    assert a.get("/api/drive?trash=true").json()["storage"]["trash"]==7
    assert a.get(url+"/download").status_code==404
    assert action("restore",v1).status_code==200
    assert action("delete_version",v1,v2).status_code==200
    assert not cs.object_path(v2).exists()
    assert action("trash",v1).status_code==200 and action("purge",v1).status_code==200
    assert a.get("/api/drive").json()["storage"]["used"]==0
    assert not cs.object_path(v1).exists()


def test_maintenance_expiry_and_validation():
    a=seed()
    assert a.post("/api/drive/uploads",json=spec("../bad.txt",b"x")).status_code==422
    assert a.post("/api/drive/uploads",json=spec("program.exe",b"x")).status_code==415
    f=create(a,"归档.txt",b"old")
    u=a.post("/api/drive/uploads",json=spec("未完成.txt",b"x")).json()["id"]
    chunk(a,u,0,b"x")
    with s.db(True) as c:
        c.execute("UPDATE cloud_uploads SET expires=0 WHERE id=?",(u,))
        c.execute("UPDATE cloud_files SET trashed=1 WHERE id=?",(f["file_id"],))
    cs.expire()
    assert not cs.object_path(f["version"]).exists() and not cs.object_path(u).exists()
    assert a.get("/api/drive/transfers").json()==[]

