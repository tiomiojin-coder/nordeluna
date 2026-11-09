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
using System.Windows.Forms;
using System.Web.Script.Serialization;

namespace Nordeluna {
static class Files {
    public static readonly JavaScriptSerializer Json=new JavaScriptSerializer { MaxJsonLength=8*1024*1024 };
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
        var wrapper=Parse(envelope);string raw=Str(wrapper,"manifest"),signature=Str(wrapper,"signature");if(raw.Length>180000||!Regex.IsMatch(signature,"\\A[0-9a-f]{512}\\z"))throw new IOException("Catálogo inválido");
        using(var rsa=new RSACryptoServiceProvider()){
            rsa.ImportParameters(new RSAParameters { Modulus=Hex(LauncherKeys.Modulus),Exponent=new byte[]{1,0,1} });
            if(!rsa.VerifyData(Encoding.UTF8.GetBytes(raw),CryptoConfig.MapNameToOID("SHA256"),Hex(signature)))throw new IOException("Assinatura da atualização inválida");
        }
        var data=Parse(raw);if(Num(data,"schema")!=1)throw new IOException("Atualize o launcher");return data;
    }
    public static HttpWebResponse Open(string url){
        for(int i=0;i<6;i++){
            Uri uri=new Uri(url);if(uri.Scheme!="https")throw new IOException("Use um endereço HTTPS");
            var req=(HttpWebRequest)WebRequest.Create(uri);req.AllowAutoRedirect=false;req.UserAgent="Nordeluna-Launcher/1.1";req.Timeout=15000;req.ReadWriteTimeout=30000;
            var response=(HttpWebResponse)req.GetResponse();int status=(int)response.StatusCode;
            if(status>=300&&status<400){url=new Uri(uri,response.Headers["Location"]).AbsoluteUri;response.Dispose();continue;}
            if(status!=200){response.Dispose();throw new IOException("Servidor respondeu HTTP "+status);}return response;
        }throw new IOException("Muitos redirecionamentos");
    }
    public static string Catalog(string url){using(var response=Open(url))using(var input=response.GetResponseStream())using(var output=new MemoryStream()){
        byte[] b=new byte[8192];int n;while((n=input.Read(b,0,b.Length))>0){if(output.Length+n>262144)throw new IOException("Catálogo grande demais");output.Write(b,0,n);}return Encoding.UTF8.GetString(output.ToArray());}}
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
            foreach(string old in Directory.GetDirectories(Path.Combine(game,".launcher"),"rollback-*")){
                if(String.Equals(old,rollback,StringComparison.OrdinalIgnoreCase))continue;
                if(!Regex.IsMatch(Path.GetFileName(old),"\\Arollback-[0-9a-f]{32}\\z")||(File.GetAttributes(old)&FileAttributes.ReparsePoint)!=0)continue;
                string checkedPath=Child(game,".launcher/"+Path.GetFileName(old));
                try{Directory.Delete(checkedPath,true);}catch(IOException){}catch(UnauthorizedAccessException){}
            }
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

class Launcher : Form {
    readonly string root=AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
    readonly string home=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Pokemon Nordeluna");
    const string DefaultCatalog="https://raw.githubusercontent.com/tiomiojin-coder/nordeluna/main/public/launcher/releases.json";
    Dictionary<string,object> preferences;ComboBox channel;Label status;TextBox news;ProgressBar progress;FlowLayoutPanel buttons;bool busy,configureOnly;Process game;
    string Channel {get{return channel.SelectedIndex==1?"testers":"stable";}}
    string Data {get{return Path.Combine(home,"player-data",Channel);}}
    string BackupDir {get{return Path.Combine(home,"player-backups",Channel);}}
    string GameRoot {get{return Channel=="stable"?root:Path.Combine(home,"channels/testers/game");}}
    string SettingsPath {get{return Path.Combine(home,"launcher.json");}}
    public Launcher(){
        Text="Pokémon Nordeluna";ClientSize=new Size(800,600);MinimumSize=new Size(650,530);StartPosition=FormStartPosition.CenterScreen;BackColor=Color.FromArgb(12,20,35);ForeColor=Color.White;Font=new Font("Segoe UI",10);
        try{Icon=new Icon(Path.Combine(root,"Nordeluna.ico"));}catch{}
        try{preferences=File.Exists(SettingsPath)?Files.Parse(Files.Read(SettingsPath)):new Dictionary<string,object>();}catch{preferences=new Dictionary<string,object>();}
        var layout=new TableLayoutPanel { Dock=DockStyle.Fill,Padding=new Padding(26),ColumnCount=1,RowCount=7 };layout.RowStyles.Add(new RowStyle(SizeType.Absolute,50));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,36));layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,100));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,50));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,25));Controls.Add(layout);
        layout.Controls.Add(new Label{Text="POKÉMON NORDELUNA",Font=new Font(Font.FontFamily,23,FontStyle.Bold),ForeColor=Color.FromArgb(112,224,231),Dock=DockStyle.Fill});
        channel=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Width=250};channel.Items.AddRange(new object[]{"Estável","Testers · saves separados"});channel.SelectedIndex=Files.Str(preferences,"channel")=="testers"?1:0;channel.SelectedIndexChanged+=(s,e)=>{preferences["channel"]=Channel;Files.Save(SettingsPath,preferences);};layout.Controls.Add(channel);
        news=new TextBox{Multiline=true,ReadOnly=true,BorderStyle=BorderStyle.None,BackColor=Color.FromArgb(19,32,49),ForeColor=ForeColor,Dock=DockStyle.Fill,ScrollBars=ScrollBars.Vertical,Text="Bem-vindo a Nordeluna. Confira novidades e atualizações antes de jogar. Você também pode jogar offline."};layout.Controls.Add(news);
        buttons=new FlowLayoutPanel{Dock=DockStyle.Fill,AutoScroll=true};layout.Controls.Add(buttons);Button("JOGAR",Play);Button("Atualizar",()=>CheckUpdates(true));Button("Backups",Backups);Button("Configurações",Settings);Button("Diagnóstico",Diagnostics);
        status=new Label{Dock=DockStyle.Fill,Text="Pronto para jogar • launcher 1.1.1"};layout.Controls.Add(status);progress=new ProgressBar{Dock=DockStyle.Fill};layout.Controls.Add(progress);
        FormClosing+=(s,e)=>{if(busy||game!=null&&!game.HasExited){e.Cancel=true;MessageBox.Show("Finalize o jogo ou a atualização antes de fechar o launcher.");}};
        Shown+=async(s,e)=>{try{Files.Recover(root);string tester=Path.Combine(home,"channels/testers/game");if(Directory.Exists(tester))Files.Recover(tester);}catch(Exception ex){MessageBox.Show("Recuperação pendente: "+ex.Message);buttons.Enabled=false;return;}
            string interrupted=Path.Combine(home,"session.json");if(File.Exists(interrupted)){Files.Save(Path.Combine(home,"last-crash.json"),new{ reason="Sessão anterior não terminou normalmente",time=DateTime.UtcNow.ToString("o") });File.Delete(interrupted);}
            if(File.Exists(Path.Combine(home,"last-crash.json"))&&MessageBox.Show("O jogo foi interrompido anteriormente. Exportar diagnóstico sem saves ou dados de login?","Diagnóstico",MessageBoxButtons.YesNo)==DialogResult.Yes)await Diagnostics();await CheckUpdates(false);
        };
    }
    void Button(string text,Func<Task> action){var button=new Button{Text=text,AutoSize=true,Height=40,FlatStyle=FlatStyle.Flat,BackColor=Color.FromArgb(29,55,73),Padding=new Padding(8),Margin=new Padding(4)};button.Click+=async(s,e)=>await action();buttons.Controls.Add(button);}
    async Task Work(Func<Task> action){if(busy)return;busy=true;buttons.Enabled=false;channel.Enabled=false;try{await action();}catch(Exception ex){status.Text="Não foi possível concluir: "+ex.Message;}finally{busy=false;buttons.Enabled=true;channel.Enabled=true;}}
    void Progress(string text,int percent){BeginInvoke((Action)(()=>{status.Text=text+" • "+percent+"%";progress.Value=Math.Max(0,Math.Min(100,percent));}));}
    async Task CheckUpdates(bool interactive){string requestedChannel=Channel;Func<Task> operation=async()=>{
        status.Text="Consultando novidades...";var catalog=await Task.Run(()=>Files.Verify(Files.Catalog(Files.Str(preferences,"catalog",DefaultCatalog))));
        if(IsDisposed||(!interactive&&busy)||requestedChannel!=Channel)return;
        var channels=Files.Obj(catalog["channels"]);if(!channels.ContainsKey(Channel))throw new IOException("Este canal ainda não tem uma versão publicada");var selected=Files.Obj(channels[Channel]);if(!selected.ContainsKey("windows"))throw new IOException("Nenhuma versão Windows neste canal");var row=Files.Obj(selected["windows"]);
        string local=Path.Combine(GameRoot,"installed-client.json");int code=File.Exists(local)?Files.Num(Files.Parse(Files.Read(local)),"code"):LauncherKeys.Code;
        news.Text=Files.Str(row,"notes","Sem notas de versão");if(selected.ContainsKey("android")&&Files.Str(Files.Obj(selected["android"]),"compatibility")!=Files.Str(row,"compatibility"))news.AppendText("\r\nAtenção: PC e Android publicados possuem versões online diferentes.");
        bool newer=Files.Num(row,"code")>code||!File.Exists(Path.Combine(GameRoot,"Game.exe"));status.Text=newer?"Atualização disponível: "+Files.Str(row,"version"):"Jogo atualizado";
        if(interactive&&newer&&MessageBox.Show("Baixar e aplicar a versão "+Files.Str(row,"version")+"? O jogo deve permanecer fechado.","Atualização completa",MessageBoxButtons.YesNo)==DialogResult.Yes){string target=GameRoot,data=Data,backups=BackupDir,ch=Channel;await Task.Run(()=>{Files.Backup(data,backups,ch);string zip=Files.Download(row,Path.Combine(home,"downloads",ch),Progress);Files.Apply(zip,target,Progress);Files.Save(Path.Combine(target,"installed-client.json"),row);});status.Text="Atualização concluída. Pode jogar.";}
    };if(interactive)await Work(operation);else try{await operation();}catch{if(!IsDisposed&&!busy)status.Text="Sem novidades disponíveis agora. Você pode jogar offline.";}}
    void Migrate(){if(Files.Saves(Path.Combine(home,"player-data/stable")).Any())return;string target=Path.Combine(home,"player-data/stable");
        foreach(string source in new[]{Path.Combine(root,"Saves"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),"Pokemon Nordeluna/Saves"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),"Pokemon Essentials v21.1/Saves")})foreach(string file in Files.Saves(source)){string to=Files.Child(target,file.Substring(source.Length).TrimStart('\\').Replace('\\','/'));Directory.CreateDirectory(Path.GetDirectoryName(to));if(!File.Exists(to))File.Copy(file,to);}}
    async Task Play(){await Work(async()=>{
        string target=GameRoot,data=Data,ch=Channel,backups=BackupDir;Files.EnsureClosed(target);Migrate();
        if(!File.Exists(Path.Combine(target,"Game.exe"))&&ch=="testers"){
            status.Text="Preparando cópia isolada para testers...";await Task.Run(()=>{var manifest=Files.Parse(Files.Read(Path.Combine(root,"pc-package.json")));foreach(string name in Files.Obj(manifest["files"]).Keys){if(!Files.RuntimePath(name))continue;string to=Files.Child(target,name);Directory.CreateDirectory(Path.GetDirectoryName(to));File.Copy(Files.Child(root,name),to,true);}Directory.CreateDirectory(target);File.Copy(Path.Combine(root,"pc-package.json"),Path.Combine(target,"pc-package.json"),true);});
        }
        if(!File.Exists(Path.Combine(target,"Game.exe"))){status.Text="Use Atualizar para instalar o jogo neste canal.";return;}
        await Task.Run(()=>Files.Backup(data,backups,ch));Directory.CreateDirectory(data);
        Files.Save(Path.Combine(target,".nordeluna-launcher.json"),new{ channel=ch,save_root=data,volume=Files.Num(preferences,"volume",80),settings_only=configureOnly });
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
