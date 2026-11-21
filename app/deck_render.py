"""Apply trusted native PowerPoint prototypes and draw the editor preview from their geometry."""
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import json
import re
import unicodedata
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Pt

ASSETS=Path(__file__).parent/"deck_assets"
SLOTS={"title","eyebrow","footer","subtitle","body","left_title","left_body","right_title","right_body"}
LAYOUTS=("cover","content","columns","closing")
EMU_PT=12700


@lru_cache(maxsize=1)
def templates():
    records=json.loads((ASSETS/"catalog.json").read_text(encoding="utf-8-sig"))["templates"]
    return {t["id"]:t for t in records}


def template(key):
    if key not in templates():
        raise ValueError("所选模板不存在。")
    return templates()[key]


@lru_cache(maxsize=12)
def _binary(key):
    item=template(key)
    return (ASSETS/item["file"]).read_bytes()


def _em(ch):
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in ("W","F"):
        return 1
    if ch.isspace():
        return .32
    return .68 if ch.isupper() or ch.isdigit() else .55


def _wrap(text,limit):
    rows=[]
    line=""
    width=0
    for token in re.findall(r"[A-Za-z0-9]+|\s+|.",text):
        tw=sum(_em(ch) for ch in token)
        if token.isspace():
            line+=token;width+=tw
            continue
        if line and width+tw>limit:
            rows.append(line)
            line="";width=0
        if tw>limit:
            for ch in token:
                cw=_em(ch)
                if line and width+cw>limit:
                    rows.append(line);line="";width=0
                line+=ch;width+=cw
        else:
            line+=token;width+=tw
    if line or not rows:
        rows.append(line)
    return rows


def _color(value,fallback):
    try:
        return "#"+str(value.rgb) if value.type==MSO_COLOR_TYPE.RGB else fallback
    except (AttributeError,ValueError,TypeError):
        return fallback


def _font_spec(p):
    run=p.runs[0] if p.runs else None
    size=(run.font.size if run is not None else None) or p.font.size or Pt(22)
    return size.pt,deepcopy(run._r.rPr) if run is not None and run._r.rPr is not None else None


def _apply_text(shape,text,warnings):
    tf=shape.text_frame
    p=tf.paragraphs[0]
    size,style=_font_spec(p)
    alignment=p.alignment
    width=(shape.width-tf.margin_left-tf.margin_right)/EMU_PT
    height=(shape.height-tf.margin_top-tf.margin_bottom)/EMU_PT
    paras=text.replace("\r\n","\n").replace("\r","\n").split("\n")
    # The same explicit soft breaks and point sizes are used in both outputs.
    min_size=min(size,11.0)
    while True:
        wrapped=[_wrap(line,max(1,width/(size*1.05))) for line in paras]
        needed=sum(len(lines)*size*1.22 for lines in wrapped)+(len(paras)-1)*size*.20
        if needed<=height+.6 or size<=min_size:
            break
        size=max(min_size,size-1)
    if text and needed>height+1:
        warnings.append(shape.name)
    tf.clear()
    tf.word_wrap=True
    tf.auto_size=MSO_AUTO_SIZE.NONE
    for i,lines in enumerate(wrapped):
        pg=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        pg.alignment=alignment
        pg.space_before=Pt(0)
        pg.space_after=Pt(size*.20 if i<len(wrapped)-1 else 0)
        pg.line_spacing=Pt(size*1.22)
        for k,line in enumerate(lines):
            if k:
                pg.add_line_break()
            r=pg.add_run()
            if style is not None:
                r._r.insert(0,deepcopy(style))
            r.text=line
            r.font.size=Pt(size)


def _populate(slide,data,index,total,title):
    values=data.model_dump()
    values["title"]=values["title"] or (title if data.layout=="cover" else "")
    values["footer"]=f"{index} / {total}"
    warnings=[]
    for shape in slide.shapes:
        if shape.name in SLOTS and shape.has_text_frame:
            _apply_text(shape,values.get(shape.name,""),warnings)
    return warnings


def _clone(prs,proto):
    slide=prs.slides.add_slide(proto.slide_layout)
    tree=slide.shapes._spTree
    for shape in list(slide.shapes):
        tree.remove(shape.element)
    for shape in proto.shapes:
        tree.insert_element_before(deepcopy(shape.element),"p:extLst")
    bg=proto._element.cSld.bg
    if bg is not None:
        slide._element.cSld.insert(0,deepcopy(bg))
    return slide


