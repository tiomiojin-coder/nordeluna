using System;
using System.IO;
using System.IO.Compression;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Security.Cryptography;
using System.Net;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using System.Web.Script.Serialization;

namespace Nordeluna {
static partial class Files {
    public static readonly JavaScriptSerializer Json=new JavaScriptSerializer { MaxJsonLength=16*1024*1024 };
    public static Dictionary<string,object> Parse(string text){return Json.Deserialize<Dictionary<string,object>>(text);}
    public static Dictionary<string,object> Obj(object value){return (Dictionary<string,object>)value;}
    public static string Str(Dictionary<string,object> obj,string key,string fallback=""){return obj.ContainsKey(key)?Convert.ToString(obj[key]):fallback;}
    public static int Num(Dictionary<string,object> obj,string key,int fallback=0){return obj.ContainsKey(key)?Convert.ToInt32(obj[key]):fallback;}
    public static string Hash(string path){using(var sha=SHA256.Create())using(var f=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
    public static string Child(string root,string name){
        if(String.IsNullOrEmpty(name)||name.Contains("\\")||name.Contains(":")||name.StartsWith("/")||name.Split('/').Any(p=>p==".."||p=="."||p.EndsWith(" ")||p.EndsWith(".")))throw new IOException("Caminho inválido");
        string path=Path.GetFullPath(Path.Combine(root,name));if(!path.StartsWith(Path.GetFullPath(root).TrimEnd('\\')+"\\",StringComparison.OrdinalIgnoreCase))throw new IOException("Caminho fora do jogo");return path;
    }
    public static void Write(string file,string text){Directory.CreateDirectory(Path.GetDirectoryName(file));string tmp=file+".tmp";File.WriteAllText(tmp,text,new UTF8Encoding(false));if(File.Exists(file))File.Replace(tmp,file,null);else File.Move(tmp,file);}
    public static void Save(string path,object obj){Write(path,Json.Serialize(obj));}
    public static string Read(string path){return File.ReadAllText(path,Encoding.UTF8);}
    public static string Configure(string text,bool fullscreen,int width){
        if(!new[]{512,1024,1536}.Contains(width))throw new IOException("Resolução inválida");
        text=Regex.Replace(text,@"(?m)^\s*//.*$","");text=Regex.Replace(text,@",\s*([}\]])","$1");
        var data=Parse(text);data["fullscreen"]=fullscreen;data["defScreenW"]=width;data["defScreenH"]=width*3/4;return Json.Serialize(data);
    }
    public static byte[] Hex(string text){return Enumerable.Range(0,text.Length/2).Select(i=>Convert.ToByte(text.Substring(i*2,2),16)).ToArray();}
    public static Dictionary<string,object> Verify(string envelope){
        var data=VerifySigned(envelope,180000);if(Num(data,"schema")!=1)throw new IOException("Atualize o launcher");return data;
    }
    public static Dictionary<string,object> VerifySigned(string envelope,int limit){
        var wrapper=Parse(envelope);string raw=Str(wrapper,"manifest"),signature=Str(wrapper,"signature");if(raw.Length>limit||!Regex.IsMatch(signature,"\\A[0-9a-f]{512}\\z"))throw new IOException("Documento assinado inválido");
        using(var rsa=new RSACryptoServiceProvider()){
            rsa.ImportParameters(new RSAParameters { Modulus=Hex(LauncherKeys.Modulus),Exponent=new byte[]{1,0,1} });
            if(!rsa.VerifyData(Encoding.UTF8.GetBytes(raw),CryptoConfig.MapNameToOID("SHA256"),Hex(signature)))throw new IOException("Assinatura da atualização inválida");
        }
        return Parse(raw);
    }
    public static HttpWebResponse Open(string url,long start=-1,long length=-1){
        for(int i=0;i<6;i++){
            Uri uri=new Uri(url);if(uri.Scheme!="https")throw new IOException("Use um endereço HTTPS");
            var req=(HttpWebRequest)WebRequest.Create(uri);req.AllowAutoRedirect=false;req.UserAgent="Nordeluna-Launcher/1.1";req.Timeout=15000;req.ReadWriteTimeout=30000;
            if(start>=0){if(length<1)throw new IOException("Intervalo inválido");req.AddRange(start,start+length-1);}
            var response=(HttpWebResponse)req.GetResponse();int status=(int)response.StatusCode;
            if(status>=300&&status<400){url=new Uri(uri,response.Headers["Location"]).AbsoluteUri;response.Dispose();continue;}
            if(start>=0){string range="bytes "+start+"-"+(start+length-1)+"/";if(status!=206||!(response.Headers["Content-Range"]??"").StartsWith(range,StringComparison.Ordinal)){response.Dispose();throw new IOException("O servidor não permite reparação parcial. Nenhum pacote completo foi baixado.");}}
            else if(status!=200){response.Dispose();throw new IOException("Servidor respondeu HTTP "+status);}return response;
        }throw new IOException("Muitos redirecionamentos");
    }
    public static string Catalog(string url,int limit=262144){using(var response=Open(url))using(var input=response.GetResponseStream())using(var output=new MemoryStream()){
        byte[] b=new byte[8192];int n;while((n=input.Read(b,0,b.Length))>0){if(output.Length+n>limit)throw new IOException("Documento grande demais");output.Write(b,0,n);}return Encoding.UTF8.GetString(output.ToArray());}}
    public static string Download(Dictionary<string,object> row,string directory,Action<string,int> progress){
        Directory.CreateDirectory(directory);long size=Convert.ToInt64(row["size"]);string expected=Str(row,"sha256");if(size<1||size>3L*1024*1024*1024||!Regex.IsMatch(expected,"\\A[0-9a-f]{64}\\z"))throw new IOException("Pacote inválido");
        string path=Path.Combine(directory,"client.zip"),tmp=path+".part";
        try{
            using(var response=Open(Str(row,"url")))using(var input=response.GetResponseStream())using(var output=File.Create(tmp)){
                long count=0;int n,last=-1;byte[] b=new byte[131072];while((n=input.Read(b,0,b.Length))>0){count+=n;if(count>size)throw new IOException("Download maior que o esperado");output.Write(b,0,n);int p=(int)(count*100/size);if(p!=last){progress("Baixando atualização",p);last=p;}}if(count!=size)throw new IOException("Download incompleto");output.Flush(true);
            }
            if(Hash(tmp)!=expected)throw new IOException("Download corrompido");if(File.Exists(path))File.Delete(path);File.Move(tmp,path);return path;
        }catch{if(File.Exists(tmp))File.Delete(tmp);throw;}
    }
    public static bool RuntimePath(string name){
        if(name.StartsWith(".")||name.Split('/').Any(p=>p.StartsWith(".")))return false;
        string[] folders={"Data/","Graphics/","Audio/","Movies/","Fonts/","Plugins/"};
        return folders.Any(p=>name.StartsWith(p,StringComparison.Ordinal))||new[]{"Game.exe","Game.ini","mkxp.json","RGSS104E.dll","x64-msvcrt-ruby310.dll","zlib1.dll","soundfont.sf2","pc-package.json","achievements.dat"}.Contains(name);
    }
    public static void EnsureClosed(string game){
        string exe=Path.GetFullPath(Path.Combine(game,"Game.exe"));foreach(var process in Process.GetProcessesByName("Game"))using(process){string path=null;try{path=process.MainModule.FileName;}catch{}if(String.Equals(path,exe,StringComparison.OrdinalIgnoreCase))throw new IOException("Feche o jogo antes de continuar");}
    }
    public static void Recover(string game){
        string journal=Path.Combine(game,".launcher-update-journal.json");if(!File.Exists(journal))return;
        var data=Parse(Read(journal));string rollback=Child(game,Str(data,"rollback"));
        foreach(object obj in (System.Collections.IEnumerable)data["files"]){var row=Obj(obj);string name=Str(row,"path");if(!RuntimePath(name))throw new IOException("Registro de recuperação inválido");if(Convert.ToBoolean(row["existed"])&&row.ContainsKey("sha256")&&Hash(Child(rollback,name))!=Str(row,"sha256"))throw new IOException("Backup de recuperação corrompido");}
        foreach(object obj in (System.Collections.IEnumerable)data["files"]){var row=Obj(obj);string name=Str(row,"path");if(!RuntimePath(name))throw new IOException("Registro de recuperação inválido");string target=Child(game,name),old=Child(rollback,name);
            if(Convert.ToBoolean(row["existed"])){if(!File.Exists(old))throw new IOException("Backup de recuperação incompleto");Directory.CreateDirectory(Path.GetDirectoryName(target));File.Copy(old,target,true);}else if(File.Exists(target))File.Delete(target);
        }
        string oldUpdates=Path.Combine(rollback,"content-state"),updates=Path.Combine(game,".nordeluna-updates");if(Directory.Exists(oldUpdates)&&!Directory.Exists(updates))Directory.Move(oldUpdates,updates);
        File.Delete(journal);
    }
    public static void Apply(string archive,string game,Action<string,int> progress){
        EnsureClosed(game);Directory.CreateDirectory(game);Recover(game);string id=Guid.NewGuid().ToString("N"),stage=Path.Combine(game,".launcher/stage-"+id),rollback=Path.Combine(game,".launcher/rollback-"+id);Directory.CreateDirectory(stage);Directory.CreateDirectory(rollback);
        var paths=new HashSet<string>(StringComparer.OrdinalIgnoreCase);long total=0;
        using(var zip=ZipFile.OpenRead(archive)){
            if(zip.Entries.Count>60000)throw new IOException("Pacote grande demais");
            foreach(var entry in zip.Entries){if(String.IsNullOrEmpty(entry.Name))continue;string name=entry.FullName;if(!RuntimePath(name)||!paths.Add(name)||(entry.ExternalAttributes&0x400)!=0)throw new IOException("Arquivo não permitido: "+name);
                total+=entry.Length;if(total>4L*1024*1024*1024)throw new IOException("Pacote expandido grande demais");string target=Child(stage,name);Directory.CreateDirectory(Path.GetDirectoryName(target));entry.ExtractToFile(target);}
        }
        if(!File.Exists(Path.Combine(stage,"Game.exe"))||!File.Exists(Path.Combine(stage,"Data/PluginScripts.rxdata")))throw new IOException("Pacote não contém o jogo completo");
        var remove=new HashSet<string>(StringComparer.OrdinalIgnoreCase);string oldManifest=Path.Combine(game,"pc-package.json");
        if(File.Exists(oldManifest)){var m=Parse(Read(oldManifest));foreach(string name in Obj(m["files"]).Keys)if(RuntimePath(name)&&!paths.Contains(name)){Child(game,name);remove.Add(name);}}
        var rows=new List<Dictionary<string,object>>();foreach(string name in paths.Concat(remove)){
            string target=Child(game,name);bool exists=File.Exists(target);if(exists){string old=Child(rollback,name);Directory.CreateDirectory(Path.GetDirectoryName(old));File.Copy(target,old);}
            rows.Add(new Dictionary<string,object>{{"path",name},{"existed",exists}});
        }
        string journal=Path.Combine(game,".launcher-update-journal.json");Save(journal,new { rollback=".launcher/rollback-"+id,files=rows });
        try{
            string updates=Path.Combine(game,".nordeluna-updates");if(Directory.Exists(updates))Directory.Move(updates,Path.Combine(rollback,"content-state"));
            int done=0;foreach(string name in paths){string target=Child(game,name);Directory.CreateDirectory(Path.GetDirectoryName(target));File.Copy(Child(stage,name),target,true);if(++done%200==0)progress("Aplicando arquivos",done*100/paths.Count);}
            foreach(string name in remove){string target=Child(game,name);if(File.Exists(target))File.Delete(target);}File.Delete(journal);
            // Keep one full-game recovery copy. Save snapshots have their own five-version history.
            PruneRollback(game,rollback);
        }catch{Recover(game);throw;}
        finally{if(Directory.Exists(stage))Directory.Delete(stage,true);}
    }
    public static IEnumerable<string> Saves(string root){return Directory.Exists(root)?Directory.GetFiles(root,"*",SearchOption.AllDirectories).Where(p=>Regex.IsMatch(p,"\\.(rxdata|rvdata2?|preview|dat|json)$",RegexOptions.IgnoreCase)):Enumerable.Empty<string>();}
    public static string Backup(string saves,string directory,string channel){
        string[] files=Saves(saves).ToArray();if(files.Length==0)return null;Directory.CreateDirectory(directory);string path=Path.Combine(directory,"save-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fff")+".zip"),temp=path+".tmp";
        var hashes=new SortedDictionary<string,string>(StringComparer.Ordinal);foreach(string f in files)hashes[f.Substring(saves.Length).TrimStart('\\').Replace('\\','/')]=Hash(f);
        string signature=Json.Serialize(hashes),latest=Directory.GetFiles(directory,"save-*.zip").OrderByDescending(p=>p).FirstOrDefault();
        if(latest!=null)try{using(var zip=ZipFile.OpenRead(latest))using(var input=new StreamReader(zip.GetEntry("backup-info.json").Open()))if(Str(Parse(input.ReadToEnd()),"snapshot")==signature)return latest;}catch{}
        try{using(var zip=ZipFile.Open(temp,ZipArchiveMode.Create)){
            string info=Path.Combine(saves,"launcher-save-info.json");var entry=zip.CreateEntry("backup-info.json");using(var writer=new StreamWriter(entry.Open(),new UTF8Encoding(false)))writer.Write(Json.Serialize(new{ date=DateTime.Now.ToString("s"),channel=channel,save=File.Exists(info)?Parse(Read(info)):null,hashes=hashes,snapshot=signature }));
            foreach(string f in files){if(new FileInfo(f).Length>64*1024*1024)throw new IOException("Save grande demais");zip.CreateEntryFromFile(f,"saves/"+f.Substring(saves.Length).TrimStart('\\').Replace('\\','/'));}
        }File.Move(temp,path);}catch{if(File.Exists(temp))File.Delete(temp);throw;}
        foreach(string old in Directory.GetFiles(directory,"save-*.zip").OrderByDescending(p=>p).Skip(5))File.Delete(old);return path;
    }
    public static string DescribeBackup(string path){using(var zip=ZipFile.OpenRead(path))using(var input=new StreamReader(zip.GetEntry("backup-info.json").Open())){
        var meta=Parse(input.ReadToEnd());int seconds=meta.ContainsKey("save")&&meta["save"]!=null?Num(Obj(meta["save"]),"play_seconds"):0;return Str(meta,"date")+" • "+seconds/3600+"h "+(seconds/60)%60+"min";}}
    public static void Restore(string archive,string saves,string backups,string channel){
        // Do not delete the selected ZIP while rotating the history.
        string temporary=Path.Combine(backups,"restore-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(temporary);
        var targets=new List<string>();var original=new Dictionary<string,byte[]>();var added=new List<string>();
        try{
            using(var zip=ZipFile.OpenRead(archive)){long size=0;var seen=new HashSet<string>(StringComparer.OrdinalIgnoreCase);Dictionary<string,object> hashes;using(var input=new StreamReader(zip.GetEntry("backup-info.json").Open()))hashes=Obj(Parse(input.ReadToEnd())["hashes"]);foreach(var entry in zip.Entries){if(entry.FullName=="backup-info.json"||String.IsNullOrEmpty(entry.Name))continue;
                if(!entry.FullName.StartsWith("saves/")||!seen.Add(entry.FullName)||++size>1000)throw new IOException("Backup inválido");string name=entry.FullName.Substring(6);if(!Regex.IsMatch(name,"\\.(rxdata|rvdata2?|preview|dat|json)$",RegexOptions.IgnoreCase)||entry.Length>64*1024*1024)throw new IOException("Arquivo não permitido no backup");string target=Child(temporary,name);Directory.CreateDirectory(Path.GetDirectoryName(target));entry.ExtractToFile(target);if(!hashes.ContainsKey(name)||Hash(target)!=Str(hashes,name))throw new IOException("Backup corrompido");targets.Add(name);}
                if(zip.Entries.Sum(e=>e.Length)>128L*1024*1024)throw new IOException("Backup grande demais");
            }
            if(targets.Count==0)throw new IOException("Backup vazio");Backup(saves,backups,channel);
            try{foreach(string name in targets){string target=Child(saves,name);if(File.Exists(target))original[target]=File.ReadAllBytes(target);else added.Add(target);Directory.CreateDirectory(Path.GetDirectoryName(target));File.Copy(Child(temporary,name),target,true);}}
            catch{foreach(var row in original)File.WriteAllBytes(row.Key,row.Value);foreach(string path in added)if(File.Exists(path))File.Delete(path);throw;}
        }finally{Directory.Delete(temporary,true);}
    }
}

static class LauncherStyle {
    public static readonly Color Background=Color.FromArgb(11,17,29),Card=Color.FromArgb(20,31,47),Ink=Color.FromArgb(235,242,250),Muted=Color.FromArgb(159,178,198),Accent=Color.FromArgb(100,224,220),Gold=Color.FromArgb(232,199,128);
    public static GraphicsPath Shape(Rectangle r,int radius){var p=new GraphicsPath();int d=Math.Min(radius*2,Math.Min(r.Width,r.Height));p.AddArc(r.X,r.Y,d,d,180,90);p.AddArc(r.Right-d,r.Y,d,d,270,90);p.AddArc(r.Right-d,r.Bottom-d,d,d,0,90);p.AddArc(r.X,r.Bottom-d,d,d,90,90);p.CloseFigure();return p;}
}
sealed class LauncherCard : Panel {
    public LauncherCard(){DoubleBuffered=true;BackColor=LauncherStyle.Card;Padding=new Padding(20);}
    protected override void OnPaint(PaintEventArgs e){base.OnPaint(e);e.Graphics.SmoothingMode=SmoothingMode.AntiAlias;using(var p=LauncherStyle.Shape(new Rectangle(0,0,Width-1,Height-1),16))using(var pen=new Pen(Color.FromArgb(43,62,81)))e.Graphics.DrawPath(pen,p);}
}
sealed class LauncherAction : Button {
    public bool Primary,Full;bool hover;
    public LauncherAction(){FlatStyle=FlatStyle.Flat;FlatAppearance.BorderSize=0;Cursor=Cursors.Hand;DoubleBuffered=true;UseVisualStyleBackColor=false;}
    protected override void OnMouseEnter(EventArgs e){hover=true;Invalidate();base.OnMouseEnter(e);}
    protected override void OnMouseLeave(EventArgs e){hover=false;Invalidate();base.OnMouseLeave(e);}
    protected override void OnGotFocus(EventArgs e){base.OnGotFocus(e);Invalidate();}
    protected override void OnLostFocus(EventArgs e){base.OnLostFocus(e);Invalidate();}
    protected override void OnPaint(PaintEventArgs e){
        e.Graphics.Clear(Parent.BackColor);e.Graphics.SmoothingMode=SmoothingMode.AntiAlias;
        var r=new Rectangle(1,1,Width-3,Height-3);Color fill=Primary?LauncherStyle.Accent:(hover?Color.FromArgb(38,61,78):Color.FromArgb(27,43,61));
        using(var p=LauncherStyle.Shape(r,12))using(var brush=new SolidBrush(Enabled?fill:Color.FromArgb(31,42,54)))using(var pen=new Pen(Focused?LauncherStyle.Gold:Color.FromArgb(49,71,89),Focused?2:1)){e.Graphics.FillPath(brush,p);e.Graphics.DrawPath(pen,p);}
        string[] lines=Text.Split('\n');Color ink=Enabled?(Primary?LauncherStyle.Background:LauncherStyle.Ink):LauncherStyle.Muted;float scale=e.Graphics.DpiX/96f;int pad=(int)(16*scale);
        using(var title=new Font(Font.FontFamily,Primary?14:10.5f,FontStyle.Bold))TextRenderer.DrawText(e.Graphics,lines[0],title,new Rectangle(pad,(int)((lines.Length>1?12:10)*scale),Width-pad*2,(int)(25*scale)),ink,TextFormatFlags.Left|TextFormatFlags.VerticalCenter|TextFormatFlags.EndEllipsis|TextFormatFlags.NoPrefix);
        if(lines.Length>1)using(var small=new Font(Font.FontFamily,9))TextRenderer.DrawText(e.Graphics,lines[1],small,new Rectangle(pad,(int)(37*scale),Width-pad*2,(int)(19*scale)),Primary?Color.FromArgb(25,78,85):LauncherStyle.Muted,TextFormatFlags.Left|TextFormatFlags.EndEllipsis|TextFormatFlags.NoPrefix);
    }
}
sealed class LauncherProgress : ProgressBar {
    public LauncherProgress(){SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);}
    protected override void OnPaint(PaintEventArgs e){e.Graphics.Clear(Color.FromArgb(32,51,69));if(Value>0)using(var brush=new SolidBrush(LauncherStyle.Accent))e.Graphics.FillRectangle(brush,0,0,Width*Value/100,Height);}
}
partial class Launcher : Form {
    readonly string root=AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
    readonly string home=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Pokemon Nordeluna");
    const string DefaultCatalog="https://raw.githubusercontent.com/tiomiojin-coder/nordeluna/main/public/launcher/releases.json";
    Dictionary<string,object> preferences;ComboBox channel;Label status;TextBox news;ProgressBar progress;FlowLayoutPanel buttons;bool busy,configureOnly;Process game;
    Label newsVersion;string fullNews="As novidades aparecem ao consultar uma versão publicada.";
    string Channel {get{return channel.SelectedIndex==1?"testers":"stable";}}
    string Data {get{return Path.Combine(home,"player-data",Channel);}}
    string BackupDir {get{return Path.Combine(home,"player-backups",Channel);}}
    string GameRoot {get{return Channel=="stable"?root:Path.Combine(home,"channels/testers/game");}}
    string SettingsPath {get{return Path.Combine(home,"launcher.json");}}
    public Launcher(){
        Text="Pokémon Nordeluna";ClientSize=new Size(Math.Min(960,Screen.PrimaryScreen.WorkingArea.Width-80),Math.Min(760,Screen.PrimaryScreen.WorkingArea.Height-80));MinimumSize=new Size(820,680);AutoScaleMode=AutoScaleMode.Dpi;StartPosition=FormStartPosition.CenterScreen;BackColor=LauncherStyle.Background;ForeColor=LauncherStyle.Ink;Font=new Font("Segoe UI",10);DoubleBuffered=true;
        try{Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);}catch{}
        try{preferences=File.Exists(SettingsPath)?Files.Parse(Files.Read(SettingsPath)):new Dictionary<string,object>();}catch{preferences=new Dictionary<string,object>();}
        var layout=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(24),ColumnCount=2,RowCount=3};layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,54));layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,46));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,112));layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,88));Controls.Add(layout);
        var header=new Panel{Dock=DockStyle.Fill};layout.Controls.Add(header,0,0);layout.SetColumnSpan(header,2);
        var logo=new PictureBox{Location=new Point(0,8),Size=new Size(80,80),SizeMode=PictureBoxSizeMode.Zoom};using(var asset=typeof(Launcher).Assembly.GetManifestResourceStream("Nordeluna.Brand")){if(asset!=null)using(var image=Image.FromStream(asset))logo.Image=new Bitmap(image);else if(Icon!=null)logo.Image=Icon.ToBitmap();}logo.Disposed+=(s,e)=>{if(logo.Image!=null)logo.Image.Dispose();};header.Controls.Add(logo);
        header.Controls.Add(new Label{Text="POKÉMON",Location=new Point(98,8),Size=new Size(280,22),ForeColor=LauncherStyle.Gold,Font=new Font(Font.FontFamily,10,FontStyle.Bold)});
        header.Controls.Add(new Label{Text="NORDELUNA",Location=new Point(94,27),Size=new Size(420,42),Font=new Font(Font.FontFamily,27,FontStyle.Bold)});
        header.Controls.Add(new Label{Text="Sua próxima aventura começa aqui.",Location=new Point(98,74),Size=new Size(440,24),ForeColor=LauncherStyle.Muted});
        var actionCard=new LauncherCard{Dock=DockStyle.Fill,Margin=new Padding(0,8,12,8)};layout.Controls.Add(actionCard,0,1);
        var actionLayout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=3};actionLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,26));actionLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,44));actionLayout.RowStyles.Add(new RowStyle(SizeType.Percent,100));actionCard.Controls.Add(actionLayout);
        actionLayout.Controls.Add(new Label{Text="CANAL DA AVENTURA",ForeColor=LauncherStyle.Muted,Dock=DockStyle.Fill,Font=new Font(Font.FontFamily,9,FontStyle.Bold)});
        channel=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Dock=DockStyle.Top,FlatStyle=FlatStyle.Flat,BackColor=Color.FromArgb(28,44,61),ForeColor=LauncherStyle.Ink,AccessibleName="Canal do jogo",DrawMode=DrawMode.OwnerDrawFixed,ItemHeight=28};channel.DrawItem+=(s,e)=>{if(e.Index<0)return;using(var brush=new SolidBrush(Color.FromArgb(28,44,61)))e.Graphics.FillRectangle(brush,e.Bounds);TextRenderer.DrawText(e.Graphics,channel.Items[e.Index].ToString(),Font,new Rectangle(e.Bounds.X+8,e.Bounds.Y,e.Bounds.Width-8,e.Bounds.Height),LauncherStyle.Ink,TextFormatFlags.Left|TextFormatFlags.VerticalCenter);e.DrawFocusRectangle();};channel.Items.AddRange(new object[]{"Estável","Testers · saves separados"});channel.SelectedIndex=Files.Str(preferences,"channel")=="testers"?1:0;channel.SelectedIndexChanged+=(s,e)=>{preferences["channel"]=Channel;Files.Save(SettingsPath,preferences);};actionLayout.Controls.Add(channel);
        buttons=new FlowLayoutPanel{Dock=DockStyle.Fill,AutoScroll=true,Padding=new Padding(0),Margin=new Padding(0)};actionLayout.Controls.Add(buttons);
        Button("JOGAR\nContinuar sua aventura",Play,true,true);Button("Atualizar\nConferir novidades e downloads",()=>CheckUpdates(true),false,true);Button("Reparar\nConferir arquivos",RepairInstallation);Button("Backups\nRestaurar progresso",Backups);Button("Configurações\nTela, áudio e controles",Settings);Button("Diagnóstico\nConexão e relatórios",Diagnostics);Button("Acesso de tester\nGerenciar convite",ResetTester,false,true);
        buttons.SizeChanged+=(s,e)=>{foreach(LauncherAction b in buttons.Controls)b.Width=Math.Max(100,b.Full?buttons.ClientSize.Width-22:(buttons.ClientSize.Width-30)/2);};
        var updates=new LauncherCard{Dock=DockStyle.Fill,Margin=new Padding(0,8,0,8)};layout.Controls.Add(updates,1,1);
        var updatesLayout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=5};updatesLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,34));updatesLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,104));updatesLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,30));updatesLayout.RowStyles.Add(new RowStyle(SizeType.Percent,100));updatesLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,46));updates.Controls.Add(updatesLayout);
        updatesLayout.Controls.Add(new Label{Text="Novidades de Nordeluna",Dock=DockStyle.Fill,ForeColor=LauncherStyle.Accent,Font=new Font(Font.FontFamily,16,FontStyle.Bold)});
        var feature=new PictureBox{Dock=DockStyle.Fill,SizeMode=PictureBoxSizeMode.Zoom,BackColor=LauncherStyle.Background,AccessibleName="Pokémon Nordeluna"};if(logo.Image!=null)feature.Image=new Bitmap(logo.Image);feature.Disposed+=(s,e)=>{if(feature.Image!=null)feature.Image.Dispose();};updatesLayout.Controls.Add(feature);
        newsVersion=new Label{Text="NOVIDADES",Dock=DockStyle.Fill,ForeColor=LauncherStyle.Gold};updatesLayout.Controls.Add(newsVersion);
        news=new TextBox{Multiline=true,ReadOnly=true,BorderStyle=BorderStyle.None,BackColor=LauncherStyle.Card,ForeColor=LauncherStyle.Ink,Dock=DockStyle.Fill,ScrollBars=ScrollBars.None,AccessibleName="Novidades do jogo",Text="Bem-vindo a Nordeluna.\r\n\r\nSuas novidades aparecem aqui.\r\nSem internet? O canal estável permite continuar sua aventura offline."};news.SizeChanged+=(s,e)=>AdjustNewsScroll();news.TextChanged+=(s,e)=>AdjustNewsScroll();updatesLayout.Controls.Add(news);
        var readMore=new LauncherAction{Text="Ler todas as novidades",Dock=DockStyle.Fill,Height=42,Font=Font,AccessibleName="Ler todas as novidades"};readMore.Click+=(s,e)=>ShowNews();updatesLayout.Controls.Add(readMore);
        var footer=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=2,Padding=new Padding(2,12,2,4)};footer.RowStyles.Add(new RowStyle(SizeType.Percent,100));footer.RowStyles.Add(new RowStyle(SizeType.Absolute,8));layout.Controls.Add(footer,0,2);layout.SetColumnSpan(footer,2);
        status=new Label{Dock=DockStyle.Fill,Text="Pronto para jogar • seus saves ficam separados por canal",ForeColor=LauncherStyle.Muted,AutoEllipsis=true};footer.Controls.Add(status);progress=new LauncherProgress{Dock=DockStyle.Fill,AccessibleName="Progresso da operação"};footer.Controls.Add(progress);
        FormClosing+=(s,e)=>{if(busy||game!=null&&!game.HasExited){e.Cancel=true;MessageBox.Show("Finalize o jogo ou a atualização antes de fechar o launcher.");}};
        Shown+=async(s,e)=>{try{Files.Recover(root);string tester=Path.Combine(home,"channels/testers/game");if(Directory.Exists(tester))Files.Recover(tester);}catch(Exception ex){MessageBox.Show("Recuperação pendente: "+ex.Message);buttons.Enabled=false;return;}
            string interrupted=Path.Combine(home,"session.json");if(File.Exists(interrupted)){Files.Save(Path.Combine(home,"last-crash.json"),new{ reason="Sessão anterior não terminou normalmente",time=DateTime.UtcNow.ToString("o") });File.Delete(interrupted);}
            if(File.Exists(Path.Combine(home,"last-crash.json"))&&MessageBox.Show("O jogo foi interrompido anteriormente. Exportar diagnóstico sem saves ou dados de login?","Diagnóstico",MessageBoxButtons.YesNo)==DialogResult.Yes)await Diagnostics();await CheckUpdates(false);
        };
    }
    void Button(string text,Func<Task> action,bool primary=false,bool full=false){var button=new LauncherAction{Text=text,Primary=primary,Full=full,Width=full?400:190,Height=66,Margin=new Padding(4),Font=Font,AccessibleName=text.Replace('\n',' ')};button.Click+=async(s,e)=>await action();buttons.Controls.Add(button);}
    void AdjustNewsScroll(){if(news.ClientSize.Width<24||news.ClientSize.Height<24)return;int height=TextRenderer.MeasureText(news.Text,news.Font,new Size(news.ClientSize.Width-20,int.MaxValue),TextFormatFlags.WordBreak|TextFormatFlags.TextBoxControl).Height;var bar=height>news.ClientSize.Height?ScrollBars.Vertical:ScrollBars.None;if(news.ScrollBars!=bar)news.ScrollBars=bar;}
    void SetNews(string version,string notes){fullNews=notes;newsVersion.Text="VERSÃO "+version;var lines=notes.Split(new[]{'\r','\n'},StringSplitOptions.RemoveEmptyEntries).Select(x=>x.Trim().TrimStart('-','*','•',' ')).Where(x=>x.Length>0).Take(3);news.Text=String.Join("\r\n\r\n",lines.Select(x=>"• "+x));}
    void ShowNews(){using(var dialog=new Form{Text=newsVersion.Text+" — novidades",Size=new Size(620,480),StartPosition=FormStartPosition.CenterParent,BackColor=LauncherStyle.Card,ForeColor=LauncherStyle.Ink,Font=Font}){dialog.Controls.Add(new TextBox{Multiline=true,ReadOnly=true,Text=fullNews,Dock=DockStyle.Fill,ScrollBars=ScrollBars.Vertical,BackColor=LauncherStyle.Card,ForeColor=LauncherStyle.Ink,BorderStyle=BorderStyle.None});dialog.ShowDialog(this);}}
    async Task Work(Func<Task> action){if(busy)return;busy=true;buttons.Enabled=false;channel.Enabled=false;try{await action();}catch(Exception ex){status.Text="Não foi possível concluir: "+ex.Message;}finally{busy=false;buttons.Enabled=true;channel.Enabled=true;}}
    void Progress(string text,int percent){BeginInvoke((Action)(()=>{status.Text=text+" • "+percent+"%";progress.Value=Math.Max(0,Math.Min(100,percent));progress.Invalidate();}));}
    async Task CheckUpdates(bool interactive){string requestedChannel=Channel;Func<Task> operation=async()=>{
        status.Text="Consultando novidades...";var catalog=await ChannelCatalog(interactive);
        if(IsDisposed||(!interactive&&busy)||requestedChannel!=Channel)return;
        var channels=Files.Obj(catalog["channels"]);if(!channels.ContainsKey(Channel))throw new IOException("Este canal ainda não tem uma versão publicada");var selected=Files.Obj(channels[Channel]);if(!selected.ContainsKey("windows"))throw new IOException("Nenhuma versão Windows neste canal");var row=Files.Obj(selected["windows"]);
        string local=Path.Combine(GameRoot,"installed-client.json");int code=File.Exists(local)?Files.Num(Files.Parse(Files.Read(local)),"code"):LauncherKeys.Code;
        string notes=Files.Str(row,"notes","Sem notas de versão");if(selected.ContainsKey("android")&&Files.Str(Files.Obj(selected["android"]),"compatibility")!=Files.Str(row,"compatibility"))notes+="\r\nAtenção: PC e Android publicados possuem versões online diferentes.";SetNews(Files.Str(row,"version"),notes);
        bool newer=Files.Num(row,"code")>code||!File.Exists(Path.Combine(GameRoot,"Game.exe"));status.Text=newer?"Atualização disponível: "+Files.Str(row,"version"):"Jogo atualizado";
        if(interactive&&(newer||Channel=="testers")&&MessageBox.Show((newer?"Baixar e aplicar a versão ":"Reinstalar a versão de testes ")+Files.Str(row,"version")+"? O jogo deve permanecer fechado.","Atualização completa",MessageBoxButtons.YesNo)==DialogResult.Yes){string target=GameRoot,data=Data,backups=BackupDir,ch=Channel;await Task.Run(()=>{Files.Backup(data,backups,ch);string zip=DownloadChannel(row,Path.Combine(home,"downloads",ch));if(ch=="testers")TesterAccess.Call(new Dictionary<string,object>{{"action","tester_access"},{"tester",testerCredentials}});Files.Apply(zip,target,Progress);Files.Save(Path.Combine(target,"installed-client.json"),row);});status.Text="Atualização concluída. Pode jogar.";}
    };if(interactive)await Work(operation);else try{await operation();}catch{if(!IsDisposed&&!busy)status.Text="Sem novidades disponíveis agora. Você pode jogar offline.";}}
    void Migrate(){if(Files.Saves(Path.Combine(home,"player-data/stable")).Any())return;string target=Path.Combine(home,"player-data/stable");
        foreach(string source in new[]{Path.Combine(root,"Saves"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),"Pokemon Nordeluna/Saves"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),"Pokemon Essentials v21.1/Saves")})foreach(string file in Files.Saves(source)){string to=Files.Child(target,file.Substring(source.Length).TrimStart('\\').Replace('\\','/'));Directory.CreateDirectory(Path.GetDirectoryName(to));if(!File.Exists(to))File.Copy(file,to);}}
    async Task Play(){await Work(async()=>{
        string target=GameRoot,data=Data,ch=Channel,backups=BackupDir;Files.EnsureClosed(target);Migrate();
        if(ch=="testers"){
            var approved=await ChannelCatalog(true);var approvedRow=Files.Obj(Files.Obj(Files.Obj(approved["channels"])["testers"])["windows"]);
            string installed=Path.Combine(target,"installed-client.json");if(!File.Exists(installed)||Files.Num(Files.Parse(Files.Read(installed)),"code")!=Files.Num(approvedRow,"code"))throw new IOException("Use Atualizar para instalar a versão de testes autorizada.");
        }
        if(!File.Exists(Path.Combine(target,"Game.exe"))){status.Text="Use Atualizar para instalar o jogo neste canal.";return;}
        await Task.Run(()=>Files.Backup(data,backups,ch));Directory.CreateDirectory(data);
        Files.Save(Path.Combine(target,".nordeluna-launcher.json"),new{ channel=ch,save_root=data,volume=Files.Num(preferences,"volume",80),settings_only=configureOnly,tester=ch=="testers"?testerCredentials:null });
        string mkxp=Path.Combine(target,"mkxp.json");if(File.Exists(mkxp))Files.Write(mkxp,Files.Configure(Files.Read(mkxp),Files.Str(preferences,"fullscreen")=="True",Files.Num(preferences,"width",1024)));
        Files.Save(Path.Combine(home,"session.json"),new{ started=DateTime.UtcNow.ToString("o"),channel=ch });
        game=Process.Start(new ProcessStartInfo(Path.Combine(target,"Game.exe")){WorkingDirectory=target,UseShellExecute=false});status.Text="Jogo em execução • finalize-o para atualizar ou restaurar saves.";
        await Task.Run(()=>game.WaitForExit());int exit=game.ExitCode;game.Dispose();game=null;File.Delete(Path.Combine(home,"session.json"));await Task.Run(()=>Files.Backup(data,backups,ch));
        if(exit!=0){Files.Save(Path.Combine(home,"last-crash.json"),new{ exit_code=exit,time=DateTime.UtcNow.ToString("o"),channel=ch });status.Text="O jogo foi interrompido. O diagnóstico está disponível.";}else status.Text="Jogo encerrado. Backup salvo.";
    });}
    Task Backups(){try{Files.EnsureClosed(GameRoot);}catch(Exception error){status.Text=error.Message;return Task.CompletedTask;}string dir=BackupDir;string[] paths=Directory.Exists(dir)?Directory.GetFiles(dir,"save-*.zip").OrderByDescending(p=>p).ToArray():new string[0];if(paths.Length==0){MessageBox.Show("Os últimos cinco backups aparecerão aqui após jogar.");return Task.CompletedTask;}
        using(var dialog=new Form{Text="Restaurar backup • "+Channel,Size=new Size(620,350),StartPosition=FormStartPosition.CenterParent}){var list=new ListBox{Dock=DockStyle.Fill};foreach(string p in paths)list.Items.Add(Files.DescribeBackup(p));dialog.Controls.Add(list);var restore=new Button{Dock=DockStyle.Bottom,Text="Restaurar selecionado",Height=44};dialog.Controls.Add(restore);restore.Click+=async(s,e)=>{int i=list.SelectedIndex;if(i<0)return;if(MessageBox.Show("O save atual será copiado antes de restaurar. Continuar?","Backup",MessageBoxButtons.YesNo)!=DialogResult.Yes)return;dialog.Close();await Work(async()=>{await Task.Run(()=>Files.Restore(paths[i],Data,BackupDir,Channel));status.Text="Save restaurado.";});};dialog.ShowDialog(this);}return Task.CompletedTask;}
    Task Settings(){using(var dialog=new Form{Text="Antes de jogar",Size=new Size(600,400),StartPosition=FormStartPosition.CenterParent}){
        var panel=new FlowLayoutPanel{Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,Padding=new Padding(20),WrapContents=false};dialog.Controls.Add(panel);
        var resolution=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Width=300};resolution.Items.AddRange(new object[]{"512 × 384","1024 × 768","1536 × 1152"});resolution.SelectedIndex=Math.Max(0,Array.IndexOf(new[]{512,1024,1536},Files.Num(preferences,"width",1024)));panel.Controls.Add(resolution);
        var full=new CheckBox{Text="Tela cheia",Checked=Files.Str(preferences,"fullscreen")=="True",AutoSize=true};panel.Controls.Add(full);panel.Controls.Add(new Label{Text="Volume do jogo",AutoSize=true});var volume=new TrackBar{Minimum=0,Maximum=100,Value=Files.Num(preferences,"volume",80),Width=450};panel.Controls.Add(volume);
        panel.Controls.Add(new Label{Text="Controle USB/Bluetooth: reconhecimento automático.\nPressione F1 no jogo para configurar botões e teclado.",AutoSize=true});
        var controls=new Button{Text="Configurar teclado e controle",AutoSize=true};panel.Controls.Add(controls);controls.Click+=async(s,e)=>{dialog.Close();configureOnly=true;await Play();configureOnly=false;};
        var catalog=new TextBox{Text=Files.Str(preferences,"catalog",DefaultCatalog),Width=520};panel.Controls.Add(new Label{Text="Catálogo HTTPS de atualizações",AutoSize=true});panel.Controls.Add(catalog);
        var save=new Button{Text="Salvar",AutoSize=true};panel.Controls.Add(save);save.Click+=(s,e)=>{if(!catalog.Text.StartsWith("https://")){MessageBox.Show("Use HTTPS.");return;}preferences["volume"]=volume.Value;preferences["width"]=new[]{512,1024,1536}[resolution.SelectedIndex];preferences["fullscreen"]=full.Checked;preferences["catalog"]=catalog.Text.Trim();Files.Save(SettingsPath,preferences);dialog.Close();};dialog.ShowDialog(this);
    }return Task.CompletedTask;}
    Task Diagnostics(){using(var save=new SaveFileDialog{Title="Salvar diagnóstico sem saves ou dados de login",Filter="Relatório ZIP|*.zip",FileName="Nordeluna-diagnostico.zip"})if(save.ShowDialog(this)==DialogResult.OK){
        string crash=Path.Combine(home,"last-crash.json");Dictionary<string,object> previous=File.Exists(crash)?Files.Parse(Files.Read(crash)):null;
        using(var output=File.Create(save.FileName))using(var zip=new ZipArchive(output,ZipArchiveMode.Create)){var entry=zip.CreateEntry("diagnostico.json");using(var writer=new StreamWriter(entry.Open()))writer.Write(Files.Json.Serialize(new{ launcher="1.1.1",windows=Environment.OSVersion.VersionString,channel=Channel,is64bit=Environment.Is64BitOperatingSystem,previous_exit=previous,created=DateTime.UtcNow.ToString("o") }));}
        if(File.Exists(crash))File.Delete(crash);MessageBox.Show("Relatório salvo. Nenhum save ou dado de login foi incluído.");
    }return Task.CompletedTask;}
    [STAThread] static void Main(string[] args){ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;if(args.Contains("--verify-only")){Files.Verify(File.ReadAllText(args[Array.IndexOf(args,"--verify-only")+1]));return;}
        using(var mutex=new Mutex(false,"Local\\NordelunaClientLauncher")){if(!mutex.WaitOne(0)){MessageBox.Show("O launcher já está aberto.");return;}try{Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Launcher());}finally{mutex.ReleaseMutex();}}
    }
}
}
