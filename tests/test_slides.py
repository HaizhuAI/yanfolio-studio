from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile
import json

from lxml import etree
from pptx import Presentation
import pytest

from app import agent,deck_render
from app.slide_content import Deck,Slide
from conftest import seed,new_client

SAMPLE=Deck(title="城市绿地与热环境",template="academic-ribbon",slides=[
 Slide(layout="cover",title="城市绿地与热环境",subtitle="一项观测研究的设计"),
 Slide(layout="content",title="如何界定研究问题？",body="比较相近建成环境中的绿地。\n明确观测时段和空间尺度。",notes="区分相关性与因果关系。"),
 Slide(layout="columns",title="两类数据的角色",left_title="遥感观测",left_body="地表温度\n空间分辨率",right_title="现场记录",right_body="植被覆盖\n采样条件"),
 Slide(layout="closing",title="下一步核实什么？",subtitle="核对数据来源、季节差异与混杂因素。")])


@pytest.mark.parametrize("key",["academic-ribbon","gaia-seminar","bricks-talk"])
def test_native_deck_template_preview_export_and_roundtrip(key):
    cli=seed()
    deck=SAMPLE.model_copy(update={"template":key})
    assert cli.get("/api/slides/templates/"+key+"/thumbnail").headers["content-type"].startswith("image/webp")
    response=cli.post("/api/slides/preview",json={"title":deck.title,"template":key,"slide":deck.slides[2].model_dump(),"number":3,"total":4})
    assert "现场记录" in response.json()["svg"] and not response.json()["overflow"]
    response=cli.post("/api/slides/export",json=deck.model_dump())
    assert response.status_code==200,response.text[:100]
    prs=Presentation(BytesIO(response.content))
    assert len(prs.slides)==4 and prs.slides[1].notes_slide.notes_text_frame.text==deck.slides[1].notes
    text=lambda slide:{sh.name:sh.text for sh in slide.shapes if sh.has_text_frame}
    assert text(prs.slides[0])["title"]==deck.title and text(prs.slides[2])["right_title"]=="现场记录"
    assert all(item.shape_type!=13 for slide in prs.slides for item in slide.shapes)
    for raw in [response.content,cli.get("/api/slides/templates/"+key+"/download").content]:
        with ZipFile(BytesIO(raw)) as z:
            assert b"Permission is hereby granted" in z.read("docProps/custom.xml")
    copy=cli.post("/api/slides/import?template="+key,files={"presentation":("test.pptx",response.content)}).json()
    assert copy==deck.model_dump()


def test_deck_edit_is_private_and_versioned():
    a=seed();b=seed("second@example.org");key=str(uuid4())
    url="/api/slides/drafts/"+key
    assert new_client().get("/api/slides/templates").status_code==401
    payload={"deck":SAMPLE.model_dump(),"version":0}
    assert a.put(url,json=payload).json()=={"version":1}
    assert a.put(url,json=payload).json()=={"version":1}
    assert b.get(url).status_code==404 and b.get("/api/slides/drafts").json()["items"]==[]
    payload["deck"]["title"]="修改后的题目"
    assert a.put(url,json=payload).status_code==409
    payload["version"]=1
    assert a.put(url,json=payload).json()["version"]==2
    assert a.delete(url+"?version=1").status_code==409
    assert a.get(url).json()["deck"]["title"]=="修改后的题目"


def test_ai_deck_bills_only_valid_persisted_draft(monkeypatch):
    a=seed(points=12)
    req={"action":"slides","title":"论文汇报","text":"研究采用访谈记录。","page_count":3,"template_id":"gaia-seminar","model_id":1}
    def execution():
        return {**req,"request_id":str(uuid4()),"quote":a.post("/api/write/quote",json=req).json()["quote"]}
    async def broken(*args):return '{"pages":["孤立的标题"]}',[35,8],True
    monkeypatch.setattr(agent,"invoke",broken)
    assert a.post("/api/write",json=execution()).status_code==502
    assert a.get("/api/me").json()["balance"]==12
    assert a.get("/api/slides/drafts").json()["items"]==[]
    async def good(*args):
        return json.dumps({"pages":[{"title":t,"points":["访谈材料需逐条核查。"]} for t in ("研究问题","材料来源","下一步")]},ensure_ascii=False),[80,60],True
    monkeypatch.setattr(agent,"invoke",good)
    body=execution()
    r=a.post("/api/write",json=body)
    assert r.status_code==200 and len(r.json()["presentation"]["deck"]["slides"])==3
    assert a.get("/api/slides/drafts/"+body["request_id"]).json()==r.json()["presentation"]
    assert a.post("/api/write",json=body).json()==r.json()
    assert a.get("/api/me").json()["balance"]==10


def test_appearance_persists_by_account_and_asset_access():
    a,b=seed(),seed("other@example.org")
    assert a.get("/api/preferences").json()["mode"]=="system"
    data={"mode":"dark","ui_font":"sans","reading_font":"serif","reading_size":20}
    assert a.put("/api/preferences",json=data).status_code==200
    assert a.get("/api/preferences").json()["reading_font"]=="serif"
    assert b.get("/api/preferences").json()["mode"]=="system"
    assert a.put("/api/preferences",json={**data,"mode":"unknown"}).status_code==422
    assert new_client().get("/appearance.js",follow_redirects=False).status_code==200
    r=new_client().get("/fonts/noto-sans-sc.woff2?v=06bfe0d6")
    assert r.content[:4]==b"wOF2" and "immutable" in r.headers["cache-control"]

