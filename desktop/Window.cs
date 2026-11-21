using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal sealed class RailButton : Button {
    internal bool Selected;
    private bool hovering;
    private readonly string glyph;
    internal RailButton(string caption,string name,string symbol) {
        Text=caption;AccessibleName=name;AccessibleRole=AccessibleRole.PushButton;glyph=symbol;
        FlatStyle=FlatStyle.Flat;FlatAppearance.BorderSize=0;TabStop=true;Cursor=Cursors.Hand;
        Width=66;Height=56;Margin=new Padding(7,3,7,3);
        Font=new Font("Microsoft YaHei UI",8.5f,FontStyle.Regular);BackColor=Color.FromArgb(17,18,30);
        SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);
    }
    protected override void OnMouseEnter(EventArgs e){base.OnMouseEnter(e);hovering=true;Invalidate();}
    protected override void OnMouseLeave(EventArgs e){base.OnMouseLeave(e);hovering=false;Invalidate();}
    protected override void OnGotFocus(EventArgs e){base.OnGotFocus(e);Invalidate();}
    protected override void OnLostFocus(EventArgs e){base.OnLostFocus(e);Invalidate();}
    protected override void OnPaint(PaintEventArgs e) {
        var g=e.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias;g.Clear(BackColor);
        var rect=new Rectangle(1,1,Width-3,Height-3);
        using(var path=Rounded(rect,9)) {
            if(Selected||hovering){using(var brush=new SolidBrush(Selected?Color.FromArgb(55,49,80):Color.FromArgb(38,38,55)))g.FillPath(brush,path);}
            if(Focused&&ShowFocusCues){using(var outline=new Pen(Color.FromArgb(179,165,255),1.4f))g.DrawPath(outline,path);}
        }
        var fg=Selected?Color.FromArgb(220,211,255):Color.FromArgb(202,202,220);
        var state=g.Save();float scale=Math.Max(.85f,Height/58f);g.TranslateTransform(Width/2f-12*scale,7*scale);g.ScaleTransform(scale,scale);
        using(var pen=new Pen(fg,1.65f)){
            pen.StartCap=pen.EndCap=LineCap.Round;pen.LineJoin=LineJoin.Round;
            if(glyph=="write"){g.DrawPolygon(pen,new[]{new Point(4,19),new Point(5,15),new Point(16,4),new Point(20,8),new Point(9,19)});g.DrawLine(pen,14,6,18,10);}
            else if(glyph=="folder"){g.DrawPolygon(pen,new[]{new Point(3,6),new Point(10,6),new Point(12,8),new Point(21,8),new Point(21,19),new Point(3,19)});}
            else if(glyph=="profile"){g.DrawEllipse(pen,8,3,8,8);g.DrawArc(pen,4,13,16,12,180,180);}
            else if(glyph=="wallet"){g.DrawRectangle(pen,3,7,18,13);g.DrawLines(pen,new[]{new Point(3,7),new Point(4,5),new Point(16,3),new Point(17,7)});g.DrawRectangle(pen,15,11,6,5);}
            else{g.DrawLine(pen,3,6,21,6);g.DrawLine(pen,3,12,21,12);g.DrawLine(pen,3,18,21,18);g.DrawLine(pen,9,4,9,8);g.DrawLine(pen,16,10,16,14);g.DrawLine(pen,7,16,7,20);}
        }
        g.Restore(state);
        TextRenderer.DrawText(g,Text,Font,new Rectangle(0,Height/2+2,Width,Height/2-4),fg,TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter|TextFormatFlags.NoPadding);
    }
    private static GraphicsPath Rounded(Rectangle r,int radius){
        var p=new GraphicsPath();int d=radius*2;p.AddArc(r.Left,r.Top,d,d,180,90);p.AddArc(r.Right-d,r.Top,d,d,270,90);
        p.AddArc(r.Right-d,r.Bottom-d,d,d,0,90);p.AddArc(r.Left,r.Bottom-d,d,d,90,90);p.CloseFigure();return p;
    }
}

internal sealed class Workspace : Form {
    private readonly WebView2 view=new WebView2();
    private readonly Panel content=new Panel();
    private readonly Panel errorBar=new Panel();
    private readonly Label errorText=new Label();
    private readonly ToolTip tips=new ToolTip();
    private readonly Dictionary<string,RailButton> buttons=new Dictionary<string,RailButton>();
    private readonly string profile=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Yanfolio","Browser");
    private Uri endpoint;
    private RailButton connection;
    private string ConfigFile {get{return Path.Combine(profile,"service.txt");}}
    private static readonly Color Night=Color.FromArgb(17,18,30);
    [DllImport("dwmapi.dll")] private static extern int DwmSetWindowAttribute(IntPtr handle,int attribute,ref int value,int size);

