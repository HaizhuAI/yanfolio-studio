import asyncio
import struct
import zlib
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
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

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
    cached = OxmlElement("w:r")
    cached_text = OxmlElement("w:t")
    cached_text.text = "表 1"
    cached.append(cached_text)
    field.append(cached)
    p._p.append(field)
    math = OxmlElement("m:oMath")
    run = OxmlElement("m:r")
    text = OxmlElement("m:t")
    text.text = "x+y"
    run.append(text)
    math.append(run)
    p._p.append(math)
    source.sections[0].header.paragraphs[0].text="研究手稿"
    table = source.add_table(rows=1,cols=2)
    table.style="Table Grid"
    caption = table.cell(0,0).paragraphs[0]
    mark = OxmlElement("w:bookmarkStart")
    mark.set(qn("w:id"),"0")
    mark.set(qn("w:name"),"Fig1")
    caption._p.append(mark)
    caption.add_run("表 1")
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"),"0")
    caption._p.append(end)
    table.cell(0,1).text="保留表格"
    def chunk(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
    width,height = 80,20
    # A two-colour measurement strip with valid PNG checksums.
    row = b"\x00"+bytes([48,108,85])*(width//2)+bytes([196,140,62])*(width//2)
    image = b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))
    image += chunk(b"IDAT",zlib.compress(row*height))+chunk(b"IEND",b"")
    source.add_picture(BytesIO(image),width=Cm(3))
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


def test_text_pdf_rule_and_model_citation_check(monkeypatch):
    pdf=PdfWriter()
    page=pdf.add_blank_page(width=500,height=500)
    font=DictionaryObject({NameObject("/Type"):NameObject("/Font"),NameObject("/Subtype"):NameObject("/Type1"),NameObject("/BaseFont"):NameObject("/Helvetica")})
    page[NameObject("/Resources")]=DictionaryObject({NameObject("/Font"):DictionaryObject({NameObject("/F1"):font})})
    stream=DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 30 440 Td (A4) Tj ET")
    page[NameObject("/Contents")]=pdf._add_object(stream)
    output=BytesIO()
    pdf.write(output)
    original,_=fixtures()
    result=client.post("/api/format/preview",files={"manuscript":("a.docx",original),"requirements":("rules.pdf",output.getvalue())}).json()
    assert result["sections"]==1 and result["recognized"]==["A4 纵向"]
    monkeypatch.setenv("YANFOLIO_AI_BASE_URL","http://localhost:3000/v1")
    monkeypatch.setenv("YANFOLIO_AI_MODEL","test-model")
    async def answer(self,url,headers,json):
        assert "题名" in json["messages"][1]["content"]
        assert "10.1234/abc" in json["messages"][1]["content"]
        return httpx.Response(200,request=httpx.Request("POST",url),json={"choices":[{"message":{"content":"比较两种方法 [1][9]。"}}]})
    monkeypatch.setattr(httpx.AsyncClient,"post",answer)
    reply=client.post("/api/write",json={"action":"review","title":"题目","text":"原句","references":[{"title":"文献","doi":"10.1234/abc"}]})
    assert reply.status_code==200 and reply.json()["unlinked_citations"]==[9]


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

