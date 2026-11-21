"use strict";
(() => {
 const paths={
   book:"M3 4.5c3.2-.7 6.2-.1 9 1.9 3-2 5.8-2.6 9-1.9v14c-3.6-.6-6.3.1-9 2-2.7-1.9-5.4-2.6-9-2z M12 6.5v14",
   plus:"M12 5v14M5 12h14",pen:"m4 20 4-1 12-12-3-3L5 16l-1 4Zm10-13 3 3",
   search:"M20 20l-4.6-4.6 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
   layout:"M3 4h18v16H3zM3 9h18M9 9v11",drive:"m3 14 3-9h12l3 9v5H3zM3 14h18m-6 2.5h3",
   check:"m4 12 5 5L20 6",download:"M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4",upload:"M12 16V4m-5 5 5-5 5 5M4 16v4h16v-4",
   file:"M6 3h8l5 5v13H6zM14 3v5h5m-10 5h7m-7 4h5",align:"M4 5h16M4 10h12M4 15h16M4 20h10",undo:"m8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12",
   spark:"m10 3 1.7 5.3L17 10l-5.3 1.7L10 17l-1.7-5.3L3 10l5.3-1.7L10 3Zm8 11 1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3Z",
   bookmark:"M6 3h12v18l-6-4-6 4z",books:"M3 5h4v14H3zM9 5h4v14H9zM15 6l3-1 4 13-3 1z",
   checklist:"M9 6h11M9 12h11M9 18h11m-17-12 1 1 2-3m-3 8 1 1 2-3m-3 8 1 1 2-3",
   cloud:"M6.5 18a4.5 4.5 0 0 1-.5-9 6.3 6.3 0 0 1 12-1 5.1 5.1 0 0 1-.2 10z",
   user:"M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2c0-3 3-5 8-5s8 2 8 5v2",
   wallet:"M3 7V5l14-2v4M3 7h18v13H3zM21 11h-6v5h6m-4-2.5h.1",
   desktop:"M3 4h18v13H3zM12 17v4m-4 0h8",folder:"M3 6h7l2 2h9v12H3z",
   focus:"M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5",eye:"M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Zm12.5 0a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0",
   hide:"M3 3l18 18M10 6.3a11 11 0 0 1 2-.3c6.5 0 10 6 10 6s-1 1.7-3.1 3.4M6.5 7.4A17 17 0 0 0 2 12s3.5 6 10 6a12 12 0 0 0 4.1-.8",
   layers:"m3 8 9-5 9 5-9 5zM3 12l9 5 9-5M3 16l9 5 9-5",
   sliders:"M3 6h10m4 0h4M3 12h4m4 0h10M3 18h12m4 0h2M13 4v4M7 10v4m8 2v4",
   arrow:"M5 12h14m-6-6 6 6-6 6",back:"M19 12H5m6-6-6 6 6 6",left:"m15 5-7 7 7 7",right:"m9 5 7 7-7 7",
   trash:"M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15m-9 4v7m4-7v7",clock:"M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0m-9-5v6l3 2",
   logout:"M10 4H4v16h6m4-13 5 5-5 5m-6-5h11",shield:"m12 2 8 4v6c0 5-4 8-8 10-4-2-8-5-8-10V6zM8 12l3 3 5-6"
 };
 function icon(name){
   const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg"),path=document.createElementNS(ns,"path");
   svg.setAttribute("class","icon");svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("aria-hidden","true");path.setAttribute("d",paths[name]||paths.file);svg.append(path);return svg;
 }
 function icons(root=document){root.querySelectorAll("i[data-icon]").forEach(el=>el.replaceWith(icon(el.dataset.icon)));}
 function motion(){return !matchMedia("(prefers-reduced-motion: reduce)").matches;}
 function enter(el){if(el&&motion()&&el.animate)el.animate([{opacity:.45,transform:"translateY(5px)"},{opacity:1,transform:"translateY(0)"}],{duration:230,easing:"cubic-bezier(.22,.78,.23,1)"});}
 function setupNavigator(){
   const nav=document.querySelector(".account-nav,.sidebar");
   if(!nav)return;
   const routes=[
     {name:"论文创作",icon:"pen",url:"/studio",keys:"writing write lunwen",view:"write"},
     {name:"文献检索",icon:"search",url:"/studio?view=search",keys:"search literature wenxian",view:"search"},
     {name:"格式工作室",icon:"layout",url:"/studio?view=format",keys:"format word geshi",view:"format"},
     {name:"我的云文档",icon:"folder",url:"/drive.html",keys:"files cloud wendang"},
     {name:"个人中心",icon:"user",url:"/profile.html",keys:"profile account geren"},
     {name:"点数钱包",icon:"wallet",url:"/wallet.html",keys:"wallet credits qianbao"}
   ];
   const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;};
   const launcher=make("button","command-launch");launcher.type="button";launcher.append(icon("search"),make("span","","快速导航"),make("kbd","","Ctrl K"));launcher.setAttribute("aria-haspopup","dialog");
   const brand=nav.querySelector(".brand");if(brand)brand.after(launcher);else nav.prepend(launcher);
   const dialog=make("dialog","jump-dialog");dialog.setAttribute("aria-label","快速导航");
   const line=make("div","jump-line"),input=make("input"),close=make("button","jump-esc","Esc"),list=make("ul","jump-list");
   input.type="search";input.placeholder="查找页面或工具";input.autocomplete="off";input.setAttribute("aria-label","查找页面或工具");
   input.setAttribute("role","combobox");input.setAttribute("aria-expanded","true");input.setAttribute("aria-controls","jump-list");input.setAttribute("aria-autocomplete","list");
   list.id="jump-list";list.setAttribute("role","listbox");list.setAttribute("aria-label","匹配的页面");
   close.type="button";close.setAttribute("aria-label","关闭快速导航");line.append(icon("search"),input,close);dialog.append(line,list);document.body.append(dialog);
   let visible=[],index=0,previous=null;
   function paint(){Array.from(list.querySelectorAll('[role="option"]')).forEach((row,i)=>row.setAttribute("aria-selected",i===index));if(visible.length)input.setAttribute("aria-activedescendant","jump-"+index);else input.removeAttribute("aria-activedescendant");}
   function go(i){const r=visible[i];if(!r)return;previous=null;dialog.close();if(r.view&&document.querySelector(".shell")){const button=document.querySelector('nav [data-view="'+r.view+'"]');if(button){button.click();return;}}location.assign(r.url);}
   function render(){const key=input.value.trim().toLowerCase();visible=routes.filter(r=>(r.name+" "+r.keys).includes(key));index=0;list.replaceChildren();
     visible.forEach((r,i)=>{const row=make("li");row.id="jump-"+i;row.setAttribute("role","option");row.append(icon(r.icon),make("span","",r.name));row.onpointerdown=e=>e.preventDefault();row.onclick=()=>go(i);list.append(row);});
     if(!visible.length)list.append(make("li","jump-empty","没有匹配的页面。"));paint();}
   function open(){if(dialog.open)return;previous=document.activeElement;input.value="";render();dialog.showModal();input.focus();enter(dialog);}
   launcher.onclick=open;close.onclick=()=>dialog.close();input.oninput=render;
   dialog.addEventListener("close",()=>{if(previous instanceof HTMLElement&&previous.isConnected)previous.focus({preventScroll:true});});
   dialog.addEventListener("click",e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dialog.close();});
   input.onkeydown=e=>{if(!visible.length)return;if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();index=(index+(e.key==="ArrowDown"?1:-1)+visible.length)%visible.length;paint();}else if(e.key==="Enter"){e.preventDefault();go(index);}};
   document.addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&!e.altKey&&!e.shiftKey&&e.code==="KeyK"){e.preventDefault();if(dialog.open)dialog.close();else open();}
     if(document.documentElement.classList.contains("native-client")&&e.ctrlKey&&!e.shiftKey&&!e.altKey&&/^Digit[1-4]$/.test(e.code)){e.preventDefault();location.assign(["/studio","/drive.html","/profile.html","/wallet.html"][Number(e.code.slice(-1))-1]);}});
   window.YanUI.openNavigator=open;
 }
 window.YanUI={icon,icons,motion,enter};
 document.documentElement.classList.toggle("native-client",navigator.userAgent.includes("YanfolioDesktop/"));
 icons();
 setupNavigator();
 document.querySelectorAll(".account-nav a[href]").forEach(a=>{if(new URL(a.href).pathname===location.pathname)a.setAttribute("aria-current","page");});
})();