    internal Workspace(){
        Text="砚稿 · Yanfolio";Width=1410;Height=920;MinimumSize=new Size(760,540);StartPosition=FormStartPosition.CenterScreen;
        AutoScaleDimensions=new SizeF(96,96);AutoScaleMode=AutoScaleMode.Dpi;Font=new Font("Microsoft YaHei UI",9f);
        Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);BackColor=Color.FromArgb(246,246,251);
        var rail=new Panel(){Dock=DockStyle.Left,Width=82,BackColor=Night};
        var mark=new PictureBox(){Image=Icon.ToBitmap(),SizeMode=PictureBoxSizeMode.Zoom,Width=34,Height=34,Left=24,Top=20,AccessibleName="砚稿"};
        var top=new Panel(){Height=78,Dock=DockStyle.Top,BackColor=Night};top.Controls.Add(mark);
        var routes=new FlowLayoutPanel(){Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,WrapContents=false,BackColor=Night};
        AddRoute(routes,"写作","写作工作台","write","/studio","Ctrl+1");
        AddRoute(routes,"文档","我的云文档","folder","/drive.html","Ctrl+2");
        AddRoute(routes,"账号","个人中心","profile","/profile.html","Ctrl+3");
        AddRoute(routes,"点数","点数钱包","wallet","/wallet.html","Ctrl+4");
        var bottom=new FlowLayoutPanel(){Dock=DockStyle.Bottom,Height=70,BackColor=Night};connection=new RailButton("连接","连接服务器","server");
        connection.Click+=(s,e)=>Configure();bottom.Controls.Add(connection);tips.SetToolTip(connection,"连接运营方服务器");
        rail.Controls.Add(routes);rail.Controls.Add(top);rail.Controls.Add(bottom);
        content.Dock=DockStyle.Fill;view.Dock=DockStyle.Fill;view.DefaultBackgroundColor=Color.FromArgb(246,246,251);
        errorBar.Dock=DockStyle.Bottom;errorBar.Height=44;errorBar.BackColor=Color.FromArgb(244,240,251);errorBar.Visible=false;
        errorText.Dock=DockStyle.Fill;errorText.Padding=new Padding(12,0,0,0);errorText.TextAlign=ContentAlignment.MiddleLeft;
        var retry=new Button(){Text="重试连接",Dock=DockStyle.Right,Width=92,FlatStyle=FlatStyle.Flat,BackColor=Color.White};retry.Click+=(s,e)=>Go("/profile.html");
        errorBar.Controls.Add(errorText);errorBar.Controls.Add(retry);content.Controls.Add(view);content.Controls.Add(errorBar);
        Controls.Add(content);Controls.Add(rail);
        Load+=async (sender,evt)=>{
            try{
                Directory.CreateDirectory(profile);Uri stored;
                endpoint=File.Exists(ConfigFile)&&Valid(File.ReadAllText(ConfigFile).Trim(),out stored)?stored:new Uri(BuildConfig.ServiceUrl);
                tips.SetToolTip(connection,"服务地址   "+endpoint.Authority);
                var env=await CoreWebView2Environment.CreateAsync(null,profile);
                await view.EnsureCoreWebView2Async(env);
                view.CoreWebView2.Settings.UserAgent+=" YanfolioDesktop/2.2";
                view.CoreWebView2.Settings.AreHostObjectsAllowed=false;view.CoreWebView2.Settings.IsWebMessageEnabled=false;
                view.CoreWebView2.NavigationStarting+=(s,e)=>{
                    Uri next;if(!Uri.TryCreate(e.Uri,UriKind.Absolute,out next)){e.Cancel=true;return;}
                    if(next.Scheme=="blob"){Uri inner;if(Uri.TryCreate(e.Uri.Substring(5),UriKind.Absolute,out inner)&&SameHost(inner))return;}
                    if(!SameHost(next)){e.Cancel=true;OpenExternal(next);}
                };
                view.CoreWebView2.NewWindowRequested+=(s,e)=>{e.Handled=true;Uri next;if(Uri.TryCreate(e.Uri,UriKind.Absolute,out next))OpenExternal(next);};
                view.CoreWebView2.SourceChanged+=(s,e)=>SetActive(view.Source);
                view.CoreWebView2.NavigationCompleted+=(s,e)=>{errorBar.Visible=!e.IsSuccess;if(!e.IsSuccess)errorText.Text="无法连接 "+endpoint.Authority+"。请检查服务地址或重试。";SetActive(view.Source);};
                Go("/profile.html");
            }catch(Exception ex){errorBar.Visible=true;errorText.Text="桌面运行环境未就绪。";MessageBox.Show("请检查 WebView2 Evergreen Runtime 和服务地址。\n"+ex.Message,Text);}
        };
    }
    protected override void OnHandleCreated(EventArgs e){base.OnHandleCreated(e);try{int dark=1,bg=0x001e1211,fg=0x00f4f0ef;DwmSetWindowAttribute(Handle,20,ref dark,4);DwmSetWindowAttribute(Handle,35,ref bg,4);DwmSetWindowAttribute(Handle,36,ref fg,4);}catch(DllNotFoundException){}catch(EntryPointNotFoundException){}}
    private void AddRoute(Control panel,string label,string name,string glyph,string path,string shortcut){
        var b=new RailButton(label,name,glyph);b.Click+=(s,e)=>Go(path);buttons[path]=b;panel.Controls.Add(b);tips.SetToolTip(b,name+"   "+shortcut);
    }
    private void SetActive(Uri uri){if(uri==null)return;foreach(var item in buttons){item.Value.Selected=uri.AbsolutePath==item.Key;item.Value.Invalidate();}}
    protected override bool ProcessCmdKey(ref Message msg,Keys keyData){
        if(keyData==(Keys.Control|Keys.Oemcomma)){Configure();return true;}
        var routes=new[]{"/studio","/drive.html","/profile.html","/wallet.html"};
        for(int i=0;i<routes.Length;i++)if(keyData==(Keys.Control|(Keys)((int)Keys.D1+i))){Go(routes[i]);return true;}
        return base.ProcessCmdKey(ref msg,keyData);
    }
    private bool SameHost(Uri uri){return (uri.Scheme=="https"||uri.Scheme=="http")&&uri.GetLeftPart(UriPartial.Authority)==endpoint.GetLeftPart(UriPartial.Authority);}
    private static bool Valid(string value,out Uri uri){return Uri.TryCreate(value,UriKind.Absolute,out uri)&&String.IsNullOrEmpty(uri.UserInfo)&&(uri.Scheme=="https"||(uri.Scheme=="http"&&uri.IsLoopback))&&uri.AbsolutePath=="/"&&String.IsNullOrEmpty(uri.Query)&&String.IsNullOrEmpty(uri.Fragment);}
    private static void OpenExternal(Uri uri){if(uri!=null&&(uri.Scheme=="https"||uri.Scheme=="http"))Process.Start(new ProcessStartInfo(uri.AbsoluteUri){UseShellExecute=true});}
    private void Go(string path){if(view.CoreWebView2!=null&&endpoint!=null)view.CoreWebView2.Navigate(new Uri(endpoint,path).AbsoluteUri);}
    private void Configure(){
        using(var dialog=new Form()){
            dialog.Text="连接服务器 · 砚稿";dialog.Icon=Icon;dialog.ClientSize=new Size(445,189);dialog.StartPosition=FormStartPosition.CenterParent;
            dialog.FormBorderStyle=FormBorderStyle.FixedDialog;dialog.MaximizeBox=false;dialog.MinimizeBox=false;dialog.BackColor=Color.FromArgb(248,248,252);dialog.Font=Font;
            var title=new Label(){Left=22,Top=17,Width=360,Height=29,Font=new Font(Font.FontFamily,13,FontStyle.Bold),Text="服务地址"};
            var note=new Label(){Left=23,Top=52,Width=400,Height=23,Text="输入运营方的 HTTPS 根地址，或本机回环地址。"};
            var box=new TextBox(){Left=23,Top=82,Width=395,Text=endpoint==null?BuildConfig.ServiceUrl:endpoint.AbsoluteUri,AccessibleName="服务地址"};
            var save=new Button(){Left=332,Top=130,Width=86,Height=32,Text="连接",FlatStyle=FlatStyle.Flat,BackColor=Color.FromArgb(89,74,199),ForeColor=Color.White,DialogResult=DialogResult.OK};
            save.FlatAppearance.BorderSize=0;var cancel=new Button(){Left=237,Top=130,Width=85,Height=32,Text="取消",DialogResult=DialogResult.Cancel};
            dialog.Controls.AddRange(new Control[]{title,note,box,save,cancel});dialog.AcceptButton=save;dialog.CancelButton=cancel;
            if(dialog.ShowDialog(this)!=DialogResult.OK)return;Uri next;
            if(!Valid(box.Text.Trim(),out next)){MessageBox.Show("请输入有效的 HTTPS 服务根地址。",Text);return;}
            endpoint=next;Directory.CreateDirectory(profile);File.WriteAllText(ConfigFile,endpoint.AbsoluteUri);tips.SetToolTip(connection,"服务地址   "+endpoint.Authority);Go("/profile.html");
        }
    }
    protected override void Dispose(bool disposing){if(disposing)tips.Dispose();base.Dispose(disposing);}
    [STAThread] static void Main(){Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Workspace());}
}

