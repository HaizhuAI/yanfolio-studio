import re
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
from app import agent,store as s
from conftest import new_client,seed


def test_verified_registration_and_recovery():
    cli=new_client()
    addr="reader@example.org"
    payload={"email":addr,"password":"long-example-pass"}
    assert cli.get("/api/search?q=test").status_code==401
    assert cli.get("/").status_code==200
    assert cli.get("/studio",follow_redirects=False).headers["location"]=="/login.html?next=/studio"
    assert cli.post("/api/auth/register",json={**payload,"code":"00000000"}).status_code==400
    def code(purpose):
        response=cli.post("/api/auth/code",json={"email":addr,"purpose":purpose})
        assert response.status_code==200 and "code" not in response.json()
        file=s.directory()/"mail"/(s.digest(addr+"|"+purpose)[:18]+".txt")
        return re.search(r"\b\d{8}\b",file.read_text(encoding="utf-8"))[0]
    otp=code("register")
    response=cli.post("/api/auth/register",json={**payload,"code":otp})
    assert response.json()["role"]=="user" and response.json()["balance"]==0
    assert "HttpOnly" in response.headers["set-cookie"]
    assert cli.get("/api/admin/overview").status_code==403
    assert cli.post("/api/auth/register",json={**payload,"code":otp}).status_code==400
    assert cli.post("/api/auth/reset",json={**payload,"code":code("reset"),"password":"replacement-long-password"}).status_code==200
    assert cli.get("/api/me").status_code==401
    assert cli.post("/api/auth/login",json=payload).status_code==401


def test_concurrent_voucher_redemption_preserves_issued_price():
    op=seed("owner@example.org","admin")
    clients=[seed("a@example.org"),seed("b@example.org")]
    batch=op.post("/api/admin/vouchers",json={"pack":1,"count":2}).json()
    assert op.post("/api/admin/packs",json={"id":1,"label":"调整后套餐","points":120,"cents":1200}).status_code==200
    with ThreadPoolExecutor(2) as pool:
        replies=list(pool.map(lambda c:c.post("/api/wallet/redeem",json={"code":batch["codes"][0]}),clients))
    assert sorted(x.status_code for x in replies)==[200,400]
    assert sum(c.get("/api/wallet").json()["balance"] for c in clients)==100
    assert op.post("/api/admin/batches/"+batch["batch"]+"/revoke",json={}).json()["revoked"]==1
    assert clients[0].post("/api/wallet/redeem",json={"code":batch["codes"][1]}).status_code==400
    assert not any(code in op.get("/api/admin/overview").text for code in batch["codes"])


def test_billing_charge_refund_idempotency_and_stale_quote(monkeypatch):
    op=seed("owner@example.org","admin")
    user=seed(points=200)
    mid=op.post("/api/admin/models",json={"label":"高级","model":"test","base":"https://example.org/v1","secret":"test-secret-value",
                "fee":3,"input_rate":2,"output_rate":4,"max_output":128}).json()["id"]
    assert "test-secret-value" not in op.get("/api/admin/overview").text
    assert "example.org" not in user.get("/api/catalog").text
    req={"model_id":mid,"action":"draft","title":"气候与遥感","text":"本研究采用遥感数据。","level":"peer"}
    q=user.post("/api/write/quote",json=req).json()
    assert q["passes"]==2 and q["expert"]=="环境科学专家"
    def body():
        return {**req,"request_id":str(uuid4()),"quote":q["quote"]}
    calls=[]
    async def answer(client,m,ms):
        calls.append(len(ms))
        return "草案 [99]",[40,10],True
    monkeypatch.setattr(agent,"invoke",answer)
    job=body()
    r=user.post("/api/write",json=job)
    assert r.status_code==200 and r.json()["charged"]==7 and r.json()["unlinked_citations"]==[99]
    assert user.post("/api/write",json=job).json()==r.json() and calls==[2,4]
    assert user.get("/api/wallet").json()["balance"]==193
    async def fail(*args):
        raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr(agent,"invoke",fail)
    assert user.post("/api/write",json=body()).status_code==502
    assert user.get("/api/wallet").json()["balance"]==193
    with s.db(True) as c:
        c.execute("UPDATE models SET fee=4 WHERE id=?",(mid,))
    assert user.post("/api/write",json=body()).status_code==409
    assert user.get("/api/wallet").json()["balance"]==193


def test_account_bound_workspace_and_concurrent_writes():
    a,b=seed("alpha@example.org"),seed("beta@example.org")
    doc={"active":"d","docs":[{"id":"d","title":"A","text":"Private A","references":[]}],"library":[]}
    assert a.put("/api/workspace",json={"version":0,"content":doc}).json()["version"]==1
    assert a.put("/api/workspace",json={"version":0,"content":doc}).status_code==409
    assert b.get("/api/workspace").json()["content"] is None
    assert b.put("/api/workspace",headers={"X-Yanfolio-Account":str(a.get("/api/me").json()["id"])},json={"version":0,"content":doc}).status_code==409
    assert a.post("/api/auth/logout",json={}).status_code==200 and a.get("/api/workspace").status_code==401


def test_insufficient_balance_and_crash_recovery(monkeypatch):
    user=seed(points=5)
    req={"model_id":1,"action":"review","title":"T","text":"Data"}
    q=user.post("/api/write/quote",json=req).json()
    with s.db(True) as c:
        uid=c.execute("SELECT id FROM users").fetchone()[0]
        s.post_points(c,uid,-5,"reserve","old","pending")
        c.execute("INSERT INTO jobs(id,uid,fingerprint,status,reserved,created) VALUES('old',?,'hash','pending',5,?)",(uid,s.now()))
    assert user.post("/api/write",json={**req,"quote":q["quote"],"request_id":str(uuid4())}).status_code==402
    with s.db(True) as c:
        c.execute("UPDATE jobs SET created=0")
    for _ in range(2):
        assert user.get("/api/wallet").json()["balance"]==5


def test_parallel_generations_reserve_one_available_charge(monkeypatch):
    user=seed(points=2)
    other=new_client()
    other.cookies.update(user.cookies)
    payload={"model_id":1,"action":"polish","text":"原文","title":"T"}
    quoted=user.post("/api/write/quote",json=payload).json()
    job={**payload,"request_id":str(uuid4()),"quote":quoted["quote"]}
    entered,finish=threading.Event(),threading.Event()
    async def wait_for_provider(*args):
        entered.set()
        assert await asyncio.to_thread(finish.wait,8)
        return "原文。",[10,4],True
    monkeypatch.setattr(agent,"invoke",wait_for_provider)
    with ThreadPoolExecutor(1) as pool:
        first=pool.submit(user.post,"/api/write",json=job)
        try:
            assert entered.wait(5)
            assert other.post("/api/write",json=job).status_code==409
            assert other.post("/api/write",json={**job,"request_id":str(uuid4())}).status_code==402
        finally:
            finish.set()
        assert first.result().json()["charged"]==2
    assert other.get("/api/wallet").json()["balance"]==0

