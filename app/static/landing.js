const demos={
 write:["环境科学","城市绿地与地表温度","本研究","想看一下","旨在探讨","绿地覆盖与地表温度之间的关系。","保留“关系”的表述，避免将观测结果写成因果结论。"],
 cite:["题录核对","检查一个引用的来源","先核对题名、作者和 DOI，再把题录存入文献夹。","","[1]"," 会随手稿导出到参考文献表。","查到题录后，仍需阅读原文以判断它能否支持具体论断。"],
 format:["Word 格式","把投稿规范应用到副本","正文样式：","","宋体 · 小四 · 1.5 倍行距","。先检查识别结果，再下载排版副本。","预检保留无法识别的规则原句，便于逐条人工复核。"]
};
document.querySelectorAll("[data-demo]").forEach(b=>b.onclick=()=>{
 const [kind,title,a,old,change,tail,note]=demos[b.dataset.demo];
 document.querySelectorAll("[data-demo]").forEach(x=>x.setAttribute("aria-pressed",x===b));
 document.getElementById("sample-kind").textContent=kind;document.getElementById("sample-title").textContent=title;
 const p=document.createElement("p"),cut=document.createElement("span"),mark=document.createElement("mark");
 cut.className="cut";cut.textContent=old;mark.textContent=change;p.append(a,cut,mark,tail);
 document.getElementById("sample-body").replaceChildren(p);document.getElementById("sample-note").textContent=note;
});
fetch("/api/auth/options").then(r=>r.json()).then(o=>{
 if(!o.desktop)document.querySelectorAll(".download").forEach(a=>a.remove());
 if(o.signed_in){document.querySelectorAll("[data-entry]").forEach(a=>{a.href="/studio";a.textContent="进入工作台";});const a=document.querySelector(".login");a.href="/profile.html";a.textContent="个人中心";}
}).catch(()=>{});

