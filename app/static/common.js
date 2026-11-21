"use strict";
window.YF={
 el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;},
 async api(url,method="GET",data){
   const opt={method,headers:{"X-Yanfolio-Request":"1"}};
   if(data!==undefined){opt.headers["Content-Type"]="application/json";opt.body=JSON.stringify(data);}
   const r=await fetch(url,opt);const out=await r.json().catch(()=>({}));
   if(!r.ok){if(r.status===401&&!location.pathname.startsWith("/login"))location.replace("/login.html");const err=new Error(typeof out.detail==="string"?out.detail:"输入格式有误，请检查后重试。");err.status=r.status;throw err;}
   return out;
 },
 date(stamp){return new Date(stamp*1000).toLocaleString("zh-CN",{hour12:false});},
 async logout(){await YF.api("/api/auth/logout","POST");location.replace("/login.html");}
};
window.addEventListener("pageshow",e=>{if(e.persisted)location.reload();});

