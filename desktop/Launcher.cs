using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Windows.Forms;

internal static class Launcher {
    [STAThread] private static void Main(){
        try {
            var self=Assembly.GetExecutingAssembly();
            string hash;
            using(var sha=SHA256.Create())using(var f=File.OpenRead(self.Location))hash=BitConverter.ToString(sha.ComputeHash(f)).Replace("-","").Substring(0,24);
            var dir=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Yanfolio","Desktop",hash);
            Directory.CreateDirectory(dir);
            foreach(var name in self.GetManifestResourceNames()){
                var path=Path.Combine(dir,name);
                using(var stream=self.GetManifestResourceStream(name)){
                    using(var sha=SHA256.Create()){
                        var expected=Convert.ToBase64String(sha.ComputeHash(stream));stream.Position=0;
                        if(File.Exists(path)){using(var file=File.OpenRead(path)){if(expected==Convert.ToBase64String(sha.ComputeHash(file)))continue;}}
                    }
                    var tmp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
                    using(var output=File.Create(tmp))stream.CopyTo(output);
                    try{if(File.Exists(path))File.Replace(tmp,path,null);else File.Move(tmp,path);}
                    catch(IOException){if(!File.Exists(path))throw;}
                    finally{if(File.Exists(tmp))File.Delete(tmp);}
                }
            }
            Process.Start(new ProcessStartInfo(Path.Combine(dir,"Yanfolio.Workspace.exe")){WorkingDirectory=dir,UseShellExecute=false});
        }catch(Exception e){MessageBox.Show(e.Message,"砚稿启动失败");}
    }
}