def export(deck):
    prs=Presentation(BytesIO(_binary(deck.template)))
    prototypes=dict(zip(LAYOUTS,list(prs.slides),strict=True))
    template_ids=list(prs.slides._sldIdLst)
    for i,data in enumerate(deck.slides,1):
        slide=_clone(prs,prototypes[data.layout])
        slide._element.cSld.set("name","Yanfolio:"+data.layout)
        overflow=_populate(slide,data,i,len(deck.slides),deck.title)
        if overflow:
            raise ValueError(f"第 {i} 页文字超出模板可读范围，请精简或拆页。")
        if data.notes:
            slide.notes_slide.notes_text_frame.text=data.notes
    for item in template_ids:
        prs.part.drop_rel(item.rId)
        prs.slides._sldIdLst.remove(item)
    prs.core_properties.title=deck.title
    prs.core_properties.keywords="Yanfolio:"+deck.template
    prs.core_properties.author="Yanfolio"
    prs.core_properties.last_modified_by="Yanfolio"
    output=BytesIO();prs.save(output)
    return output.getvalue()


def _fill(shape):
    if shape.fill.type==MSO_FILL.SOLID:
        return _color(shape.fill.fore_color,"none")
    return "none"


def _draw_text(svg,shape,x,y,w,h,ink):
    tf=shape.text_frame
    left,right,top,bottom=[v/EMU_PT for v in (tf.margin_left,tf.margin_right,tf.margin_top,tf.margin_bottom)]
    lines=[]
    for pg in tf.paragraphs:
        r=pg.runs[0] if pg.runs else None
        if not r:
            continue
        size,_=_font_spec(pg)
        lead=pg.line_spacing
        step=lead.pt if hasattr(lead,"pt") else size*(lead or 1.22)
        for text in pg.text.split("\v"):
            lines.append((pg,r,size,step,text))
        if pg.space_after:
            lines.append((pg,r,size,pg.space_after.pt,None))
    total=sum(a[3] for a in lines)
    y+=top
    if tf.vertical_anchor==MSO_ANCHOR.MIDDLE:
        y+=max(0,(h-top-bottom-total)/2)
    elif tf.vertical_anchor==MSO_ANCHOR.BOTTOM:
        y+=max(0,h-top-bottom-total)
    for pg,r,size,step,text in lines:
        if text:
            align=pg.alignment
            tx=x+w/2 if align==PP_ALIGN.CENTER else (x+w-right if align==PP_ALIGN.RIGHT else x+left)
            anchor="middle" if align==PP_ALIGN.CENTER else ("end" if align==PP_ALIGN.RIGHT else "start")
            is_serif=any(n in (r.font.name or "").lower() for n in ("serif","宋","georgia","times"))
            font="SimSun,serif" if is_serif else "Microsoft YaHei,Noto Sans CJK SC,sans-serif"
            item=etree.SubElement(svg,"text",x=str(tx),y=str(y+size*.93),fill=_color(r.font.color,ink),
                      attrib={"font-size":str(size),"font-family":font,"text-anchor":anchor,
                              "font-weight":"700" if r.font.bold else "400","font-style":"italic" if r.font.italic else "normal"})
            item.text=text
        y+=step


def preview(key,layout,data=None,index=1,total=1,title=""):
    prs=Presentation(BytesIO(_binary(key)))
    slide=prs.slides[LAYOUTS.index(layout)]
    warnings=_populate(slide,data,index,total,title) if data else []
    colors=template(key)["colors"]
    sw,sh=prs.slide_width/EMU_PT,prs.slide_height/EMU_PT
    root=etree.Element("svg",nsmap={None:"http://www.w3.org/2000/svg"},viewBox=f"0 0 {sw} {sh}",width=str(sw),height=str(sh))
    background=colors["background"]
    if slide.background.fill.type==MSO_FILL.SOLID:
        background=_color(slide.background.fill.fore_color,background)
    etree.SubElement(root,"rect",width=str(sw),height=str(sh),fill=background)
    for shape in slide.shapes:
        x,y,w,h=[v/EMU_PT for v in (shape.left,shape.top,shape.width,shape.height)]
        if shape.shape_type==MSO_SHAPE_TYPE.LINE:
            etree.SubElement(root,"line",x1=str(x),y1=str(y),x2=str(x+w),y2=str(y+h),stroke=_color(shape.line.color,colors["accent"]),
                             attrib={"stroke-width":str((shape.line.width or Pt(1)).pt)})
            continue
        if not shape.has_text_frame:
            continue
        group=etree.SubElement(root,"g")
        if shape.rotation:
            group.set("transform",f"rotate({shape.rotation} {x+w/2} {y+h/2})")
        fill=_fill(shape)
        if fill!="none":
            if shape.shape_type==MSO_SHAPE_TYPE.AUTO_SHAPE and shape.auto_shape_type==MSO_AUTO_SHAPE_TYPE.OVAL:
                etree.SubElement(group,"ellipse",cx=str(x+w/2),cy=str(y+h/2),rx=str(w/2),ry=str(h/2),fill=fill)
            else:
                etree.SubElement(group,"rect",x=str(x),y=str(y),width=str(w),height=str(h),fill=fill)
        _draw_text(group,shape,x,y,w,h,colors["ink"])
    return etree.tostring(root,encoding="unicode"),warnings

