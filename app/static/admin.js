const $=id=>document.getElementById(id),el=YF.el;
let modelId=null,packId=null,batchId="",state;
$("logout").onclick=YF.logout;
function msg(s){$("feedback").textContent=s;}
function button(label,fn){const b=el("button",label,"text-btn");b.type="button";b.onclick=()=>Promise.resolve(fn()).catch(e=>msg(e.message));return b;}
function table(id,heads,rows){const t=el("table"),h=el("tr");heads.forEach(x=>h.append(el("th",x)));t.append(h);rows.forEach(cols=>{const row=el("tr");cols.forEach(x=>{const cell=el("td");if(x instanceof Node)cell.append(x);else cell.textContent=x;row.append(cell);});t.append(row);});$(id).replaceChildren(rows.length?t:el("p","暂无记录","sub"));}
function modelActions(m){const wrap=el("div",undefined,"inline");wrap.append(button("编辑",()=>editModel(m)),button("测试",async()=>{msg("正在检查模型接口…");const r=await YF.api("/api/admin/models/"+m.id+"/test","POST",{});msg(r.found?"已连接，模型列表包含 "+m.model:"已连接，但列表中未找到 "+m.model);}));return wrap;}
function editModel(m){modelId=m?.id||null;const f=$("model-form");f.reset();$("model-title").textContent=m?"编辑模型 · "+m.label:"添加模型";if(m)for(const k of ["label","model","base","fee","max_output","input_rate","output_rate","enabled"])f.elements[k].value=m[k];f.elements.secret.placeholder=m?.has_secret?"密钥已配置，留空保留":"可选，输入服务端密钥";f.elements.label.focus();}
function editPack(p){packId=p?.id||null;const f=$("pack-form");f.reset();if(p){for(const k of ["label","points","enabled"])f.elements[k].value=p[k];f.elements.yuan.value=(p.cents/100).toFixed(2);}f.elements.label.focus();}
async function load(){state=await YF.api("/api/admin/overview?q="+encodeURIComponent($("user-q").value));$("metrics").replaceChildren(...[["用户",state.metrics.users],["兑换到账",state.metrics.redeemed],["已消费点数",state.metrics.consumed],["完成任务",state.metrics.jobs]].map(([a,b])=>{const m=el("div",undefined,"metric");m.append(el("span",a),el("strong",b));return m;}));
 table("models",["名称","上游模型","基础点/次","千输入 / 千输出","状态",""],state.models.map(m=>[m.label,m.model,m.fee,m.input_rate+" / "+m.output_rate,m.enabled?"已启用":"已下架",modelActions(m)]));
 table("usage",["模型","调用次数","已报告输入 / 输出 Token","实收点数","用量报告不全的任务"],state.usage.map(m=>[m.label,m.calls,m.inputs+" / "+m.outputs,m.points,m.incomplete]));
 table("packs",["套餐","点数","参考价","状态",""],state.packs.map(p=>[p.label,p.points,"¥"+(p.cents/100).toFixed(2),p.enabled?"在售":"下架",button("编辑",()=>editPack(p))]));
 $("issue-pack").replaceChildren(...state.packs.filter(p=>p.enabled).map(p=>new Option(p.label+" · "+p.points+" 点",p.id)));
 table("batches",["批次","套餐","每码点数","发行 / 已兑 / 停用",""],state.batches.map(a=>[a.batch,a.label,a.points,a.issued+" / "+a.redeemed+" / "+a.revoked,a.issued>a.redeemed+a.revoked?button("停用未兑码",async()=>{if(!confirm("停用此批次剩余未兑换的码？"))return;await YF.api("/api/admin/batches/"+a.batch+"/revoke","POST",{});await load();}):"—"]));
 table("users",["邮箱","角色","点数","状态",""],state.users.map(u=>[u.email,u.role==="admin"?"管理员":"用户",u.balance,u.active?"正常":"停用",u.role==="admin"?"—":button(u.active?"停用":"启用",async()=>{if(!confirm("更改 "+u.email+" 的账号状态？"))return;await YF.api("/api/admin/users/"+u.id+"/state","POST",{active:!u.active});await load();})]));
 table("audit",["时间","管理员","操作","对象"],state.audit.map(a=>[YF.date(a.created),a.email,a.action,a.subject]));
}
document.querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>{document.querySelectorAll("[data-tab]").forEach(x=>{x.classList.toggle("selected",x===b);x.setAttribute("aria-pressed",x===b);$("tab-"+x.dataset.tab).hidden=x!==b;});YanUI.enter($("tab-"+b.dataset.tab));msg("");});
function form(id,fn){$(id).onsubmit=async e=>{e.preventDefault();const btn=e.target.querySelector("button");btn.disabled=true;try{await fn(e.target);await load();}catch(err){msg(err.message);}finally{btn.disabled=false;}};}
$("new-model").onclick=()=>editModel(null);$("new-pack").onclick=()=>editPack(null);
form("model-form",async f=>{const d=Object.fromEntries(new FormData(f));for(const k of ["fee","input_rate","output_rate","max_output"])d[k]=Number(d[k]);d.enabled=d.enabled==="1";d.id=modelId;d.secret=d.key_action==="clear"?"":d.secret||null;delete d.key_action;const r=await YF.api("/api/admin/models","POST",d);modelId=r.id;f.elements.secret.value="";msg("已保存模型配置。");});
form("pack-form",async f=>{const d=Object.fromEntries(new FormData(f));const r=await YF.api("/api/admin/packs","POST",{id:packId,label:d.label,points:Number(d.points),cents:Math.round(Number(d.yuan)*100),enabled:d.enabled==="1"});packId=r.id;msg("已保存套餐。");});
form("issue-form",async()=>{const r=await YF.api("/api/admin/vouchers","POST",{pack:Number($("issue-pack").value),count:Number($("issue-count").value)});batchId=r.batch;$("issued").hidden=false;$("code-output").value=r.codes.join("\n");msg("已发行 "+r.codes.length+" 个兑换码。");});
$("download-codes").onclick=()=>{const a=el("a");a.download="Yanfolio-"+batchId+".txt";a.href=URL.createObjectURL(new Blob([$("code-output").value],{type:"text/plain;charset=utf-8"}));a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1500);};
form("user-search",async()=>{});load().catch(e=>msg(e.message));


