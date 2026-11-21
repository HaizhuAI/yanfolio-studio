"use strict";
(() => {
 const key="yanfolio.appearance.v1", root=document.documentElement, media=matchMedia("(prefers-color-scheme: dark)");
 const defaults={mode:"system",ui_font:"geist",reading_font:"system",reading_size:18};
 const modes={system:"跟随系统",light:"浅色",dark:"深色"};
 const faces={geist:"Geist · 系统中文",system:"系统默认",sans:"Noto Sans SC · 黑体",serif:"Noto Serif SC · 宋体"};
 const readers={system:"系统衬线",interface:"跟随界面",sans:faces.sans,serif:faces.serif};
 function clean(p){
   p=p||{};return {mode:Object.hasOwn(modes,p.mode)?p.mode:defaults.mode,ui_font:Object.hasOwn(faces,p.ui_font)?p.ui_font:defaults.ui_font,
    reading_font:Object.hasOwn(readers,p.reading_font)?p.reading_font:defaults.reading_font,reading_size:[16,18,20].includes(+p.reading_size)?+p.reading_size:18};
 }
 function cached(){try{return JSON.parse(localStorage.getItem(key)||"null")||{};}catch{return {};}}
 let saved=clean(cached()),shown=saved,uid=null,dialog=null;
 function apply(p){
   shown=clean(p);const theme=shown.mode==="system"?(media.matches?"dark":"light"):shown.mode;
   if(root.dataset.theme&&root.dataset.theme!==theme){root.classList.add("theme-switching");requestAnimationFrame(()=>requestAnimationFrame(()=>root.classList.remove("theme-switching")));}
   root.dataset.theme=theme;root.dataset.themeMode=shown.mode;root.dataset.uiFont=shown.ui_font;root.dataset.readFont=shown.reading_font;
   root.style.setProperty("--reader-size",shown.reading_size+"px");
   if(navigator.userAgent.includes("YanfolioDesktop/"))window.chrome?.webview?.postMessage("yanfolio.theme."+theme);
 }
 function remember(p){saved=clean(p);try{localStorage.setItem(key,JSON.stringify({...saved,uid}));}catch{}}
 apply(saved);media.addEventListener("change",()=>{if(shown.mode==="system")apply(shown);});
 window.addEventListener("storage",e=>{if(e.key!==key||dialog?.open)return;const value=cached();if(uid!==null&&value.uid!==uid)return;saved=clean(value);apply(saved);});
 function start(){
   const authPage=!!document.querySelector(".shell,.business,.deck-app");
   const host=document.querySelector(".sidebar-foot,.account-nav,.deck-utilities,.auth-card footer,.foot");
   if(!host)return;
   let ready=Promise.resolve();
   if(authPage)ready=fetch("/api/preferences").then(async r=>{if(!r.ok)throw Error();const v=await r.json();uid=v.uid;remember(v);if(!dialog?.open)apply(saved);}).catch(()=>{});
   const make=(tag,txt,cls)=>{const e=document.createElement(tag);if(txt)e.textContent=txt;if(cls)e.className=cls;return e;};
   const openButton=make("button",null,"appearance-open");openButton.type="button";openButton.setAttribute("aria-haspopup","dialog");openButton.setAttribute("aria-label","外观设置");
   openButton.append(window.YanUI?.icon("sliders")||make("span","◐"),make("span","外观设置"));
   if(host.classList.contains("sidebar-foot"))host.before(openButton);else if(host.classList.contains("account-nav"))host.querySelector("#logout")?.before(openButton);else host.append(openButton);
   dialog=make("dialog",null,"appearance-dialog");dialog.setAttribute("aria-label","外观设置");
   const h=make("h2","外观设置"),form=make("form"),group=make("fieldset"),legend=make("legend","显示模式"),row=make("div",null,"theme-choices");
   const modeButtons=[];
   for(const [v,label] of Object.entries(modes)){const b=make("button",label);b.type="button";b.dataset.mode=v;b.onclick=()=>{apply({...shown,mode:v});paint();};row.append(b);modeButtons.push(b);}
   group.append(legend,row);
   function select(label,choices,prop){const l=make("label",label),select=make("select");select.name=prop;for(const [v,name] of Object.entries(choices))select.append(new Option(name,v));select.onchange=()=>apply({...shown,[prop]:select.value});l.append(select);return l;}
   const preview=make("div",null,"type-preview");preview.append(make("strong","研究问题与证据"),make("p","同一份手稿，可以按自己的阅读习惯调整字体。"));
   const tools=make("div",null,"appearance-actions"),cancel=make("button","取消","button"),save=make("button","保存设置","primary");
   cancel.type="button";cancel.onclick=()=>dialog.close();save.type="submit";tools.append(cancel,save);
   const status=make("p",null,"feedback");status.setAttribute("role","status");
   form.append(group,select("界面字体",faces,"ui_font"),select("手稿正文字体",readers,"reading_font"),select("正文字号",{"16":"16 px","18":"18 px","20":"20 px"},"reading_size"),preview,status,tools);
   dialog.append(h,form);document.body.append(dialog);
   function paint(){modeButtons.forEach(b=>b.setAttribute("aria-pressed",b.dataset.mode===shown.mode));for(const prop of ["ui_font","reading_font","reading_size"])form.elements[prop].value=String(shown[prop]);}
   openButton.onclick=async()=>{await ready;apply(saved);status.textContent="";paint();dialog.showModal();modeButtons.find(b=>b.dataset.mode===shown.mode)?.focus();};
   window.YanfolioAppearance={open:openButton.onclick};
   form.onsubmit=async e=>{e.preventDefault();save.disabled=true;cancel.disabled=true;try{let data=shown;
    if(authPage){const opt={method:"PUT",headers:{"X-Yanfolio-Request":"1","Content-Type":"application/json"},body:JSON.stringify(data)};
      if(uid!==null)opt.headers["X-Yanfolio-Account"]=String(uid);const r=await fetch("/api/preferences",opt);if(!r.ok)throw Error("保存失败，请检查登录和网络。");data=await r.json();uid=data.uid;}
    remember(data);dialog.close();
   }catch(err){status.textContent=err.message;}finally{save.disabled=false;cancel.disabled=false;}};
   dialog.addEventListener("cancel",e=>{if(save.disabled)e.preventDefault();});
   dialog.addEventListener("close",()=>{apply(saved);openButton.focus({preventScroll:true});});
 }
 document.addEventListener("DOMContentLoaded",start,{once:true});
})();

