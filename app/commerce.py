from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import store as s
from .accounts import current

router=APIRouter()


@router.get("/api/wallet")
def wallet(req:Request):
    from .agent import expire
    uid=current(req)["id"]
    with s.db(True) as c:
        expire(c)
        balance=c.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone()[0]
        history=[dict(x) for x in c.execute("SELECT delta,after,kind,note,created FROM ledger WHERE uid=? ORDER BY id DESC LIMIT 100",(uid,))]
        packs=[dict(x) for x in c.execute("SELECT id,label,points,cents FROM packs WHERE enabled=1 ORDER BY cents")]
    return {"balance":balance,"ledger":history,"packs":packs}


class Redeem(BaseModel):
    code:str=Field(min_length=8,max_length=100)


@router.post("/api/wallet/redeem")
def redeem(body:Redeem,req:Request):
    uid=current(req)["id"]
    s.rate("redeem:"+str(uid),20,600)
    h=s.digest(body.code.upper().strip())
    with s.db(True) as c:
        row=c.execute("SELECT * FROM vouchers WHERE hash=?",(h,)).fetchone()
        if row and row["uid"]==uid:
            balance=c.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone()[0]
            return {"balance":balance,"points":row["points"],"already":True}
        if not row or row["uid"] is not None or row["revoked"]:
            raise HTTPException(400,"兑换码无效或已使用。")
        c.execute("UPDATE vouchers SET uid=?,redeemed=? WHERE hash=?",(uid,s.now(),h))
        balance=s.post_points(c,uid,row["points"],"voucher",h,"兑换码充值")
    return {"balance":balance,"points":row["points"]}


