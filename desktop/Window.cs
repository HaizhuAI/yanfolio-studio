using System;
using System.Drawing;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal sealed class Workspace : Form {
    private readonly WebView2 view = new WebView2();
    private readonly Label status = new Label();
    private readonly string profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Yanfolio","Browser");
    private Uri endpoint;
    private string ConfigFile { get { return Path.Combine(profile,"service.txt"); } }

    internal Workspace() {
        Text="砚稿 Yanfolio"; Width=1350; Height=900; MinimumSize=new Size(760,540);
        StartPosition=FormStartPosition.CenterScreen;
        var menu=new MenuStrip();
        menu.Items.Add("写作工作台",null,(s,e)=>Go("/"));
        menu.Items.Add("点数钱包",null,(s,e)=>Go("/wallet.html"));
        menu.Items.Add("连接服务器",null,(s,e)=>Configure());
        status.Dock=DockStyle.Bottom; status.Height=23; status.Padding=new Padding(7,2,0,0);
        view.Dock=DockStyle.Fill; Controls.Add(view); Controls.Add(status); Controls.Add(menu); MainMenuStrip=menu;
        Load+=async (sender,evt)=>{
            try {
                Directory.CreateDirectory(profile);
                Uri stored;
                endpoint=File.Exists(ConfigFile) && Valid(File.ReadAllText(ConfigFile).Trim(),out stored)?stored:new Uri(BuildConfig.ServiceUrl);
                var env=await CoreWebView2Environment.CreateAsync(null,profile);
                await view.EnsureCoreWebView2Async(env);
                view.CoreWebView2.Settings.AreHostObjectsAllowed=false;
                view.CoreWebView2.Settings.IsWebMessageEnabled=false;
                view.CoreWebView2.NavigationStarting+=(s,e)=>{
                    Uri next;
                    if (!Uri.TryCreate(e.Uri,UriKind.Absolute,out next) || next.GetLeftPart(UriPartial.Authority)!=endpoint.GetLeftPart(UriPartial.Authority)) {
                        e.Cancel=true;
                        OpenExternal(next);
                    }
                };
                view.CoreWebView2.NewWindowRequested+=(s,e)=>{e.Handled=true;Uri next;if(Uri.TryCreate(e.Uri,UriKind.Absolute,out next)) OpenExternal(next);};
                view.CoreWebView2.NavigationCompleted+=(s,e)=>{status.Text=e.IsSuccess?"已连接   "+endpoint.Authority:"连接失败。请确认服务已启动，或使用“连接服务器”填写运营方地址。";};
                Go("/");
            } catch(Exception ex){status.Text="桌面运行环境未就绪"; MessageBox.Show("请安装 Microsoft Edge WebView2 Evergreen Runtime 后重试。\n"+ex.Message,Text);}
        };
    }
    private static bool Valid(string value,out Uri uri) {
        return Uri.TryCreate(value,UriKind.Absolute,out uri) && String.IsNullOrEmpty(uri.UserInfo) &&
            (uri.Scheme=="https" || (uri.Scheme=="http" && uri.IsLoopback)) && uri.AbsolutePath=="/" &&
            String.IsNullOrEmpty(uri.Query) && String.IsNullOrEmpty(uri.Fragment);
    }
    private static void OpenExternal(Uri uri) {
        if(uri!=null && (uri.Scheme=="https" || uri.Scheme=="http")) Process.Start(new ProcessStartInfo(uri.AbsoluteUri){UseShellExecute=true});
    }
    private void Go(string path) {
        if(view.CoreWebView2!=null){status.Text="连接中   "+endpoint.Authority;view.CoreWebView2.Navigate(new Uri(endpoint,path).AbsoluteUri);}
    }
    private void Configure() {
        using(var dialog=new Form()){dialog.Text="连接砚稿服务器";dialog.ClientSize=new Size(470,124);dialog.StartPosition=FormStartPosition.CenterParent;
            var label=new Label(){Left=15,Top=12,Width=440,Text="运营方 HTTPS 地址，或本机回环地址"};
            var box=new TextBox(){Left=15,Top=38,Width=435,Text=endpoint==null?BuildConfig.ServiceUrl:endpoint.AbsoluteUri};
            var save=new Button(){Left=365,Top=77,Text="连接",DialogResult=DialogResult.OK};
            dialog.Controls.AddRange(new Control[]{label,box,save});dialog.AcceptButton=save;
            if(dialog.ShowDialog(this)!=DialogResult.OK)return;
            Uri next;if(!Valid(box.Text.Trim(),out next)){MessageBox.Show("请输入有效的 HTTPS 服务根地址。",Text);return;}
            endpoint=next;Directory.CreateDirectory(profile);File.WriteAllText(ConfigFile,endpoint.AbsoluteUri);Go("/");
        }
    }
    [STAThread] static void Main(){Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Workspace());}
}

