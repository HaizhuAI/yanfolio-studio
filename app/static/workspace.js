"use strict";
const $ = id => document.getElementById(id);
const make = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
const paths = {
  plus:"M12 5v14M5 12h14", pen:"m4 20 4.2-1 12-12-3.2-3.2-12 12L4 20Zm10.5-13.5 3 3", search:"M20 20l-4.5-4.5 M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0",
  layout:"M3 4h18v16H3z M3 9h18 M9 9v11", drive:"M3 13l3-8h12l3 8v6H3z M3 13h18 M16 16h2",
  check:"m4 12 5 5L20 6",download:"M12 3v12m-5-5 5 5 5-5 M4 16v4h16v-4",file:"M6 3h8l4 4v14H6z M14 3v5h4",
  align:"M4 5h16M4 10h12M4 15h16M4 20h10",undo:"m8 4-5 5 5 5 M3 9h11a6 6 0 0 1 0 12",
  spark:"m10 3 1.7 5.3L17 10l-5.3 1.7L10 17l-1.7-5.3L3 10l5.3-1.7L10 3Zm8 11 1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3Z",
  bookmark:"M6 3h12v18l-6-4-6 4z",books:"M3 5h4v14H3z M9 5h4v14H9z M15 6l3-1 4 13-3 1z",
  checklist:"M9 6h11M9 12h11M9 18h11 M3 6l1 1 2-3 M3 12l1 1 2-3 M3 18l1 1 2-3"
};
document.querySelectorAll("[data-icon]").forEach(el => {
  const svg = document.createElementNS("http://www.w3.org/2000/svg","svg");
  const path = document.createElementNS(svg.namespaceURI,"path");
  svg.setAttribute("viewBox","0 0 24 24"); svg.setAttribute("class","icon"); svg.setAttribute("aria-hidden","true");
  path.setAttribute("d",paths[el.dataset.icon]); svg.append(path); el.replaceWith(svg);
});
const storageKey = "yanfolio.workspace.v1";
const blank = () => ({id:crypto.randomUUID(),title:"",text:"",references:[],updated:Date.now()});
const sample = blank();
sample.title = "城市绿地与夏季地表温度";
sample.text = "研究问题\n\n在相近的建成环境中，不同类型的城市绿地与周边地表温度之间存在怎样的关联？\n\n研究设计\n\n本研究拟结合夏季遥感影像与土地覆盖数据，比较乔木、草地和混合植被周边的地表温度。分析将区分绿地内部与邻近街区，并记录影像采集时间、空间分辨率和天气条件。\n\n待补充的证据\n\n确定研究区域与观测时段，核对数据来源，并检索已有研究对空间尺度的处理方法。";
sample.example = true;
function initial() {
  const item = localStorage.getItem(storageKey);
  if (!item) return {active:sample.id,docs:[sample],library:[]};
  const parsed = JSON.parse(item);
  if (!Array.isArray(parsed.docs) || !parsed.docs.length || !Array.isArray(parsed.library)) throw Error("无法读取已保存的工作区。");
  return parsed;
}
let state;
try { state=initial(); } catch (error) { document.querySelector("main").textContent="浏览器存储不可用或草稿数据损坏，请先检查浏览器存储权限和备份。"; throw error; }
const doc = () => state.docs.find(x=>x.id===state.active) || state.docs[0];
const keyOf = r => r.doi ? "doi:"+r.doi.toLowerCase() : (r.url || r.title+"|"+r.year);
const names = {write:"论文创作",search:"文献检索",format:"格式工作室"};
let mode="polish", ticket=0, proposal=null, past=null, formatVersion=0, validFormat=false, liveItems=[];
let timer;
function notice(msg) { $("notice").textContent=msg; $("notice").hidden=false; clearTimeout(timer); timer=setTimeout(()=>$("notice").hidden=true,6500); }
function save() {
  try { localStorage.setItem(storageKey,JSON.stringify(state)); $("save-state").lastChild.textContent="已保存到本机"; }
  catch { $("save-state").lastChild.textContent="本机保存失败"; notice("浏览器空间不足或存储不可用，请立即导出 Word 备份。"); }
}
function show(view) {
  Object.keys(names).forEach(v=>$("view-"+v).hidden=v!==view);
  document.querySelectorAll("nav [data-view]").forEach(b=>{b.classList.toggle("active",b.dataset.view===view);b.setAttribute("aria-current",b.dataset.view===view?"page":"false");});
  $("breadcrumb").textContent=names[view]; if (view==="search") $("query").focus();
}
document.querySelectorAll("[data-view]").forEach(b=>b.onclick=()=>show(b.dataset.view));
function action(label, fn, cls="text-btn") { const b=make("button",label,cls); b.type="button"; b.onclick=fn; return b; }
function manuscripts() {
  $("drafts").replaceChildren(...state.docs.map(d=>{const btn=action(d.title||"无题手稿",()=>{selectDoc(d.id);show("write");},d.id===doc().id?"current":"");btn.title=d.title||"无题手稿";return btn;}));
}
function meta() { $("wordcount").textContent=Array.from(doc().text.replace(/\s/g,"")).length.toLocaleString()+" 字"; }
function clearSuggestion() { proposal=null; $("suggestion").hidden=true; }
function selectDoc(id) {
  state.active=id; ++ticket; clearSuggestion(); past=null; $("undo").disabled=true; $("generate").disabled=false; $("generate").lastChild.textContent="生成建议";
  $("doc-title").value=doc().title; $("body").value=doc().text; $("paper-id").textContent=doc().example?"示例手稿":"个人手稿";meta();manuscripts();library();save();
}
$("new").onclick=()=>{const d=blank();state.docs.unshift(d);selectDoc(d.id);show("write");$("doc-title").focus();};
$("doc-title").oninput=()=>{doc().title=$("doc-title").value;doc().updated=Date.now();save();manuscripts();};
$("body").oninput=()=>{doc().text=$("body").value;doc().updated=Date.now();past=null;$("undo").disabled=true;meta();save();};
function insert(text,start=$("body").selectionStart,end=$("body").selectionEnd) {
  const area=$("body");area.setRangeText(text,start,end,"end");area.oninput();area.focus();
}
$("add-h").onclick=()=>insert("\n# "); $("add-h2").onclick=()=>insert("\n## ");
function library() {
  $("library-count").textContent=state.library.length;
  const list=$("library");list.replaceChildren();
  if (!state.library.length) list.append(make("p","将检索到的文献存入文献夹，在正文中插入编号引文。"));
  state.library.forEach(r=>{
    const item=make("div",undefined,"lib-item");item.append(make("strong",r.title),make("span",r.year+" · "+(r.sources||[]).join(" / ")));
    item.append(document.createElement("br"),action("插入引文",()=>{
      let idx=doc().references.findIndex(x=>keyOf(x)===keyOf(r));
      if (idx<0){doc().references.push(r);idx=doc().references.length-1;}
      insert("["+String(idx+1)+"]");library();notice("引文已插入正文，并已加入本文参考文献。");
    }));list.append(item);
  });
  const refs=$("bibliography");refs.replaceChildren();
  if (doc().references.length) refs.append(make("h3","参考文献"));
  doc().references.forEach((r,i)=>refs.append(make("p","["+(i+1)+"] "+r.title+" · "+r.year,"reference-line")));
}
async function request(url,options={}) {
  const response=await fetch(url,options);
  if (!response.ok) { const value=await response.json().catch(()=>({}));throw Error(typeof value.detail==="string"?value.detail:"请求未完成，请检查输入后重试。"); }
  return response;
}
const post = body => ({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
function download(blob,filename) {
  const a=make("a");a.href=URL.createObjectURL(blob);a.download=filename.replace(/[\\/:*?"<>|]/g,"_");a.click();setTimeout(()=>URL.revokeObjectURL(a.href),15000);
}
$("export").onclick=async()=>{try { const r=await request("/api/export",post(doc()));download(await r.blob(),(doc().title||"无题手稿")+".docx"); } catch(e){notice(e.message);} };
$("import").onclick=()=>$("import-file").click();
$("import-file").onchange=async()=>{
  const file=$("import-file").files[0];if(!file)return;
  const form=new FormData();form.append("manuscript",file);
  try{const raw=await(await request("/api/import",{method:"POST",body:form})).json();
    const d={...blank(),...raw};state.docs.unshift(d);selectDoc(d.id);notice("已导入正文。表格、图片和域保留在原始 Word 文件中。");
  }catch(e){notice(e.message);}finally{$("import-file").value="";}
};
$("use-draft").onclick=async()=>{
  try{const d=doc(),r=await request("/api/export",post(d)),blob=await r.blob();
    const transfer=new DataTransfer();transfer.items.add(new File([blob],(d.title||"手稿")+".docx",{type:blob.type}));
    $("manuscript").files=transfer.files;$("manuscript").dispatchEvent(new Event("input",{bubbles:true}));notice("已选用当前手稿。");
  }catch(e){notice(e.message);}
};
document.querySelectorAll("[data-mode]").forEach(b=>b.onclick=()=>{
  mode=b.dataset.mode;document.querySelectorAll("[data-mode]").forEach(el=>el.classList.toggle("selected",el===b));
});
$("generate").onclick=async()=>{
  const btn=$("generate"), area=$("body"), d=doc(), id=++ticket, start=area.selectionStart,end=area.selectionEnd;
  const snapshot={docId:d.id,raw:d.text,title:d.title,start,end,mode};
  clearSuggestion();btn.disabled=true;btn.lastChild.textContent="正在生成…";
  try{
    const response=await request("/api/write",post({...d,action:mode,selection:d.text.slice(start,end),instruction:$("prompt").value}));
    const result=await response.json(); if(id!==ticket) return;
    proposal={...snapshot,text:result.suggestion};$("suggest-text").textContent=result.suggestion;
    $("accept").textContent=snapshot.mode==="polish"?(start===end?"替换正文":"替换选区"):"追加到正文";$("suggestion").hidden=false;
  }catch(e){if(id===ticket)notice(e.message);}finally{if(id===ticket){btn.disabled=false;btn.lastChild.textContent="生成建议";}}
};
$("discard").onclick=clearSuggestion;
$("accept").onclick=()=>{
  const p=proposal,d=doc(); if(!p)return;
  if (d.id!==p.docId||d.text!==p.raw||d.title!==p.title){notice("原稿已变化，请重新生成建议。");clearSuggestion();return;}
  const before=d.text;
  if(p.mode==="polish") d.text=p.start===p.end?p.text:before.slice(0,p.start)+p.text+before.slice(p.end);
  else d.text=[before,p.text].filter(Boolean).join("\n\n");
  if(d.text.length>500000){d.text=before;notice("采纳后将超出手稿长度限制。");return;}
  past=before;$("body").value=d.text;$("undo").disabled=false;clearSuggestion();meta();save();
};
$("undo").onclick=()=>{if(past===null)return;doc().text=past;$("body").value=past;past=null;$("undo").disabled=true;clearSuggestion();meta();save();};
function drawResults() {
  const container=$("results");container.replaceChildren();
  for(const r of liveItems){
    const card=make("article",undefined,"result");
    const title=make(r.url?"a":"strong",r.title);
    if(r.url){title.href=r.url;title.target="_blank";title.rel="noopener noreferrer";}
    const foot=make("footer");foot.append(make("span",r.sources.join(" · "),"source-tag"));
    const has=state.library.some(x=>keyOf(x)===keyOf(r));
    const button=action(has?"已存入":"存入文献夹",()=>{state.library.push(r);save();library();drawResults();notice("已存入文献夹。");},"button");button.disabled=has;foot.append(button);
    card.append(title,make("p",[r.authors.slice(0,4).join(", ")+(r.authors.length>4?" 等":""),r.year,r.journal].filter(Boolean).join(" · ")));
    if(r.doi)card.append(make("p","DOI "+r.doi));
    card.append(foot);container.append(card);
  }
}
$("search-form").onsubmit=async e=>{
  e.preventDefault();const btn=e.currentTarget.querySelector("button");btn.disabled=true;const q=$("query").value.trim();
  const params=new URLSearchParams({q,source:$("source").value});if($("year").value)params.set("year",$("year").value);
  $("source-status").textContent="正在查询学术索引…";$("result-count").textContent="";$("results").replaceChildren();
  try{
    const data=await(await request("/api/search?"+params)).json();liveItems=data.items;drawResults();
    $("source-status").replaceChildren(...Object.entries(data.status).map(([s,msg])=>make("span",s+" · "+msg,"source-tag")));
    $("result-count").textContent="去重后 "+liveItems.length+" 条";
    if(!liveItems.length)$("results").append(make("div","本次未取得题录。请查看数据源状态，或更换关键词。","empty"));
  }catch(err){$("source-status").textContent=err.message;}finally{btn.disabled=false;}
};
const formatForm=$("format-form");
formatForm.oninput=()=>{formatVersion++;validFormat=false;$("apply-format").disabled=true;$("report").replaceChildren(make("p","输入已更新，请重新预检。","sub"));};
function payload(){const f=new FormData(formatForm);for(const [k,v] of [...f])if(v instanceof File&&!v.name)f.delete(k);return f;}
function reportList(title,items){
  if(!items.length)return;const ul=make("ul");items.forEach(i=>ul.append(make("li",i)));$("report").append(make("h3",title),ul);
}
formatForm.onsubmit=async e=>{
  e.preventDefault();const version=formatVersion;$("preview").disabled=true;$("apply-format").disabled=true;validFormat=false;$("report").textContent="正在分析 Word 结构与规则…";
  try{
    const data=await(await request("/api/format/preview",{method:"POST",body:payload()})).json();
    if(version!==formatVersion)return;
    $("report").replaceChildren(make("p",data.changed?"已找到可套用的格式。":"尚未找到可自动套用的格式。"));
    reportList("匹配范围",[...Object.entries(data.paragraphs).map(([k,n])=>k+" · "+n+" 段"),...(data.sections?["页面设置 · "+data.sections+" 节"]:[])]);
    reportList("模板中提取的样式",data.template_roles);reportList("识别到的文字要求",data.recognized);reportList("待人工确认",data.pending);reportList("分节说明",data.warnings);
    validFormat=data.changed;$("apply-format").disabled=!validFormat;
  }catch(err){if(version===formatVersion)$("report").textContent=err.message;}finally{$("preview").disabled=false;}
};
$("apply-format").onclick=async()=>{
  if(!validFormat)return;const version=formatVersion, filename=$("manuscript").files[0].name.replace(/\.docx$/i,"");$("apply-format").disabled=true;
  try{const r=await request("/api/format/apply",{method:"POST",body:payload()});const blob=await r.blob();if(version===formatVersion)download(blob,filename+"-排版副本.docx");}
  catch(e){notice(e.message);}finally{$("apply-format").disabled=!validFormat;}
};
selectDoc(doc().id);
request("/api/status").then(r=>r.json()).then(s=>{$("model-info").textContent=s.ai?"生成时将把所选文字及本文题录发送给 "+s.model+"。":"写作模型待配置，可继续编辑、检索和排版。";}).catch(()=>{$("model-info").textContent="服务暂不可用。";});
window.addEventListener("storage",e=>{if(e.key===storageKey&&e.newValue){state=initial();selectDoc(state.active);if(liveItems.length)drawResults();}});

