const by=id=>document.getElementById(id);
let mode="login",cooldown=0;
const labels={login:"登录砚稿",register:"注册账号",reset:"重设密码"};
function select(value){mode=value;YanUI.enter(by("auth-form"));by("auth-title").textContent=labels[mode];by("submit").textContent=mode==="login"?"登录":labels[mode];by("code-row").hidden=mode==="login";by("code").required=mode!=="login";by("password").minLength=mode==="login"?1:10;by("password").autocomplete=mode==="login"?"current-password":"new-password";by("pass-label").textContent=mode==="login"?"密码":"设置密码（至少 10 个字符）";by("response").textContent="";document.querySelectorAll(".auth-card footer [data-mode]").forEach(b=>b.hidden=b.dataset.mode===mode);}
document.querySelectorAll(".auth-card footer [data-mode]").forEach(b=>b.onclick=()=>select(b.dataset.mode));
by("send-code").onclick=async()=>{if(!by("email").reportValidity())return;const b=by("send-code");b.disabled=true;try{const r=await YF.api("/api/auth/code","POST",{email:by("email").value,purpose:mode});by("response").textContent=r.local?"本机验收模式：请到服务数据目录的 mail 文件夹读取验证码。":"请查收与这个邮箱对应的验证码，10 分钟内有效。";cooldown=60;const timer=setInterval(()=>{b.textContent=--cooldown+" 秒";if(!cooldown){clearInterval(timer);b.textContent="获取验证码";b.disabled=false;}},1000);}catch(e){by("response").textContent=e.message;b.disabled=false;}};
by("auth-form").onsubmit=async e=>{e.preventDefault();const b=by("submit");b.disabled=true;try{await YF.api("/api/auth/"+mode,"POST",{email:by("email").value,password:by("password").value,code:by("code").value});if(mode==="reset"){select("login");by("response").textContent="密码已更新，请重新登录。";}else{const next=new URLSearchParams(location.search).get("next");location.replace(["/admin.html","/wallet.html","/studio","/slides","/drive.html","/profile.html"].includes(next)?next:"/profile.html");}}catch(err){by("response").textContent=err.message;}finally{b.disabled=false;}};


YF.api("/api/auth/options").then(o=>by("desktop-download").hidden=!o.desktop).catch(()=>{});

if(new URLSearchParams(location.search).get("mode")==="register")select("register");

by("reveal-password").onclick=()=>{const field=by("password"),b=by("reveal-password"),show=field.type==="password";field.type=show?"text":"password";b.setAttribute("aria-label",show?"隐藏密码":"显示密码");b.setAttribute("aria-pressed",show);b.replaceChildren(YanUI.icon(show?"hide":"eye"));};
