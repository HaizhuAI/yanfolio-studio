"use strict";
(() => {
 const $=id=>document.getElementById(id);
 const tabs=[...document.querySelectorAll("[data-demo]")];
 function activate(b){
   tabs.forEach(t=>{const on=t===b;t.setAttribute("aria-selected",on);t.tabIndex=on?0:-1;$("demo-"+t.dataset.demo).hidden=!on;});
   YanUI.enter($("demo-"+b.dataset.demo));
 }
 tabs.forEach((b,i)=>{b.onclick=()=>activate(b);b.onkeydown=e=>{const steps={ArrowRight:1,ArrowLeft:-1,Home:-i,End:tabs.length-1-i};if(!(e.key in steps))return;e.preventDefault();const next=tabs[(i+steps[e.key]+tabs.length)%tabs.length];activate(next);next.focus();};});
 const review=$("review-copy"),marked=review.innerHTML;
 let accepted=false,cited=false;
 $("accept-demo").onclick=()=>{accepted=!accepted;if(accepted)review.textContent="本研究旨在探讨绿地覆盖与地表温度之间的关系。";else review.innerHTML=marked;
   $("accept-demo").textContent=accepted?"撤销示例修改":"采纳示例修改";$("review-state").textContent=accepted?"建议已写回示例手稿":"当前显示修改痕迹";YanUI.enter(review);};
 const citation=$("cite-line").textContent;
 $("insert-demo").onclick=()=>{cited=!cited;$("cite-line").textContent=citation+(cited?" [1]":"");$("insert-demo").textContent=cited?"移除示例引文":"插入示例引文";YanUI.enter($("cite-line"));};
 function compare(value){$("compare").value=value;$("compare").parentElement.style.setProperty("--split",value+"%");$("compare").setAttribute("aria-valuetext","模板显示 "+value+"%");}
 $("compare").oninput=e=>compare(e.target.value);$("only-before").onclick=()=>compare(0);$("only-after").onclick=()=>compare(100);
 const descriptions=[["Word 原稿","导入正文或使用原件排版"],["PDF 文献","保存原件与不同版本"],["BibTeX 题录","按项目整理检索资料"]];
 const cards=[...document.querySelectorAll("[data-sheet]")];
 function selectFile(active){
   cards.forEach(card=>{
     const i=(Number(card.dataset.sheet)-active+3)%3,target=[{x:0,y:-16,r:-3},{x:38,y:1,r:15},{x:-38,y:1,r:-16}][i];
     card.style.zIndex=String(4-i);
     if(YanUI.motion()&&window.anime){anime.utils.remove(card);anime.animate(card,{translateX:target.x,translateY:target.y,rotate:target.r,duration:380,ease:"out(4)"});}
     else card.style.transform="translate("+target.x+"px,"+target.y+"px) rotate("+target.r+"deg)";
   });
   $("file-caption").textContent=descriptions[active][0];$("file-detail").textContent=descriptions[active][1];
   document.querySelectorAll("[data-file]").forEach(b=>b.setAttribute("aria-pressed",Number(b.dataset.file)===active));
 }
 document.querySelectorAll("[data-file]").forEach(b=>b.onclick=()=>selectFile(Number(b.dataset.file)));
 if(YanUI.motion()&&window.anime){anime.animate(".hero-copy h1 span",{translateY:[12,0],opacity:[.52,1],delay:anime.stagger(55),duration:530,ease:"out(4)"});}
 const hero=document.querySelector(".hero"),stage=document.querySelector(".optic-stage");
 let frame=0,x=0,y=0;
 function move(){frame=0;stage.style.transform=YanUI.motion()?"translate("+x+"px,"+y+"px)":"none";}
 hero.onpointermove=e=>{if(e.pointerType!=="mouse"||!YanUI.motion()||!matchMedia("(min-width:661px)").matches)return;const box=hero.getBoundingClientRect();x=(.5-(e.clientX-box.left)/box.width)*7;y=(.5-(e.clientY-box.top)/box.height)*5;if(!frame)frame=requestAnimationFrame(move);};
 hero.onpointerleave=()=>{x=0;y=0;if(!frame)frame=requestAnimationFrame(move);};
 fetch("/api/auth/options").then(r=>r.json()).then(o=>{
   if(!o.desktop)document.querySelectorAll(".download").forEach(a=>a.hidden=true);
   if(o.signed_in){document.querySelectorAll("[data-entry]").forEach(a=>{a.href="/studio";a.textContent="进入工作台";});const a=document.querySelector(".login");a.href="/profile.html";a.textContent="个人中心";}
 }).catch(()=>{});
})();