let cloudState;
async function cloudLoad(){
 const d=await YF.api("/api/admin/cloud?q="+encodeURIComponent($("cloud-q").value));cloudState=d;
 const fmt=YanfolioDrive.fmt;$("cloud-summary").textContent="已保存 "+d.versions+" 份版本，共 "+fmt(d.stored)+"；存储卷可用 "+fmt(d.disk_available)+"。每个账号默认 "+fmt(d.config.free_bytes)+"。";
 $("cloud-switch").textContent=d.config.uploads_enabled?"暂停文档上传":"恢复文档上传";
 table("cloud-users",["邮箱","已用","传输预留","配额",""],d.users.map(u=>[u.email,fmt(u.used),fmt(u.reserved),fmt(u.quota),button("调整配额",async()=>{const n=prompt("请输入账号配额（GB）；输入 default 恢复默认配额。",String(u.quota/1e9));if(n===null)return;
  if(n!=="default"&&!/^\d+(?:\.\d{1,3})?$/.test(n.trim()))throw Error("请输入有效的 GB 数值。");
  await YF.api("/api/admin/cloud/users/"+u.id,"PUT",{bytes:n==="default"?null:Math.round(Number(n)*1e9)});await cloudLoad();msg("配额已更新。");})]));
}
document.querySelector('[data-tab="cloud"]').addEventListener("click",()=>cloudLoad().catch(e=>msg(e.message)));
$("cloud-find").onsubmit=e=>{e.preventDefault();cloudLoad().catch(err=>msg(err.message));};
$("cloud-switch").onclick=async()=>{if(!cloudState||!confirm("更改所有客户端的文档上传状态？"))return;
 try{await YF.api("/api/admin/cloud/uploads","PUT",{enabled:!cloudState.config.uploads_enabled});await cloudLoad();msg("服务端上传状态已更新。");}catch(e){msg(e.message);}};
