import hashlib
import hmac
import json
import os
import secrets
from uuid import UUID
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import store as s
from .accounts import current

router=APIRouter()


def stripe_ready():
    return bool(os.getenv("YANFOLIO_STRIPE_KEY") and os.getenv("YANFOLIO_STRIPE_WEBHOOK"))


@router.get("/api/wallet")
def wallet(req:Request):
    from .agent import expire
    uid=current(req)["id"]
    with s.db(True) as c:
        expire(c)
        balance=c.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone()[0]
        history=[dict(x) for x in c.execute("SELECT delta,after,kind,note,created FROM ledger WHERE uid=? ORDER BY id DESC LIMIT 100",(uid,))]
        orders=[dict(x) for x in c.execute("SELECT id,points,cents,currency,status,created FROM orders WHERE uid=? ORDER BY created DESC LIMIT 50",(uid,))]
        packs=[dict(x) for x in c.execute("SELECT id,label,points,cents FROM packs WHERE enabled=1 ORDER BY cents")]
    return {"balance":balance,"ledger":history,"orders":orders,"packs":packs,"online":stripe_ready()}


class Redeem(BaseModel):
    code:str=Field(min_length=8,max_length=100)


@router.post("/api/wallet/redeem")
def redeem(body:Redeem,req:Request):
    uid=current(req)["id"]
    s.rate("redeem:"+str(uid),20,600)
    h=s.digest(body.code.upper().strip())
    with s.db(True) as c:
        row=c.execute("SELECT * FROM vouchers WHERE hash=?",(h,)).fetchone()
        if not row or row["uid"] is not None:
            raise HTTPException(400,"兑换码无效或已使用。")
        c.execute("UPDATE vouchers SET uid=?,redeemed=? WHERE hash=?",(uid,s.now(),h))
        balance=s.post_points(c,uid,row["points"],"voucher",h,"兑换码充值")
    return {"balance":balance,"points":row["points"]}


class Checkout(BaseModel):
    pack_id:int
    request_id:UUID


@router.post("/api/wallet/checkout")
async def checkout(body:Checkout,req:Request):
    if not stripe_ready():
        raise HTTPException(503,"商户尚未启用在线支付，可使用已购买的兑换码。")
    uid=current(req)["id"]
    order_id=str(body.request_id)
    with s.db(True) as c:
        row=c.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
        if row:
            if row["uid"]!=uid or row["pack"]!=body.pack_id or row["status"]!="pending":
                raise HTTPException(409,"订单已变更，请刷新钱包。")
            if row["url"]:
                return {"url":row["url"],"id":order_id}
            cents,points=row["cents"],row["points"]
        else:
            pack=c.execute("SELECT * FROM packs WHERE id=? AND enabled=1",(body.pack_id,)).fetchone()
            if not pack:
                raise HTTPException(404,"该套餐已下架。")
            cents,points=pack["cents"],pack["points"]
            c.execute("INSERT INTO orders(id,uid,pack,points,cents,currency,provider,status,created) VALUES(?,?,?,?,?,'cny','stripe','pending',?)",
                      (order_id,uid,body.pack_id,points,cents,s.now()))
    base=s.public_origin()
    data={"mode":"payment","client_reference_id":order_id,"metadata[order_id]":order_id,"line_items[0][quantity]":"1",
          "line_items[0][price_data][currency]":"cny","line_items[0][price_data][unit_amount]":str(cents),
          "line_items[0][price_data][product_data][name]":f"砚稿 · {points} 点","success_url":base+"/wallet.html?checkout=return","cancel_url":base+"/wallet.html"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.post("https://api.stripe.com/v1/checkout/sessions",data=data,headers={"Authorization":"Bearer "+os.environ["YANFOLIO_STRIPE_KEY"],"Idempotency-Key":order_id})
            r.raise_for_status()
            session=r.json()
            if urlparse(session["url"]).hostname!="checkout.stripe.com":
                raise ValueError
        with s.db(True) as c:
            c.execute("UPDATE orders SET provider_id=?,url=? WHERE id=?",(session["id"],session["url"],order_id))
        return {"url":session["url"],"id":order_id}
    except (ValueError,KeyError,httpx.HTTPError) as exc:
        raise HTTPException(502,"暂时无法创建收款页面，可以重试同一笔订单。") from exc


@router.post("/api/payments/stripe")
async def stripe_callback(req:Request):
    secret=os.getenv("YANFOLIO_STRIPE_WEBHOOK","")
    if not secret:
        raise HTTPException(503,"收款渠道未配置。")
    raw=await req.body()
    fields=[x.partition("=") for x in req.headers.get("stripe-signature","").split(",")]
    try:
        stamp=next(v for k,_,v in fields if k=="t")
        if abs(s.now()-int(stamp))>300:
            raise ValueError
        expected=hmac.new(secret.encode(),stamp.encode()+b"."+raw,hashlib.sha256).hexdigest()
        if not any(k=="v1" and hmac.compare_digest(v,expected) for k,_,v in fields):
            raise ValueError
        event=json.loads(raw)
        kind=event["type"]
        obj=event["data"]["object"]
    except (ValueError,StopIteration,TypeError,KeyError) as exc:
        raise HTTPException(400,"回调校验失败。") from exc
    if kind not in ("checkout.session.completed","checkout.session.async_payment_succeeded","checkout.session.expired","checkout.session.async_payment_failed"):
        return {"received":True}
    order_id=(obj.get("metadata") or {}).get("order_id")
    with s.db(True) as c:
        row=c.execute("SELECT * FROM orders WHERE id=?",(order_id,)).fetchone()
        if not row:
            return {"received":True}
        if (row["provider_id"] not in (None,obj.get("id")) or obj.get("client_reference_id")!=order_id or obj.get("mode")!="payment"
                or obj.get("amount_total")!=row["cents"] or obj.get("currency")!=row["currency"]):
            raise HTTPException(400,"回调与订单不匹配。")
        if row["status"]=="paid":
            return {"received":True}
        if kind in ("checkout.session.expired","checkout.session.async_payment_failed"):
            c.execute("UPDATE orders SET status='closed' WHERE id=?",(order_id,))
        elif obj.get("payment_status")=="paid":
            s.post_points(c,row["uid"],row["points"],"purchase",order_id,"在线充值")
            c.execute("UPDATE orders SET provider_id=?,status='paid',paid=? WHERE id=?",(obj["id"],s.now(),order_id))
    return {"received":True}

