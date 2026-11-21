"use strict";
window.YanfolioDrive={
 fmt(n){if(n>=1e9)return +(n/1e9).toFixed(2)+" GB";if(n>=1e6)return +(n/1e6).toFixed(2)+" MB";if(n>=1e3)return +(n/1e3).toFixed(1)+" KB";return n+" B";},
 async hash(data){return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",data)),b=>b.toString(16).padStart(2,"0")).join("");},
 async upload(file,{folder="",target=null,resume=null,signal,progress=()=>{}}={}){
   const spec={name:file.name,size:file.size,client_id:resume?.client_id||crypto.randomUUID(),folder:resume?.folder??folder,
     file_id:resume?.target??target?.id??null,base_version:resume?.base??target?.head??null};
   if(resume && (resume.total!==file.size || resume.name!==file.name))throw Error("请选择与暂停任务名称及大小相同的原文件。");
   const u=await YF.api("/api/drive/uploads","POST",spec);if(u.file_id)return {file_id:u.file_id,version:u.id};
   const url="/api/drive/uploads/"+u.id;
   if(u.offset){
     const state=await YF.api(url);
     for(const part of state.parts){signal?.throwIfAborted();if(await this.hash(await file.slice(part.offset,part.offset+part.bytes).arrayBuffer())!==part.sha)throw Error("已上传部分与所选文件内容不同，请选择原文件或取消旧任务。");}
   }
   let offset=u.offset;progress(offset,file.size);
   while(offset<file.size){
     signal?.throwIfAborted();const data=await file.slice(offset,offset+u.chunk_bytes).arrayBuffer();
     const headers={"X-Yanfolio-Request":"1","X-Yanfolio-Account":String(YF.account),"X-Chunk-SHA256":await this.hash(data),"Content-Type":"application/octet-stream"};
     const r=await fetch(url+"/part?offset="+offset,{method:"PUT",headers,body:data,signal});
     if(r.status===401){location.assign("/login.html?next=/drive.html");throw Error("请重新登录。");}
     const j=await r.json();if(!r.ok)throw Error(j.detail||"分片传输失败。");offset=j.offset;progress(offset,file.size);
   }
   signal?.throwIfAborted();return YF.api(url+"/finish","POST",{});
 }
};

