"""Read template examples and change only supported formatting in the source OPC package."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from lxml import etree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
DOC = "word/document.xml"
ROLES = {"body": "正文", "title": "论文标题", "h1": "一级标题", "h2": "二级标题", "h3": "三级标题", "caption": "图表题注", "ref": "参考文献条目"}
RUN = {"rFonts": ("ascii", "hAnsi", "eastAsia", "cs"), "sz": ("val",), "szCs": ("val",)}
HEADING_RUN = {**RUN, "b": ("val",), "bCs": ("val",)}
PARA = {"spacing": ("before", "after", "line", "lineRule"), "ind": ("left", "right", "firstLine", "firstLineChars", "hanging", "hangingChars"), "jc": ("val",)}
PAGE = {"pgSz": ("w", "h", "orient"), "pgMar": ("top", "right", "bottom", "left", "header", "footer", "gutter")}
# Child order comes from the WordprocessingML schema.
P_ORDER = "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange".split()
R_ORDER = "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange".split()
S_ORDER = "headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange".split()


def tag(name):
    return f"{{{W}}}{name}"


def val(node, key="val"):
    return node.get(tag(key)) if node is not None else None


def child(parent, name, order=()):
    node = parent.find(tag(name))
    if node is None:
        node = ET.Element(tag(name))
        rank = order.index(name) if name in order else -1
        for i, item in enumerate(parent):
            local = ET.QName(item).localname if isinstance(item.tag, str) else ""
            if local in order and order.index(local) > rank:
                parent.insert(i, node)
                break
        else:
            if not order:
                parent.insert(0, node)
            else:
                parent.append(node)
    return node


def xml(raw):
    root = ET.fromstring(raw, ET.XMLParser(resolve_entities=False, load_dtd=False, no_network=True))
    if root.getroottree().docinfo.doctype:
        raise ValueError("文件包含不支持的 XML 文档类型声明。")
    return root


class Package:
    def __init__(self, raw):
        try:
            self.zip = ZipFile(BytesIO(raw))
            entries = self.zip.infolist()
            names = {e.filename for e in entries}
            if (len(entries) > 4000 or len(entries) != len(names) or
                sum(e.file_size for e in entries) > 96_000_000 or
                any(e.file_size > 32_000_000 or e.flag_bits & 1 or ".." in PurePosixPath(e.filename).parts for e in entries)):
                raise ValueError("文档过大、已加密或包结构异常。")
            if any("vbaproject" in n.lower() or n.lower().startswith("_xmlsignatures/") for n in names):
                raise ValueError("请使用无宏且未签名的 DOCX 副本。")
            if DOC not in names or "[Content_Types].xml" not in names:
                raise ValueError("上传的文件不是有效的 Word Open XML 文档。")
            self.doc = xml(self.zip.read(DOC))
            if self.doc.tag != tag("document") or self.doc.find(tag("body")) is None:
                raise ValueError("当前支持 Word 默认保存的过渡型 DOCX。")
            self.styles = xml(self.zip.read("word/styles.xml")) if "word/styles.xml" in names else ET.Element(tag("styles"))
            self.nodes = {val(s, "styleId"): s for s in self.styles.findall(tag("style"))}
        except (BadZipFile, KeyError, ET.XMLSyntaxError, RuntimeError, NotImplementedError) as exc:
            raise ValueError("无法读取 Word 文件，请检查文件格式或重新另存为 DOCX。") from exc

    def paragraphs(self):
        return self.doc.xpath("/w:document/w:body/w:p", namespaces=NS)

    def save(self):
        out = BytesIO()
        with ZipFile(out, "w") as dest:
            for item in self.zip.infolist():
                raw = ET.tostring(self.doc, xml_declaration=True, encoding="UTF-8", standalone=True) if item.filename == DOC else self.zip.read(item)
                dest.writestr(item, raw)
        return out.getvalue()


def content(p):
    return "".join(p.xpath(".//w:t[not(ancestor::w:del)]/text()", namespaces=NS)).strip()


def style_chain(pkg, style_id):
    chain = []
    while style_id in pkg.nodes and len(chain) < 25:
        node = pkg.nodes[style_id]
        if node in chain:
            break
        chain.append(node)
        style_id = val(node.find(tag("basedOn")))
    return list(reversed(chain))


def role_of(pkg, p, text, references):
    sid = val(p.find("w:pPr/w:pStyle", NS))
    chain = list(reversed(style_chain(pkg, sid)))
    names = [s for n in chain for s in (val(n.find(tag("name"))), val(n, "styleId")) if s]
    for name in names:
        key = re.sub(r"[\s_-]+", "", name.lower())
        for prefix in ("heading", "标题"):
            if key.startswith(prefix) and key[len(prefix):] in ("1", "2", "3"):
                return "h" + key[len(prefix):]
        if key in ("title", "标题", "论文标题", "文档标题"):
            return "title"
        if key in ("caption", "题注", "图题", "表题"):
            return "caption"
        if key in ("bibliography", "参考文献条目"):
            return "ref"
    level = val(p.find("w:pPr/w:outlineLvl", NS))
    if level in ("0", "1", "2"):
        return "h" + str(int(level) + 1)
    if len(text) < 90:
        if re.match(r"^(第[一二三四五六七八九十百\d]+章|[一二三四五六七八九十]+、)", text) or re.fullmatch(r"摘\s*要|abstract|references|参考文献|引言|结论|绪论|致谢", text, re.I):
            return "h1"
        match = re.match(r"^(\d+(?:\.\d+){0,2})[\s、．]+(?=\S)", text)
        if match:
            return "h" + str(match.group(1).count(".") + 1)
        if re.match(r"^(图|表|Fig(?:ure)?\.?|Table)\s*\d+", text, re.I):
            return "caption"
    return "ref" if references else "body"


def classified(pkg):
    refs = False
    for p in pkg.paragraphs():
        text = content(p)
        if not text:
            continue
        role = role_of(pkg, p, text, refs)
        if role.startswith("h"):
            refs = bool(re.fullmatch(r"参考文献|references", text, re.I))
        yield role, p


def properties(container, spec):
    result = {}
    if container is not None:
        for kind, attrs in spec.items():
            item = container.find(tag(kind))
            for key in attrs:
                value = val(item, key)
                if value is None and item is not None and kind in ("b", "bCs"):
                    value = "1"
                if value is not None:
                    result[(kind, key)] = value
    return result


def template_profile(pkg):
    defaults = pkg.styles.find(tag("docDefaults"))
    base = {}
    def add_parts(target, container, path="", run_spec=RUN):
        if container is not None:
            for kind, allowed in (("rPr", run_spec), ("pPr", PARA)):
                target.update(properties(container.find(path + "w:" + kind, NS), allowed))
    if defaults is not None:
        for kind, allowed in (("rPr", RUN), ("pPr", PARA)):
            base.update(properties(defaults.find(f"w:{kind}Default/w:{kind}", NS), allowed))
    default_style = next((val(s, "styleId") for s in pkg.nodes.values() if val(s, "type") == "paragraph" and val(s, "default") == "1"), "Normal")
    for node in style_chain(pkg, default_style):
        add_parts(base, node)
    samples = defaultdict(list)
    def sample(role, sid, p=None):
        props = dict(base)
        run_spec = HEADING_RUN if role in ("title","h1","h2","h3") else RUN
        for node in style_chain(pkg, sid):
            add_parts(props, node, run_spec=run_spec)
        if p is not None:
            props.update(properties(p.find(tag("pPr")), PARA))
            runs = [r for r in p.findall(tag("r")) if content(r)]
            if runs:
                representative = max(runs, key=lambda r: len(content(r)))
                props.update(properties(representative.find(tag("rPr")), run_spec))
        samples[role].append(props)
    for role, p in classified(pkg):
        sample(role, val(p.find("w:pPr/w:pStyle", NS)), p)
    if not samples["body"]:
        sample("body", default_style)
    for sid in pkg.nodes:
        style = pkg.nodes[sid]
        if val(style, "type") != "paragraph":
            continue
        stub = ET.Element(tag("p"))
        child(child(stub, "pPr"), "pStyle").set(tag("val"), sid)
        role = role_of(pkg, stub, "", False)
        if role != "body" and not samples[role]:
            sample(role, sid)
    profile = {}
    for role, rows in samples.items():
        if rows:
            mode = Counter(tuple(sorted(row.items())) for row in rows)
            profile[role] = dict(mode.most_common(1)[0][0])
    sections = pkg.doc.xpath("/w:document/w:body/w:sectPr | /w:document/w:body/w:p/w:pPr/w:sectPr", namespaces=NS)
    page = properties(sections[-1], PAGE) if sections else {}
    return profile, page, len(sections)


FONTS = ["Times New Roman", "Arial", "Cambria", "Calibri", "仿宋_GB2312", "宋体", "黑体", "楷体", "仿宋", "微软雅黑", "等线"]
SIZES = {"小初":36,"初号":42,"小一":24,"一号":26,"小二":18,"二号":22,"小三":15,"三号":16,"小四":12,"四号":14,"小五":9,"五号":10.5,"小六":6.5,"六号":7.5}
ROLE_LABELS = {"正文":"body","论文标题":"title","文档标题":"title","一级标题":"h1","二级标题":"h2","三级标题":"h3","图表题注":"caption","题注":"caption","参考文献条目":"ref"}
MARGINS = {"上":"top","下":"bottom","左":"left","右":"right"}


def rules(text):
    profile, page, applied, pending = defaultdict(dict), {}, [], []
    for line in re.split(r"[\r\n；;。]+", text):
        line = line.strip()
        if not line:
            continue
        remainder = line
        if len(line) > 300 or re.search(r"不要|不得|禁止|除外|除非|不超过|至少|至多|不少于|不小于|不大于|不使用", line):
            pending.append(line)
            continue
        role_hits = [(label, role) for label, role in ROLE_LABELS.items() if label in line]
        if len({r for _, r in role_hits}) > 1:
            pending.append(line)
            continue
        role = role_hits[0][1] if role_hits else "body"
        for lab, _ in role_hits:
            remainder = remainder.replace(lab, "")
        props = {}
        section = {}
        traces = []
        def accept(fragment, label):
            nonlocal remainder
            remainder = remainder.replace(fragment, "")
            traces.append(label)
        for match in re.finditer(r"(?:(上|下|左|右)(?:侧)?(?:页边距|边距)?|(?:页边距|边距)(上|下|左|右))\s*[:：为]?\s*(\d+(?:\.\d+)?)\s*(厘米|毫米|cm|mm)", line, re.I):
            side = match[1] or match[2]
            cm = float(match[3]) / (10 if match[4].lower() in ("mm","毫米") else 1)
            if 0 <= cm <= 8:
                section["pgMar", MARGINS[side]] = str(round(cm * 1440 / 2.54))
                accept(match[0], f"{side}边距 {cm:g} cm")
        if re.search(r"\bA4\b|A4纸", line, re.I):
            section.update({("pgSz","w"):"11906", ("pgSz","h"):"16838", ("pgSz","orient"):"portrait"})
            accept(re.search(r"A4纸?",line,re.I)[0], "A4 纵向")
        for font in FONTS:
            if font.lower() in remainder.lower():
                match = re.search(re.escape(font), remainder, re.I)[0]
                for key in (("eastAsia",) if re.search(r"[\u3400-\u9fff]", font) else ("ascii","hAnsi")):
                    props["rFonts",key] = font
                accept(match, font)
        size_match = re.search("|".join(SIZES), remainder)
        pt_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:pt|磅)", remainder, re.I)
        if size_match:
            size = SIZES[size_match[0]]
            accept(size_match[0], f"{size:g} pt")
            props["sz","val"] = props["szCs","val"] = str(round(size*2))
        elif pt_match and 5 <= float(pt_match[1]) <= 72 and not re.search(r"固定|段前|段后|行距", remainder[:pt_match.start()][-5:]):
            size = float(pt_match[1])
            props["sz","val"] = props["szCs","val"] = str(round(size*2))
            accept(pt_match[0], f"{size:g} pt")
        match = re.search(r"(\d+(?:\.\d+)?)\s*倍(?:行距)?|单倍(?:行距)?|双倍(?:行距)?", remainder)
        if match:
            factor = float(match[1]) if match[1] else (1 if match[0].startswith("单") else 2)
            if 0.5 <= factor <= 5:
                props.update({("spacing","line"):str(round(factor*240)),("spacing","lineRule"):"auto"})
                accept(match[0], f"{factor:g} 倍行距")
        match = re.search(r"固定(?:值|行距)?\s*(\d+(?:\.\d+)?)\s*(?:磅|pt)", remainder, re.I)
        if match and 4 <= float(match[1]) <= 100:
            props.update({("spacing","line"):str(round(float(match[1])*20)),("spacing","lineRule"):"exact"})
            accept(match[0], match[0])
        match = re.search(r"首行缩进\s*([0-9一二两三四])\s*(?:个)?字符", remainder)
        if match:
            digits = {"一":1,"二":2,"两":2,"三":3,"四":4}
            props["ind","firstLineChars"] = str(int(digits.get(match[1],match[1]))*100)
            accept(match[0], match[0])
        for phrase, value in (("两端对齐","both"),("左对齐","left"),("右对齐","right"),("居中","center")):
            if phrase in remainder:
                props["jc","val"] = value
                accept(phrase, phrase)
        if "加粗" in remainder:
            props["b","val"] = props["bCs","val"] = "1"
            accept("加粗","加粗")
        for phrase, key in (("段前","before"),("段后","after")):
            match = re.search(phrase + r"\s*(\d+(?:\.\d+)?)\s*(?:磅|pt)", remainder, re.I)
            if match and 0 <= float(match[1]) <= 100:
                props["spacing",key] = str(round(float(match[1])*20))
                accept(match[0],match[0])
        # Apply only complete, unambiguous clauses, so unsupported instructions never silently change other roles.
        residue = re.sub(r"字体|字号|页边距|页面|纸张|行距|使用|采用|设置为|设置|要求|纵向|号|为|的|和|与|[、，,：:\s]", "", remainder)
        if traces and not residue:
            profile[role].update(props)
            page.update(section)
            applied.append(f"{ROLES[role]} · " + "、".join(traces) if props else "、".join(traces))
        else:
            pending.append(line)
    return profile, page, applied, pending


def set_values(parent, data, order):
    for (kind, key), value in data.items():
        item = child(parent, kind, order)
        if kind == "rFonts":
            item.attrib.pop(tag(key + "Theme"), None)
            if key == "cs":
                item.attrib.pop(tag("cstheme"), None)
        if kind == "ind" and key in ("firstLine", "firstLineChars", "hanging", "hangingChars"):
            conflict = ("hanging","hangingChars") if key.startswith("firstLine") else ("firstLine","firstLineChars")
            for attr in conflict:
                item.attrib.pop(tag(attr), None)
            if key in ("firstLine","hanging") and (kind,key+"Chars") not in data:
                item.attrib.pop(tag(key+"Chars"),None)
        if kind == "spacing" and key in ("before","after"):
            for suffix in ("Autospacing","Lines"):
                item.attrib.pop(tag(key+suffix), None)
        item.set(tag(key), value)


def process(original, template, instructions, preview):
    pkg = Package(original)
    profile, page, nsect = template_profile(Package(template)) if template else ({}, {}, 0)
    explicit, page_rules, applied, pending = rules(instructions)
    for name, props in explicit.items():
        profile.setdefault(name, {}).update(props)
    page.update(page_rules)
    counts = Counter()
    for role, p in classified(pkg):
        fields = profile.get(role, {})
        if not fields:
            continue
        rvals = {k:v for k,v in fields.items() if k[0] in HEADING_RUN}
        pvals = {k:v for k,v in fields.items() if k[0] in PARA}
        if pvals:
            set_values(child(p,"pPr"),pvals,P_ORDER)
        if rvals:
            for r in p.xpath("w:r[w:t] | w:hyperlink/w:r[w:t]",namespaces=NS):
                set_values(child(r,"rPr"),rvals,R_ORDER)
        counts[ROLES[role]] += 1
    sections = pkg.doc.xpath("/w:document/w:body/w:sectPr | /w:document/w:body/w:p/w:pPr/w:sectPr", namespaces=NS)
    if page and not sections:
        sections = [ET.SubElement(pkg.doc.find(tag("body")),tag("sectPr"))]
    if page:
        for section in sections:
            set_values(section,page,S_ORDER)
    warnings = []
    if nsect > 1:
        warnings.append("模板含多个节，页面尺寸与边距取自模板末节，应用到原稿各节。")
    summary = {"paragraphs":dict(counts),"sections":len(sections) if page else 0,"recognized":applied,"pending":pending,"warnings":warnings,
               "template_roles":[ROLES[k] for k in profile if profile[k]] if template else [],
               "changed":bool(counts or (page and sections))}
    return summary, None if preview else pkg.save()

