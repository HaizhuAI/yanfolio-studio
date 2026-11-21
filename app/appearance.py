from typing import Literal
from fastapi import APIRouter,Request
from pydantic import BaseModel
from . import store as s
from .accounts import current

router=APIRouter()
SCHEMA="""CREATE TABLE IF NOT EXISTS appearance(uid INTEGER PRIMARY KEY REFERENCES users(id),mode TEXT NOT NULL,
 ui_font TEXT NOT NULL,reading_font TEXT NOT NULL,reading_size INTEGER NOT NULL);"""


class Preferences(BaseModel):
    mode:Literal["system","light","dark"]="system"
    ui_font:Literal["geist","system","sans","serif"]="geist"
    reading_font:Literal["system","sans","serif","interface"]="system"
    reading_size:Literal[16,18,20]=18


@router.get("/api/preferences")
def get_preferences(req:Request):
    uid=current(req)["id"]
    with s.db() as c:
        row=c.execute("SELECT * FROM appearance WHERE uid=?",(uid,)).fetchone()
    return dict(row) if row else {"uid":uid,**Preferences().model_dump()}


@router.put("/api/preferences")
def save_preferences(body:Preferences,req:Request):
    uid=current(req)["id"]
    with s.db(True) as c:
        c.execute("""INSERT INTO appearance VALUES(?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET mode=excluded.mode,
                   ui_font=excluded.ui_font,reading_font=excluded.reading_font,reading_size=excluded.reading_size""",
                  (uid,body.mode,body.ui_font,body.reading_font,body.reading_size))
    return {"uid":uid,**body.model_dump()}

