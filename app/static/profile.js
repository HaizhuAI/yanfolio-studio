const $=id=>document.getElementById(id),fmt=YanfolioDrive.fmt;
async function load(){
 const p=await YF.api("/api/profile");YF.account=p.id;$("admin-portal").hidden=p.role!=="admin";$("person").textContent=p.profile.name||p.email.split("@")[0];$("avatar").textContent=Array.from($("person").textContent)[0];$("email").textContent=p.email;$("joined").textContent=(p.role==="admin"?"管理员账号":"研究者账号")+" · "+new Date(p.created*1000).toLocaleDateString("zh-CN")+" 注册";
 for(const k of ["name","institution","discipline"])$(k).value=p.profile[k];
 $("used").textContent=fmt(p.storage.used);$("quota").textContent=fmt(p.storage.quota);$("balance").textContent=p.balance;$("meter").value=p.storage.quota?p.storage.used*100/p.storage.quota:0;
 $("counts").textContent=p.file_count+" 份文档 · 回收站 "+fmt(p.storage.trash)+" · 上传预留 "+fmt(p.storage.reserved);
 const recent=$("recent-files");recent.replaceChildren(...(p.recent_files||[]).map(f=>{
  const a=YF.el("a",undefined,"recent-doc");a.href="/drive.html?folder="+encodeURIComponent(f.folder);const box=YF.el("div");
  box.append(YF.el("strong",f.name),YF.el("small",YF.date(f.modified)+" · "+fmt(f.bytes)));a.append(YF.el("span",f.name.split(".").pop().slice(0,4).toUpperCase(),"doc-glyph"),box,YanUI.icon("right"));return a;
 }));
 if(!recent.children.length)recent.append(YF.el("p","上传后，最近更新的文档会出现在这里。","empty-list"));
 $("devices").replaceChildren(...p.devices.map(d=>{const row=YF.el("div",undefined,"device");const group=YF.el("div");group.append(YF.el("strong",d.label),YF.el("small","有效期至 "+YF.date(d.expires).split(" ")[0]));const glyph=YF.el("span",undefined,"device-glyph");glyph.append(YanUI.icon("desktop"));row.append(glyph,group);
 if(d.current)row.append(YF.el("span","当前会话","sub"));else{const b=YF.el("button","退出此设备","button");b.onclick=async()=>{if(!confirm("结束该设备的登录会话？"))return;try{await YF.api("/api/profile/devices/"+d.device+"/revoke","POST",{});await load();}catch(e){$("feedback").textContent=e.message;}};row.append(b);}return row;}));
}
$("logout").onclick=YF.logout;$("profile-form").onsubmit=async e=>{e.preventDefault();const btn=e.target.querySelector("button");btn.disabled=true;try{await YF.api("/api/profile","PUT",Object.fromEntries(["name","institution","discipline"].map(k=>[k,$(k).value])));await load();$("feedback").textContent="个人资料已保存。";}catch(err){$("feedback").textContent=err.message;}finally{btn.disabled=false;}};
load().catch(e=>$("feedback").textContent=e.message);

