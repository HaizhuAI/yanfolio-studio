const $=id=>document.getElementById(id), el=YF.el;
$("logout").onclick=YF.logout;
async function load(){const [user,w]=await Promise.all([YF.api("/api/me"),YF.api("/api/wallet")]);$("owner").textContent=user.email;$("balance").textContent=w.balance;
 $("packs").replaceChildren(...w.packs.map(p=>{const a=el("div",undefined,"pack");a.append(el("span",p.label),el("strong",p.points+" 点"),el("small","参考售价 ¥"+(p.cents/100).toFixed(2)));return a;}));
 $("usage").replaceChildren(...w.usage.map(x=>{const row=el("tr");[YF.date(x.created),x.label+" / "+x.expert,x.passes,x.input_tokens+" / "+x.output_tokens+(x.reported?"":"（上游报告不全）"),x.points].forEach(v=>row.append(el("td",v)));return row;}));
 if(!w.usage.length){const row=el("tr"),cell=el("td","暂无 AI 使用记录");cell.colSpan=5;row.append(cell);$("usage").append(row);}
 $("rows").replaceChildren(...w.ledger.map(x=>{const row=el("tr");[YF.date(x.created),x.note,(x.delta>0?"+":"")+x.delta,x.after].forEach(v=>row.append(el("td",v)));return row;}));
 if(!w.ledger.length){const row=el("tr"),cell=el("td","暂无点数变动");cell.colSpan=4;row.append(cell);$("rows").append(row);}
}
$("redeem").onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector("button");b.disabled=true;try{const r=await YF.api("/api/wallet/redeem","POST",{code:$("code").value.trim()});$("feedback").textContent=(r.already?"该兑换码已在本账号入账 ":"已到账 ")+r.points+" 点";$("code").value="";await load();}catch(err){$("feedback").textContent=err.message;}finally{b.disabled=false;}};
load().catch(e=>$("feedback").textContent=e.message);

