import asyncio
import base64
from io import BytesIO
from zipfile import ZipFile

import httpx
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from fastapi.testclient import TestClient
from lxml import etree
from pypdf import PdfWriter

from app import formatting as fmt
from app import literature
from app.main import app

client = TestClient(app)


def packed(doc):
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


def fixtures():
    source = Document()
    source.add_paragraph("绿地与温度",style="Title")
    source.add_heading("研究方法",1)
    p = source.add_paragraph("我们分析研究区域的遥感影像。")
    p.add_run("保留强调").italic = True
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr")," REF Fig1 \\h ")
    p._p.append(field)
    math = OxmlElement("m:oMath")
    run = OxmlElement("m:r")
    text = OxmlElement("m:t")
    text.text = "x+y"
    run.append(text)
    math.append(run)
    p._p.append(math)
    source.sections[0].header.paragraphs[0].text="研究手稿"
    source.add_table(rows=1,cols=1).cell(0,0).text="保留表格"
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
    source.add_picture(BytesIO(image),width=Cm(.6))
    template = Document()
    template.sections[0].left_margin=Cm(3)
    template.add_heading("方法",1).alignment=WD_ALIGN_PARAGRAPH.CENTER
    p = template.add_paragraph()
    sample = p.add_run("正文样例")
    sample.font.name="Cambria"
    sample.font.size=Pt(16)
    return packed(source),packed(template)


def test_template_rule_precedence_and_content_preservation():
    raw,template=fixtures()
    report,output=fmt.process(raw,template,"正文：宋体，小四，1.5 倍行距\n一级标题：黑体，三号，加粗，居中\n图表必须跨页续排",False)
    assert report["pending"]==["图表必须跨页续排"]
    assert report["paragraphs"]["正文"]==1 and report["sections"]==1
    with ZipFile(BytesIO(raw)) as before, ZipFile(BytesIO(output)) as after:
        assert before.namelist()==after.namelist()
        assert all(before.read(n)==after.read(n) for n in before.namelist() if n!=fmt.DOC)
        root_before=etree.fromstring(before.read(fmt.DOC))
        root_after=etree.fromstring(after.read(fmt.DOC))
        for expr in ("//w:t/text()","//w:fldSimple/@w:instr","//*[local-name()='oMath']//*[local-name()='t']/text()","//w:drawing//*/@*","//w:tbl//w:t/text()"):
            assert root_before.xpath(expr,namespaces=fmt.NS)==root_after.xpath(expr,namespaces=fmt.NS)
    reopened=Document(BytesIO(output))
    assert reopened.paragraphs[1].alignment==WD_ALIGN_PARAGRAPH.CENTER
    assert reopened.paragraphs[1].runs[0].bold
    assert reopened.paragraphs[2].runs[0].font.size.pt==12
    assert reopened.paragraphs[2].runs[0].font.name=="Cambria"
    assert reopened.paragraphs[2].runs[1].italic
    assert reopened.paragraphs[2].paragraph_format.line_spacing==1.5
    assert reopened.sections[0].left_margin==Cm(3) or abs(reopened.sections[0].left_margin.cm-3)<.01


def test_requirements_and_api_roundtrip():
    raw,template=fixtures()
    inputs={"manuscript":("原稿.docx",raw),"template":("模板.docx",template),"requirements":("要求.txt","正文：小四\n左边距 2.8 cm".encode())}
    r=client.post("/api/format/preview",files=inputs)
    assert r.status_code==200 and len(r.json()["recognized"])==2
    out=client.post("/api/format/apply",files=inputs)
    assert out.status_code==200
    assert abs(Document(BytesIO(out.content)).sections[0].left_margin.cm-2.8)<.01
    imported=client.post("/api/import",files={"manuscript":("thesis.docx",raw)}).json()
    assert imported["title"]=="绿地与温度" and "# 研究方法" in imported["text"]
    ref={"title":"Test of metadata","authors":["Author"],"year":"2024","doi":"10.1234/example"}
    new=client.post("/api/export",json={**imported,"references":[ref]})
    assert Document(BytesIO(new.content)).paragraphs[-1].text.endswith("10.1234/example")


def test_unknown_requirement_is_preserved_and_preview_blocks_noop():
    raw,_=fixtures()
    f={"manuscript":("paper.docx",raw),"requirements":("rules.txt","不要使用黑体\n脚注：宋体，小五".encode())}
    result=client.post("/api/format/preview",files=f).json()
    assert not result["changed"] and len(result["pending"])==2
    assert client.post("/api/format/apply",files=f).status_code==422
    req=Document();req.add_paragraph("正文：小四，段后 6 磅，首行缩进两个字符")
    result=client.post("/api/format/preview",files={"manuscript":("paper.docx",raw),"requirements":("rules.docx",packed(req))}).json()
    assert result["changed"] and not result["pending"]


def test_invalid_uploads_and_origin():
    assert client.post("/api/format/preview",files={"manuscript":("bad.docx",b"bad")},data={"instructions":"小四"}).status_code==422
    raw,_=fixtures()
    pdf=PdfWriter();pdf.add_blank_page(width=500,height=500);out=BytesIO();pdf.write(out)
    assert client.post("/api/format/preview",files={"manuscript":("a.docx",raw),"requirements":("r.pdf",out.getvalue())}).status_code==422
    assert client.post("/api/export",headers={"Origin":"https://elsewhere.example"},json={"title":"x","text":"y"}).status_code==403


def test_search_dedup_and_partial_failure(monkeypatch):
    def select(src,doi):
        return literature.record("Same paper",["Author"],2020,"Journal",doi,"https://example.org/paper",src)
    async def query(client,source,q,year):
        if source=="Europe PMC":
            raise httpx.ReadTimeout("unavailable")
        return [select(source,"HTTPS://DOI.ORG/10.1234/TEST" if source=="OpenAlex" else "")]
    monkeypatch.setattr(literature,"query",query)
    r=asyncio.run(literature.search("dedup regression","all",2020))
    assert len(r["items"])==1 and r["items"][0]["doi"]=="10.1234/test"
    assert r["items"][0]["sources"]==["Crossref","OpenAlex"]
    assert "不可用" in r["status"]["Europe PMC"]
    assert len(literature.merge([[select("A","10.1234/v1")],[select("B","10.1234/v2")]]))==2

