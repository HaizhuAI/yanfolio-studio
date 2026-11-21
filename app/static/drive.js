"use strict";
const $=id=>document.getElementById(id), el=YF.el, fmt=YanfolioDrive.fmt;
let folder="",trash=false,page=1,library=null,selectMode={},abort=null,seq=0,versionFile=null;
const say=message=>{$("feedback").textContent=message;};
function act(label,fn,cls="text-btn"){const b=el("button",label,cls);b.type="button";b.onclick=()=>Promise.resolve().then(fn).catch(e=>say(e.message));return b;}
function link(label,url){const a=el("a",label);a.href=url;return a;}
function source(f,v){return "/api/drive/files/"+f.id+"/download"+(v?"?version="+v:"");}
function choose(options={}){if(abort){say("请先暂停或完成当前上传。");return;}selectMode=options;$("file-input").multiple=!options.target&&!options.resume;$("file-input").value="";$("file-input").click();}
async function nav(id,bin=false){folder=id;trash=bin;page=1;versionFile=null;$("versions-panel").hidden=true;$("query").value="";await load();}
async function change(f,action,value=""){await YF.api("/api/drive/files/"+f.id,"POST",{action,value,expected:f.head});await load();if(versionFile===f.id&&!trash&&["restore_version","delete_version"].includes(action))await historyFor(f);else{$("versions-panel").hidden=true;versionFile=null;}}
async function historyFor(f){
 const data=await YF.api("/api/drive/files/"+f.id+"/versions");versionFile=f.id;$("versions-panel").hidden=false;$("versions-title").textContent=f.name+" · 版本";
 $("versions").replaceChildren(...data.versions.map(v=>{const row=el("div",undefined,"transfer-line"),details=el("div"),actions=el("div",undefined,"file-actions");
 details.append(el("strong","版本 "+v.seq+(v.id===data.file.head?" · 当前":"")),el("small",fmt(v.bytes)+" · "+YF.date(v.created)));
 actions.append(link("下载",source(f,v.id)));if(v.id!==data.file.head)actions.append(act("设为当前",()=>change(data.file,"restore_version",v.id)),act("删除此版本",()=>{if(confirm("永久删除此历史版本并释放空间？"))return change(data.file,"delete_version",v.id);}));
 row.append(details,actions);return row;}));$("versions-panel").scrollIntoView({block:"nearest"});
}
function chooseFolder(f){
 $("destination").replaceChildren(new Option("根目录",""),...library.folders.map(x=>new Option(x.name,x.id)));$("destination").value=f.folder;
 const dialog=$("move-dialog");dialog.returnValue="";dialog.onclose=()=>{if(dialog.returnValue==="ok")change(f,"move",$("destination").value).catch(e=>say(e.message));};dialog.showModal();
}
function fileRow(f){
 const tr=el("tr"),name=el("td",undefined,"file-name");const wrap=el("div",undefined,"file-line"),text=el("div");text.append(el("strong",f.name),el("small","版本 "+f.seq+" · "+f.versions+" 份版本"));wrap.append(el("span",f.name.split(".").pop().slice(0,4).toUpperCase(),"doc-glyph"),text);name.append(wrap);
 const actions=el("div",undefined,"file-actions");
 if(trash){actions.append(act("还原",()=>{const n=prompt("还原后的文件名",f.name);if(n)return change(f,"restore",n);}),act("永久删除",()=>{if(confirm("永久删除此文件及所有版本？"))return change(f,"purge");}));}
 else{
  actions.append(link("下载",source(f)),act("版本",()=>historyFor(f)));
  const more=el("details"),summary=el("summary","管理"),list=el("div",undefined,"file-actions");more.append(summary,list);
  if(/\.pptx$/i.test(f.name)&&f.bytes<=16*1024*1024)list.append(link("导入演示文字","/slides?cloud="+f.id));
  if(/\.docx$/i.test(f.name)&&f.bytes<=16*1024*1024)list.append(link("导入写作", "/studio?cloud="+f.id+"&version="+f.head),link("用于排版","/studio?formatCloud="+f.id+"&version="+f.head));
  list.append(act("上传新版本",()=>choose({target:f})),act("重命名",()=>{const n=prompt("新文件名",f.name);if(n&&n!==f.name)return change(f,"rename",n);}),
   act("移动",()=>chooseFolder(f)),act("移入回收站",()=>{if(confirm("将此文件移入回收站？30 天内可还原。"))return change(f,"trash");}));actions.append(more);
 }
 const cell=el("td");cell.append(actions);tr.append(name,el("td",fmt(f.bytes)),el("td",YF.date(f.modified)),cell);return tr;
}
async function load(){
 const my=++seq,params=new URLSearchParams({folder,trash,page,q:$("query").value.trim()});
 const [d,pending]=await Promise.all([YF.api("/api/drive?"+params),YF.api("/api/drive/transfers")]);if(my!==seq)return;library=d;
 $("root").classList.toggle("current",!folder&&!trash);$("trash").classList.toggle("current",trash);$("folders").replaceChildren(...d.folders.map(f=>act(f.name,()=>nav(f.id),"folder"+(folder===f.id&&!trash?" current":""))));
 $("folder-actions").hidden=!folder||trash;
 $("location").textContent=trash?"回收站":folder?d.folders.find(f=>f.id===folder)?.name||"文件夹":"根目录";
 $("upload").disabled=!!abort||trash||!d.storage.uploads_enabled;$("upload").textContent=d.storage.uploads_enabled?"上传文档":"上传已暂停";
 $("drop-hint").hidden=trash||!d.storage.uploads_enabled;
 $("quota-label").textContent=fmt(d.storage.used)+" / "+fmt(d.storage.quota);$("meter").value=d.storage.quota?100*d.storage.used/d.storage.quota:0;
 $("usage-detail").textContent="回收站 "+fmt(d.storage.trash)+" · 传输预留 "+fmt(d.storage.reserved);
 $("items").replaceChildren(...d.files.map(fileRow));if(!d.files.length){const r=el("tr"),c=el("td",trash?"回收站为空。":$("query").value?"没有匹配的文件。":"这里还没有文档。");c.colSpan=4;r.append(c);$("items").append(r);}
 $("page-info").textContent=d.total+" 个文件 · 第 "+d.page+" 页";$("prev").disabled=page===1;$("next").disabled=page*60>=d.total;
 $("transfers").hidden=!pending.length;$("pending").replaceChildren(...pending.map(p=>{const row=el("div",undefined,"transfer-line"),label=el("div"),actions=el("div",undefined,"file-actions");
 label.append(el("strong",p.name),el("small",fmt(p.received)+" / "+fmt(p.total)));actions.append(act("选原文件续传",()=>choose({resume:p})),act("取消传输",async()=>{if(abort){say("请先暂停当前上传。");return;}if(confirm("取消上传并释放预留空间？")){await YF.api("/api/drive/uploads/"+p.id+"/cancel","POST",{});await load();}}));row.append(label,actions);return row;}));
}
$("root").onclick=()=>nav("").catch(e=>say(e.message));$("trash").onclick=()=>nav("",true).catch(e=>say(e.message));$("prev").onclick=()=>{page--;load().catch(e=>say(e.message));};$("next").onclick=()=>{page++;load().catch(e=>say(e.message));};
$("search").onsubmit=e=>{e.preventDefault();page=1;load().catch(err=>say(err.message));};$("new-folder").onclick=async()=>{const n=prompt("文件夹名称");if(!n)return;try{const f=await YF.api("/api/drive/folders","POST",{name:n});await nav(f.id);}catch(e){say(e.message);}};
$("close-versions").onclick=()=>{$("versions-panel").hidden=true;versionFile=null;};$("logout").onclick=YF.logout;$("upload").onclick=()=>choose();$("pause").onclick=()=>abort?.abort();
async function sendFiles(files,options={}){
 if(!files.length||abort)return;
 if(trash||!library?.storage.uploads_enabled){say("当前无法上传文件。");return;}
 const dest=folder;abort=new AbortController();$("upload").disabled=true;$("transfer-progress").hidden=false;say("");
 let finished=0;
 try{
  for(const file of files){
   await YanfolioDrive.upload(file,{...options,folder:dest,signal:abort.signal,progress:(n,total)=>{
    $("transfer-text").textContent=file.name+" · "+fmt(n)+" / "+fmt(total);$("transfer-meter").value=n*100/total;
   }});
   finished++;
  }
  say("已保存 "+finished+" 份文档。");
 }catch(e){say((finished?"已保存 "+finished+" 份。":"")+(e.name==="AbortError"?"上传已暂停，当前文件可在上传任务中继续。":e.message));}
 finally{abort=null;$("transfer-progress").hidden=true;await load().catch(e=>say(e.message));}
}
$("file-input").onchange=()=>sendFiles(Array.from($("file-input").files),selectMode);
const drop=document.querySelector(".library-main");let dragDepth=0;
function isFileDrag(e){return Array.from(e.dataTransfer?.types||[]).includes("Files");}
drop.addEventListener("dragenter",e=>{if(isFileDrag(e)){e.preventDefault();dragDepth++;if(!abort&&!trash&&library?.storage.uploads_enabled)drop.classList.add("drag-over");}});
drop.addEventListener("dragover",e=>{if(isFileDrag(e)){e.preventDefault();e.dataTransfer.dropEffect=abort||trash||!library?.storage.uploads_enabled?"none":"copy";}});
drop.addEventListener("dragleave",()=>{dragDepth=Math.max(0,dragDepth-1);if(!dragDepth)drop.classList.remove("drag-over");});
drop.addEventListener("drop",e=>{if(!isFileDrag(e))return;e.preventDefault();dragDepth=0;drop.classList.remove("drag-over");sendFiles(Array.from(e.dataTransfer.files));});
async function start(){const u=await YF.api("/api/me");YF.account=u.id;const id=new URLSearchParams(location.search).get("folder")||"";
 if(id){const root=await YF.api("/api/drive");if(root.folders.some(f=>f.id===id))folder=id;}await load();}
start().catch(e=>say(e.message));document.addEventListener("visibilitychange",()=>{if(!document.hidden&&YF.account&&!abort)load().catch(e=>say(e.message));});


$("rename-folder").onclick=async()=>{const n=prompt("文件夹新名称",$("location").textContent);if(!n)return;try{await YF.api("/api/drive/folders/"+folder,"POST",{action:"rename",name:n});await load();}catch(e){say(e.message);}};
$("remove-folder").onclick=async()=>{if(!confirm("删除此空文件夹？"))return;try{await YF.api("/api/drive/folders/"+folder,"POST",{action:"remove"});await nav("");}catch(e){say(e.message);}};
