"use strict";
(async()=>{
 const $=id=>document.getElementById(id),el=YF.el, api=YF.api;
 let dragSource=null;
 let active=null,page=0,known=[],themes=[],sources=[],models=[],pendingQuote=null,creating=false,sourceRefs=[];
 const previewCache=new Map();let observer=null;
 let previewSeq=0,saveTimer,previewTimer,saving=null,saved="",conflict=false;
 const names={cover:"封面",content:"正文",columns:"双栏",closing:"收尾"};
 const controls={title:["标题",90],subtitle:["副标题",240],body:["正文要点（每行一条）",950],left_title:["左栏标题",55],left_body:["左栏正文",480],right_title:["右栏标题",55],right_body:["右栏正文",480]};
 const slots={cover:["title","subtitle"],content:["title","body"],columns:["title","left_title","left_body","right_title","right_body"],closing:["title","subtitle"]};
 const user=await api("/api/me");YF.account=user.id;
 const localKey=id=>"yanfolio.deck."+user.id+"."+id;
 const current=()=>active.deck.slides[page];
 const getTheme=id=>themes.find(t=>t.id===id);
 const defaults=(layout="content")=>({layout,title:"",subtitle:"",eyebrow:"",body:"",left_title:"",left_body:"",right_title:"",right_body:"",notes:""});
 function message(text){$("feedback").textContent=text;$("feedback").hidden=!text;}
 function button(label,handler,cls="text-btn"){const b=el("button",label,cls);b.type="button";b.onclick=()=>Promise.resolve().then(handler).catch(e=>message(e.message));return b;}
 function link(label,url){const a=el("a",label);a.href=url;return a;}
 function disabled(busy){for(const id of ["cancel-create","new-template","new-title","source-doc","material","slide-model","page-count","make-free","quote-ai","confirm-ai"])$(id).disabled=busy;}
 function syncLabel(value){$("sync").textContent=value;}
 function cache(){
   if(!active)return;
   try{localStorage.setItem(localKey(active.id),JSON.stringify(active));}catch{message("本机缓存空间不足，请保持页面打开并及时导出。");}
 }
 function changed(){
   cache();syncLabel(conflict?"有版本冲突":"待同步");clearTimeout(saveTimer);if(!conflict)saveTimer=setTimeout(()=>flush().catch(e=>message(e.message)),500);
 }
 async function flush(){
   clearTimeout(saveTimer);
   if(!active||conflict)return;
   if(saving)return saving;
   const obj=active;
   saving=(async()=>{
     while(obj===active&&!conflict){
       const snap=JSON.stringify(obj.deck);if(snap===saved){localStorage.removeItem(localKey(obj.id));syncLabel("已同步");break;}
       syncLabel("同步中");
       try{const r=await api("/api/slides/drafts/"+obj.id,"PUT",{version:obj.version,deck:JSON.parse(snap)});
         obj.version=r.version;saved=snap;
         if(JSON.stringify(obj.deck)===snap){localStorage.removeItem(localKey(obj.id));syncLabel("已同步");}else cache();
       }catch(e){if(e.status===409){conflict=true;$("deck-conflict").hidden=false;syncLabel("有版本冲突");}else syncLabel("待重试");throw e;}
     }
   })();try{await saving;}finally{saving=null;}
 }
 async function list(){known=(await api("/api/slides/drafts")).items;
  $("draft-count").textContent=known.length+" 份";$("decks").replaceChildren();
  for(const item of known){
   const row=el("article",undefined,"deck-row"),open=button(item.title,()=>openDraft(item.id));open.append(el("small",(getTheme(item.template)?.name||"演示稿")+" · "+YF.date(item.updated)));
   const del=button("删除",async()=>{if(!confirm("删除演示草稿「"+item.title+"」？已导出的 PPTX 会保留。"))return;await api("/api/slides/drafts/"+item.id+"?version="+item.version,"DELETE",{});localStorage.removeItem(localKey(item.id));await list();});
   row.append(YanUI.icon("desktop"),open,del);$("decks").append(row);
  }if(!known.length)$("decks").append(el("p","选择上方模板即可开始，也可以导入已有 PPTX 的文字。","deck-empty"));
 }
 async function openDraft(id){const v=await api("/api/slides/drafts/"+id);openData(v);}
 function openData(v){
   active=v;document.body.classList.add("edit-deck");page=0;saved=JSON.stringify(active.deck);conflict=false;
   try{const copy=JSON.parse(localStorage.getItem(localKey(v.id))||"null");
    if(copy?.deck&&JSON.stringify(copy.deck)!==saved){active.deck=copy.deck;conflict=copy.version!==v.version;}
   }catch{}
   $("deck-conflict").hidden=!conflict;$("gallery").hidden=true;$("editor").hidden=false;$("deck-title").value=active.deck.title;$("theme").value=active.deck.template;
   syncLabel(conflict?"有版本冲突":"已同步");draw();if(!conflict&&JSON.stringify(active.deck)!==saved)changed();
   history.replaceState(null,"","/slides?deck="+encodeURIComponent(active.id));window.scrollTo(0,0);
 }
 async function newData(deck,id=crypto.randomUUID()){
   const res=await api("/api/slides/drafts/"+id,"PUT",{version:0,deck});
   openData({id,version:res.version,deck});
 }
 $("back").onclick=async()=>{try{await flush();}catch(e){message(e.message);return;}active=null;document.body.classList.remove("edit-deck");observer?.disconnect();previewSeq++;clearTimeout(previewTimer);$("editor").hidden=true;$("gallery").hidden=false;history.replaceState(null,"","/slides");await list();};
 $("copy-deck").onclick=()=>newData({...active.deck,title:(active.deck.title.slice(0,111)+"（本机副本）")}).catch(e=>message(e.message));
 $("reload-deck").onclick=async()=>{if(!confirm("放弃本机未同步修改，载入云端版？"))return;try{localStorage.removeItem(localKey(active.id));await openDraft(active.id);}catch(e){message(e.message);}};
 function previewFor(i){
   const data={template:active.deck.template,title:active.deck.title,slide:{...active.deck.slides[i],notes:""},number:i+1,total:active.deck.slides.length};
   const key=JSON.stringify(data);
   if(!previewCache.has(key)){
     if(previewCache.size>=80)previewCache.delete(previewCache.keys().next().value);
     const task=api("/api/slides/preview","POST",data).then(r=>({src:"data:image/svg+xml;charset=utf-8,"+encodeURIComponent(r.svg),overflow:r.overflow}));
     previewCache.set(key,task);task.catch(()=>previewCache.delete(key));
   }
   return previewCache.get(key);
 }
 function navigation(){
   observer?.disconnect();
   observer=new IntersectionObserver(entries=>{for(const entry of entries){
     if(!entry.isIntersecting)continue;const tile=entry.target;observer.unobserve(tile);
     const i=Number(tile.dataset.index);if(!active||!active.deck.slides[i])continue;
     previewFor(i).then(r=>{if(tile.isConnected)tile.querySelector("img").src=r.src;}).catch(()=>{});
   }},{root:$("page-list"),rootMargin:"32px"});
   $("page-list").replaceChildren(...active.deck.slides.map((slide,i)=>{
     const b=button("",()=>{page=i;draw();},"slide-row");b.dataset.index=i;b.setAttribute("aria-current",i===page?"page":"false");
     const img=el("img");img.alt="";const label=el("div",undefined,"slide-row-label");label.append(el("span",String(i+1)),el("strong",slide.title||names[slide.layout]));
     b.append(img,label);b.draggable=true;
     b.ondragstart=e=>{dragSource={doc:active.id,slide};e.dataTransfer.effectAllowed="move";e.dataTransfer.setData("text/plain",String(i+1));};
     b.ondragover=e=>{if(dragSource?.doc===active.id){e.preventDefault();e.dataTransfer.dropEffect="move";b.classList.add("drop-target");}};
     b.ondragleave=()=>b.classList.remove("drop-target");
     b.ondragend=()=>{dragSource=null;document.querySelectorAll(".drop-target").forEach(x=>x.classList.remove("drop-target"));};
     b.ondrop=e=>{if(dragSource?.doc!==active.id)return;e.preventDefault();const from=active.deck.slides.indexOf(dragSource.slide);dragSource=null;
      if(from>=0&&from!==i){const moved=active.deck.slides.splice(from,1)[0];active.deck.slides.splice(i,0,moved);page=i;changed();draw();}else b.classList.remove("drop-target");};
     observer.observe(b);return b;
   }));
   const n=active.deck.slides.length;$("page-number").textContent=(page+1)+" / "+n+" · "+names[current().layout];$("show-count").textContent=(page+1)+" / "+n;
   for(const id of ["prev-page","show-prev","up"])$(id).disabled=page===0;
   for(const id of ["next-page","show-next","down"])$(id).disabled=page===n-1;
   $("remove").disabled=n===1;$("duplicate").disabled=$("add-slide").disabled=n>=32;
 }
 function requestPreview(){
   const seq=++previewSeq;clearTimeout(previewTimer);
   previewTimer=setTimeout(async()=>{
    if(!active||seq!==previewSeq)return;
    try{const res=await previewFor(page);
     if(seq!==previewSeq)return;
     const src=res.src;$("slide-preview").src=src;$("show-image").src=src;const thumb=$("page-list").children[page]?.querySelector("img");if(thumb)thumb.src=src;
     $("preview-warning").textContent=res.overflow.length?"本页文字过多，请精简或拆页后导出。":"";
    }catch(e){if(seq===previewSeq)$("preview-warning").textContent=e.message;}
   },120);
 }
 function draw(){
   const slide=current();navigation();$("layout").value=slide.layout;
   $("fields").replaceChildren(...slots[slide.layout].map(key=>{
    const [label,max]=controls[key],wrap=el("label",label),input=el(["title","left_title","right_title"].includes(key)?"input":"textarea");
    input.id="field-"+key;input.maxLength=max;input.value=slide[key]||"";if(input.tagName==="TEXTAREA")input.rows=key==="body"?7:3;
    input.oninput=()=>{slide[key]=input.value;changed();if(key==="title")$("page-list").children[page].querySelector("strong").textContent=slide.title||names[slide.layout];requestPreview();};wrap.append(input);return wrap;
   }));
   $("slide-notes").value=slide.notes||"";$("slide-eyebrow").value=slide.eyebrow||"";requestPreview();
 }
 $("slide-notes").oninput=e=>{current().notes=e.target.value;changed();};
 $("slide-eyebrow").oninput=e=>{current().eyebrow=e.target.value;changed();requestPreview();};
 $("deck-title").oninput=e=>{active.deck.title=e.target.value.trim()||"无题演示";changed();requestPreview();};
 $("layout").onchange=e=>{current().layout=e.target.value;changed();draw();};
 $("theme").onchange=e=>{active.deck.template=e.target.value;changed();navigation();requestPreview();};
 function step(d){page=Math.max(0,Math.min(active.deck.slides.length-1,page+d));draw();}
 for(const [id,d] of [["prev-page",-1],["next-page",1],["show-prev",-1],["show-next",1]])$(id).onclick=()=>step(d);
 function move(d){const slides=active.deck.slides;if(!slides[page+d])return;[slides[page],slides[page+d]]=[slides[page+d],slides[page]];page+=d;changed();draw();}
 $("up").onclick=()=>move(-1);$("down").onclick=()=>move(1);
 function insert(slide){if(active.deck.slides.length>=32)return;active.deck.slides.splice(++page,0,slide);changed();draw();$("field-title").focus();}
 $("add-slide").onclick=()=>insert(defaults());$("duplicate").onclick=()=>insert(structuredClone(current()));
 $("remove").onclick=()=>{if(active.deck.slides.length<2||!confirm("移除当前页？"))return;active.deck.slides.splice(page,1);page=Math.min(page,active.deck.slides.length-1);changed();draw();};
 $("present").onclick=()=>{$("show-dialog").showModal();requestPreview();};$("end-show").onclick=()=>$("show-dialog").close();
 $("show-dialog").onkeydown=e=>{if(e.key==="ArrowRight"||e.key==="ArrowLeft"){e.preventDefault();step(e.key==="ArrowLeft"?-1:1);}};
 async function rawResponse(url,body,form=false){
   const headers={"X-Yanfolio-Request":"1","X-Yanfolio-Account":String(user.id)};if(!form)headers["Content-Type"]="application/json";
   const r=await fetch(url,{method:"POST",headers,body:form?body:JSON.stringify(body)});
   if(r.status===401)location.replace("/login.html?next=/slides");if(!r.ok){const j=await r.json().catch(()=>({}));throw Error(j.detail||"请求失败。");}return r;
 }
 async function output(cloud){
   const b=cloud?$("deck-cloud"):$("deck-export");b.disabled=true;
   try{const deck=structuredClone(active.deck),name=(deck.title||"演示稿").replace(/[\\/:*?"<>|]/g,"_")+".pptx";
    const res=await rawResponse("/api/slides/export",deck),blob=await res.blob();
    if(cloud){const chosen=prompt("云文档文件名",name);if(!chosen)return;await YanfolioDrive.upload(new File([blob],chosen.toLowerCase().endsWith(".pptx")?chosen:chosen+".pptx",{type:blob.type}));message("PPTX 已保存到云文档。");}
    else{const a=el("a");a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),10000);}
   }catch(e){message(e.message);}finally{b.disabled=false;}
 }
 $("deck-export").onclick=()=>output(false);$("deck-cloud").onclick=()=>output(true);
 async function creator(theme=themes[0].id,fromManuscript=false){
   pendingQuote=null;creating=false;disabled(false);$("quote").hidden=true;$("create-status").textContent="";$("new-template").value=theme;
   $("new-title").value="";$("material").value="";sourceRefs=[];$("source-doc").replaceChildren(new Option("输入题目或自行粘贴材料",""));
   $("create-dialog").showModal();$("new-title").focus();
   try{const ws=await api("/api/workspace");sources=ws.content?.docs||[];$("source-doc").replaceChildren(new Option("输入题目或自行粘贴材料",""),...sources.map(d=>new Option(d.title||"无题手稿",d.id)));
    if(fromManuscript){let handoff;try{handoff=JSON.parse(sessionStorage.getItem("yanfolio.to-slides."+user.id)||"null");sessionStorage.removeItem("yanfolio.to-slides."+user.id);}catch{}
     const d=handoff||sources.find(x=>x.id===ws.content?.active);if(d){$("source-doc").value=d.id;setMaterial(d);}}
   }catch(e){$("create-status").textContent=e.message;}
 }
 function setMaterial(d){$("new-title").value=(d.title||"演示稿").slice(0,120);$("material").value=(d.text||"").slice(0,20000);sourceRefs=d.references||[];if(d.text?.length>20000)$("create-status").textContent="已带入前 20,000 字，可在生成前调整材料。";}
 $("source-doc").onchange=e=>{const d=sources.find(x=>x.id===e.target.value);if(d)setMaterial(d);else sourceRefs=[];invalidateQuote();};
 function invalidateQuote(){if(!creating){pendingQuote=null;$("quote").hidden=true;}}
 $("create-form").addEventListener("input",invalidateQuote);$("create-form").addEventListener("change",invalidateQuote);
 $("new-deck").onclick=()=>creator();$("cancel-create").onclick=()=>$("create-dialog").close();
 $("create-dialog").addEventListener("cancel",e=>{if(creating)e.preventDefault();});
 $("make-free").onclick=async()=>{
  if(!$("create-form").reportValidity())return;
  try{const title=$("new-title").value.trim(),text=$("material").value.trim();if(!title)throw Error("请输入演示题目。");
   const slides=[{...defaults("cover"),title:title.slice(0,90)}];
   for(const block of text.split(/\n\s*\n/).filter(Boolean)){
    const chars=Array.from(block.trim());while(chars.length){const part=chars.splice(0,260).join(""),lines=part.split(/\r?\n/);
     const hasTitle=lines.length>1&&lines[0].length<=60;slides.push({...defaults(),title:hasTitle?lines.shift().replace(/^#+\s*/,""):"要点 "+slides.length,body:lines.join("\n")});
     if(slides.length>32)throw Error("材料较长，请精简后分页，或分成多份演示。");}}
   creating=true;disabled(true);await newData({title,template:$("new-template").value,slides});$("create-dialog").close();
  }catch(e){$("create-status").textContent=e.message;}finally{creating=false;disabled(false);}
 };
 $("create-form").onsubmit=async e=>{
  e.preventDefault();if(!models.length){$("create-status").textContent="暂无可用写作模型，可直接建稿。";return;}
  creating=true;disabled(true);$("create-status").textContent="正在获取点数报价…";
  try{const input={action:"slides",title:$("new-title").value.trim(),text:$("material").value,model_id:Number($("slide-model").value),
      references:sourceRefs,template_id:$("new-template").value,page_count:Number($("page-count").value)};
    const q=await api("/api/write/quote","POST",input);pendingQuote={...input,request_id:crypto.randomUUID(),quote:q.quote};
    $("quote-text").textContent=q.label+" · "+input.page_count+" 页 · 最高 "+q.maximum+" 点，余额 "+q.balance+" 点。";$("quote").hidden=false;
    $("create-status").textContent=q.balance<q.maximum?"点数不足。可选择直接建稿，或在钱包中充值。":"";pendingQuote.canPay=q.balance>=q.maximum;
  }catch(err){$("create-status").textContent=err.message;pendingQuote=null;$("quote").hidden=true;}finally{creating=false;disabled(false);$("confirm-ai").disabled=!pendingQuote?.canPay;}
 };
 $("confirm-ai").onclick=async()=>{
  if(!pendingQuote?.canPay||creating)return;const {canPay,...body}=pendingQuote;creating=true;disabled(true);$("create-status").textContent="正在编排逐页大纲…";
  try{const r=await api("/api/write","POST",body);openData(r.presentation);pendingQuote=null;$("create-dialog").close();message("已生成 "+r.presentation.deck.slides.length+" 页，实收 "+r.charged+" 点。"+(r.flagged_pages?"有 "+r.flagged_pages+" 页的讲者备注含待核对项。":""));}
  catch(e){$("create-status").textContent=e.message;if(e.status&&e.status!==409){pendingQuote=null;$("quote").hidden=true;}}
  finally{creating=false;disabled(false);}
 };
 $("import-ppt").onclick=()=>{$("import-status").textContent="";$("ppt-file").value="";$("import-dialog").showModal();};$("cancel-import").onclick=()=>$("import-dialog").close();
 async function importFile(file){const form=new FormData();form.append("presentation",file);const deck=await(await rawResponse("/api/slides/import?template="+encodeURIComponent($("import-theme").value),form,true)).json();await newData(deck);}
 $("import-form").onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector(".primary");b.disabled=true;try{await importFile($("ppt-file").files[0]);$("import-dialog").close();}catch(err){$("import-status").textContent=err.message;}finally{b.disabled=false;}};
 $("logout").onclick=async()=>{try{await flush();await YF.logout();}catch(e){message(e.message);}};
 window.addEventListener("online",()=>flush().catch(e=>message(e.message)));
 document.addEventListener("visibilitychange",()=>{if(document.hidden)flush().catch(e=>message(e.message));});
 const [assets,catalog]=await Promise.all([api("/api/slides/templates"),api("/api/catalog")]);themes=assets.templates;models=catalog.models;
 for(const id of ["theme","new-template","import-theme"])$(id).replaceChildren(...themes.map(t=>new Option(t.name,t.id)));
 $("slide-model").replaceChildren(...models.map(m=>new Option(m.label+" · "+m.fee+" 点起",m.id)));
 $("templates").replaceChildren(...themes.map(t=>{const box=el("article",undefined,"template-card"),a=button("",()=>creator(t.id),"template-cover"),img=el("img");img.src="/api/slides/templates/"+t.id+"/thumbnail";img.alt="使用"+t.name+"模板";a.append(img);
   const actions=el("div",undefined,"actions"),src=link(t.license+" · 来源",t.source_url);src.target="_blank";src.rel="noopener noreferrer";actions.append(link("下载样板 PPTX","/api/slides/templates/"+t.id+"/download"),src);box.append(a,el("h3",t.name),el("p",t.description),actions);return box;}));
 await list();const query=new URLSearchParams(location.search);
 if(query.get("deck"))await openDraft(query.get("deck"));
 else if(query.get("from")==="manuscript")await creator(themes[0].id,true);
 else if(query.get("cloud")){
   const id=query.get("cloud"),info=await api("/api/drive/files/"+id+"/versions"),head=info.versions.find(v=>v.id===info.file.head);
   if(!head||head.bytes>16*1024*1024||!info.file.name.toLowerCase().endsWith(".pptx"))throw Error("请选择 16 MB 以内的 PPTX 文件。");
   const res=await fetch("/api/drive/files/"+id+"/download?version="+info.file.head);
   if(!res.ok)throw Error("读取云文档失败。");await importFile(new File([await res.blob()],info.file.name));
 }
})().catch(e=>{const box=document.getElementById("feedback");box.hidden=false;box.textContent=e.message;});

