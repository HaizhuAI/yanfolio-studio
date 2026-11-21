"""Validated slide content shared by the editor, the metered agent and PPTX export."""
import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Layout=Literal["cover","content","columns","closing"]


class Slide(BaseModel):
    layout:Layout="content"
    title:str=Field(default="",max_length=90)
    eyebrow:str=Field(default="",max_length=60)
    subtitle:str=Field(default="",max_length=240)
    body:str=Field(default="",max_length=950)
    left_title:str=Field(default="",max_length=55)
    left_body:str=Field(default="",max_length=480)
    right_title:str=Field(default="",max_length=55)
    right_body:str=Field(default="",max_length=480)
    notes:str=Field(default="",max_length=2000)

    @field_validator("*",mode="after")
    @classmethod
    def valid_text(cls,value):
        if any(ord(ch)<32 and ch not in "\t\n\r" for ch in value):
            raise ValueError("文本中含无效的控制字符")
        return value


class Deck(BaseModel):
    title:str=Field(min_length=1,max_length=120)
    template:str=Field(min_length=1,max_length=48)
    slides:list[Slide]=Field(min_length=1,max_length=32)

    @field_validator("title")
    @classmethod
    def valid_title(cls,value):
        value=value.strip()
        if not value or any(ord(ch)<32 for ch in value):
            raise ValueError("演示稿名称需要可见文本。")
        return value


def outline_schema(count):
    fields={name+str(i):{"type":"string"} for i in range(1,count+1) for name in ("t","p")}
    return {"type":"object","properties":fields,"required":list(fields),"additionalProperties":False}


def parse_outline(raw,count):
    cleaned=re.sub(r"^['\x60]{3}(?:json)?\s*|\s*['\x60]{3}$","",raw.strip(),flags=re.I)
    try:
        data=json.loads(cleaned)
        if isinstance(data,dict) and set(data)==set(outline_schema(count)["properties"]) and all(isinstance(v,str) for v in data.values()):
            rows=[{"title":data[f"t{i}"],"points":data[f"p{i}"].splitlines()} for i in range(1,count+1)]
        else:
            rows=data.get("pages") if isinstance(data,dict) else data
    except json.JSONDecodeError:
        rows=[re.sub(r"^\s*(?:\d+[.、)]\s*|[-*]\s+)","",x).strip() for x in cleaned.splitlines() if "|" in x or "｜" in x]
    if not isinstance(rows,list) or len(rows)!=count:
        raise ValueError("模型未给出所选页数")
    output=[]
    for i,row in enumerate(rows):
        if isinstance(row,dict) and isinstance(row.get("title"),str) and isinstance(row.get("points"),list) and all(isinstance(p,str) for p in row["points"]):
            parts=[row["title"].strip(),*[p.strip() for p in row["points"] if p.strip()]]
        elif isinstance(row,str):
            parts=[x.strip() for x in re.split(r"[|｜]",row) if x.strip()]
            if len(parts)==1:
                parts=re.split(r"[：:]",parts[0],maxsplit=1)
        else:
            raise ValueError("模型返回了无法编辑的内容")
        if len(parts)<2 or not parts[0] or len(parts[0])>90:
            raise ValueError("演示大纲缺少标题或要点")
        if i in (0,count-1):
            output.append(Slide(layout="cover" if i==0 else "closing",title=parts[0],subtitle="\n".join(parts[1:])))
        else:
            output.append(Slide(layout="content",title=parts[0],body="\n".join(parts[1:])))
    return output

