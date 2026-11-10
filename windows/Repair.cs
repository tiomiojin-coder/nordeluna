using System;
using System.IO;
using System.IO.Compression;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Security.Cryptography;

namespace Nordeluna {
static partial class Files {
    public static bool RepairPath(string name){
        if(!RuntimePath(name)||name.Split('/').Any(p=>p.Equals("Saves",StringComparison.OrdinalIgnoreCase)))return false;
        return !Regex.IsMatch(Path.GetFileName(name),@"\A(?:Save_?\d*|Game)\.(?:rxdata|rvdata2?)\z",RegexOptions.IgnoreCase);
    }
    static bool ContentPath(string name){return RepairPath(name)&&(Regex.IsMatch(name,@"\AData/Map[0-9]{3,6}\.rxdata\z")||new[]{"Data/MapInfos.rxdata","Data/Tilesets.rxdata","Data/CommonEvents.rxdata","Data/map_metadata.dat","Data/map_connections.dat","Data/encounters.dat","Data/species.dat","Data/species_metrics.dat","Data/types.dat","Data/abilities.dat","Data/moves.dat","Data/items.dat","Data/regional_dexes.dat"}.Contains(name)||new[]{"Graphics/","Audio/","Movies/"}.Any(p=>name.StartsWith(p,StringComparison.Ordinal)));}
    static string RepairTarget(string root,string name){
        string target=Child(root,name),relative=target.Substring(Path.GetFullPath(root).TrimEnd('\\').Length).TrimStart('\\');string current=Path.GetFullPath(root);
        foreach(string part in relative.Split('\\')){current=Path.Combine(current,part);if((File.Exists(current)||Directory.Exists(current))&&(File.GetAttributes(current)&FileAttributes.ReparsePoint)!=0)throw new IOException("Link não permitido na reparação");}return target;
    }
    static void CheckRepairRow(Dictionary<string,object> row,bool content){
        string name=Str(row,"path");long size=Convert.ToInt64(row["size"]);
        if(!(content?ContentPath(name):RepairPath(name))||size<0||size>512L*1024*1024||!Regex.IsMatch(Str(row,"sha256"),"\\A[0-9a-f]{64}\\z"))throw new IOException("Registro de reparação inválido");
    }
    static bool RepairHealthy(string target,Dictionary<string,object> row){
        if(!File.Exists(target))return false;
        if(Str(row,"path")=="mkxp.json"&&row.ContainsKey("mutable")&&Convert.ToBoolean(row["mutable"]))try{Configure(Read(target),false,512);return true;}catch{return false;}
        return new FileInfo(target).Length==Convert.ToInt64(row["size"])&&Hash(target)==Str(row,"sha256");
    }
    public static void PruneRollback(string game,string keep){
        foreach(string old in Directory.GetDirectories(Path.Combine(game,".launcher"),"rollback-*")){
            if(String.Equals(Path.GetFullPath(old),Path.GetFullPath(keep),StringComparison.OrdinalIgnoreCase))continue;
            if(!Regex.IsMatch(Path.GetFileName(old),"\\Arollback-[0-9a-f]{32}\\z")||(File.GetAttributes(old)&FileAttributes.ReparsePoint)!=0)continue;
            string checkedPath=Child(game,".launcher/"+Path.GetFileName(old));try{Directory.Delete(checkedPath,true);}catch(IOException){}catch(UnauthorizedAccessException){}
        }
    }
    sealed class LimitedRead : Stream {
        readonly Stream source;long left;public LimitedRead(Stream input,long length){source=input;left=length;}
        public override int Read(byte[] b,int offset,int count){if(left==0)return 0;int n=source.Read(b,offset,(int)Math.Min(count,left));if(n==0)throw new IOException("Trecho de download incompleto");left-=n;return n;}
        public override bool CanRead{get{return true;}}public override bool CanSeek{get{return false;}}public override bool CanWrite{get{return false;}}
        public override long Length{get{throw new NotSupportedException();}}public override long Position{get{throw new NotSupportedException();}set{throw new NotSupportedException();}}
        public override void Flush(){}public override long Seek(long o,SeekOrigin s){throw new NotSupportedException();}public override void SetLength(long l){throw new NotSupportedException();}public override void Write(byte[] b,int o,int n){throw new NotSupportedException();}
    }
    public static int Repair(Dictionary<string,object> index,string game,Func<Dictionary<string,object>,Stream> fetch,Action<string,int> progress){
        EnsureClosed(game);Recover(game);
        if(Num(index,"schema")!=1||Str(index,"platform")!="windows")throw new IOException("Índice de outra plataforma");
        string updates=Path.Combine(game,".nordeluna-updates");if(File.Exists(Path.Combine(updates,"pending.json"))||File.Exists(Path.Combine(updates,"journal.json")))throw new IOException("Abra e feche o jogo para concluir a atualização pendente antes de reparar");
        long archiveSize=Convert.ToInt64(index["archive_size"]);if(archiveSize<1||archiveSize>3L*1024*1024*1024)throw new IOException("Pacote inválido");
        var expected=new Dictionary<string,Dictionary<string,object>>(StringComparer.OrdinalIgnoreCase);var cached=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach(object obj in (IEnumerable)index["files"]){var row=Obj(obj);CheckRepairRow(row,false);string name=Str(row,"path");long start=Convert.ToInt64(row["offset"]),length=Convert.ToInt64(row["packed_size"]);int method=Num(row,"method",-1);
            if(expected.Count>=60000||expected.ContainsKey(name)||start<0||start>archiveSize||length<0||length>archiveSize-start||!new[]{0,8}.Contains(method))throw new IOException("Índice de reparação inválido");expected.Add(name,row);
        }
        string installed=Path.Combine(updates,"installed.json");if(File.Exists(installed))foreach(object obj in (IEnumerable)Parse(Read(installed))["files"]){var row=Obj(obj);CheckRepairRow(row,true);string name=Str(row,"path");if(cached.Count>=500||!cached.Add(name))throw new IOException("Registro de conteúdo inválido");expected[name]=row;}
        var broken=new Dictionary<string,Dictionary<string,object>>();int scan=0;
        foreach(var pair in expected){if(!RepairHealthy(RepairTarget(game,pair.Key),pair.Value))broken[pair.Key]=pair.Value;if(++scan%100==0)progress("Conferindo arquivos",scan*100/Math.Max(1,expected.Count));}
        if(broken.Count==0)return 0;
        string id=Guid.NewGuid().ToString("N"),stage=RepairTarget(game,".launcher/repair-"+id),rollback=RepairTarget(game,".launcher/rollback-"+id);Directory.CreateDirectory(stage);Directory.CreateDirectory(rollback);
        try{
            int count=0;
            foreach(var pair in broken){string name=pair.Key;var row=pair.Value;string target=RepairTarget(stage,name);Directory.CreateDirectory(Path.GetDirectoryName(target));
                if(cached.Contains(name)){
                    string cache=RepairTarget(Path.Combine(updates,"stage"),name);if(!RepairHealthy(cache,row))throw new IOException("O cache da atualização também está danificado: "+name+". Preserve o save e recupere o pacote de conteúdo pelo jogo.");File.Copy(cache,target);
                }else{
                    long length=Convert.ToInt64(row["packed_size"]),size=Convert.ToInt64(row["size"]);
                    using(var raw=length==0?new MemoryStream(new byte[0]):fetch(row))using(var bounded=new LimitedRead(raw,length))
                    using(Stream input=Num(row,"method")==8?(Stream)new DeflateStream(bounded,CompressionMode.Decompress):bounded)
                    using(var output=File.Create(target)){
                        byte[] buffer=new byte[65536];long written=0;int n;while((n=input.Read(buffer,0,buffer.Length))>0){written+=n;if(written>size)throw new IOException("Arquivo maior que o índice assinado");output.Write(buffer,0,n);}if(written!=size)throw new IOException("Arquivo incompleto");output.Flush(true);
                    }
                }
                if(Hash(target)!=Str(row,"sha256"))throw new IOException("Arquivo de reparação corrompido: "+name);progress("Preparando reparação",++count*100/broken.Count);
            }
            var rows=new List<Dictionary<string,object>>();foreach(var pair in broken){string target=RepairTarget(game,pair.Key);bool exists=File.Exists(target);var row=new Dictionary<string,object>{{"path",pair.Key},{"existed",exists}};
                if(exists){string old=RepairTarget(rollback,pair.Key);Directory.CreateDirectory(Path.GetDirectoryName(old));File.Copy(target,old);row["sha256"]=Hash(old);}rows.Add(row);
            }
            string journal=Path.Combine(game,".launcher-update-journal.json");Save(journal,new{rollback=".launcher/rollback-"+id,files=rows});
            try{foreach(var pair in broken){string target=RepairTarget(game,pair.Key);Directory.CreateDirectory(Path.GetDirectoryName(target));File.Copy(RepairTarget(stage,pair.Key),target,true);}File.Delete(journal);}
            catch{Recover(game);throw;}
            PruneRollback(game,rollback);return broken.Count;
        }finally{if(Directory.Exists(stage))Directory.Delete(stage,true);}
    }
}
partial class Launcher {
    async System.Threading.Tasks.Task RepairInstallation(){await Work(async()=>{
        Files.EnsureClosed(GameRoot);string target=GameRoot,ch=Channel,data=Data,backups=BackupDir;
        if(ch=="testers")throw new IOException("A reparação parcial usa a versão estável. Para testes, use Atualizar para reinstalar o pacote protegido.");
        var catalog=await ChannelCatalog(true);
        var row=Files.Obj(Files.Obj(Files.Obj(catalog["channels"])[ch])["windows"]);
        string local=Path.Combine(target,"installed-client.json");int code=File.Exists(local)?Files.Num(Files.Parse(Files.Read(local)),"code"):LauncherKeys.Code;
        if(Files.Num(row,"code")!=code)throw new IOException("Atualize o jogo para a versão publicada antes de usar a reparação");
        if(!row.ContainsKey("repair"))throw new IOException("Esta versão ainda não publicou os dados de reparação");
        var descriptor=Files.Obj(row["repair"]);int result=await System.Threading.Tasks.Task.Run(()=>{
            string envelope=Files.Catalog(Files.Str(descriptor,"url"),16*1024*1024);byte[] bytes=Encoding.UTF8.GetBytes(envelope);string digest;
            using(var sha=SHA256.Create())digest=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
            if(bytes.LongLength!=Convert.ToInt64(descriptor["size"])||digest!=Files.Str(descriptor,"sha256"))throw new IOException("Índice de reparação corrompido");
            var index=Files.VerifySigned(envelope,8*1024*1024);if(Files.Num(index,"code")!=code||Files.Str(index,"archive_sha256")!=Files.Str(row,"sha256"))throw new IOException("Índice de outra versão do jogo");
            Files.Backup(data,backups,ch);
            return Files.Repair(index,target,part=>{var response=Files.Open(Files.Str(index,"archive_url"),Convert.ToInt64(part["offset"]),Convert.ToInt64(part["packed_size"]));return new ResponseStream(response);},Progress);
        });status.Text=result==0?"Instalação íntegra. Nenhum download necessário.":result+" arquivo(s) reparado(s). Saves e configurações preservados.";
    });}
    sealed class ResponseStream : Stream {
        readonly System.Net.HttpWebResponse response;readonly Stream input;public ResponseStream(System.Net.HttpWebResponse r){response=r;input=r.GetResponseStream();}
        public override int Read(byte[] b,int o,int n){return input.Read(b,o,n);}protected override void Dispose(bool disposing){if(disposing){input.Dispose();response.Dispose();}base.Dispose(disposing);}
        public override bool CanRead{get{return true;}}public override bool CanSeek{get{return false;}}public override bool CanWrite{get{return false;}}public override long Length{get{return input.Length;}}
        public override long Position{get{throw new NotSupportedException();}set{throw new NotSupportedException();}}public override void Flush(){}public override long Seek(long o,SeekOrigin s){throw new NotSupportedException();}public override void SetLength(long l){throw new NotSupportedException();}public override void Write(byte[] b,int o,int n){throw new NotSupportedException();}
    }
}
}
