import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app


@pytest.fixture(autouse=True)
def isolated_service(tmp_path,monkeypatch):
    monkeypatch.setenv("YANFOLIO_DATA",str(tmp_path/"service"))
    monkeypatch.setenv("YANFOLIO_PUBLIC_URL","http://127.0.0.1:8769")
    monkeypatch.setenv("YANFOLIO_AI_BASE_URL","http://localhost:3000/v1")
    monkeypatch.setenv("YANFOLIO_AI_MODEL","test-model")
    for k in ("YANFOLIO_SMTP_HOST","YANFOLIO_MASTER_KEY","YANFOLIO_FAST_BASE_URL","YANFOLIO_OBJECT_DIR"):
        monkeypatch.delenv(k,raising=False)
    store.init()


def new_client():
    return TestClient(app,headers={"X-Yanfolio-Request":"1"})


def seed(email="editor@example.org",role="user",points=0):
    with store.db(True) as c:
        uid=c.execute("INSERT INTO users(email,password,role,created) VALUES(?,?,?,?)",
                      (email,store.password_hash("secure-example-password"),role,store.now())).lastrowid
        if points:
            store.post_points(c,uid,points,"test","fixture","测试")
    cli=new_client()
    r=cli.post("/api/auth/login",json={"email":email,"password":"secure-example-password"})
    assert r.status_code==200
    return cli

