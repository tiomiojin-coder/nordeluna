using System;
using System.IO;
using System.Net;
using System.Text;
using System.Security.Cryptography;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Nordeluna {
static class TesterAccess {
    public static Dictionary<string,object> Call(Dictionary<string,object> payload){
        payload["protocol"]=1;var request=(HttpWebRequest)WebRequest.Create("https://nordeluna-online.discloud.dev/api");request.Method="POST";request.ContentType="application/json";request.AllowAutoRedirect=false;request.Timeout=15000;request.ReadWriteTimeout=30000;
        byte[] bytes=Encoding.UTF8.GetBytes(Files.Json.Serialize(payload));request.ContentLength=bytes.Length;using(var output=request.GetRequestStream())output.Write(bytes,0,bytes.Length);
        HttpWebResponse response;try{response=(HttpWebResponse)request.GetResponse();}catch(WebException error){response=error.Response as HttpWebResponse;if(response==null)throw new IOException("Não foi possível validar o convite. Verifique sua conexão.");}
        using(response)using(var input=response.GetResponseStream())using(var output=new MemoryStream()){
            byte[] b=new byte[8192];int n;while((n=input.Read(b,0,b.Length))>0){if(output.Length+n>262144)throw new IOException("Resposta inválida");output.Write(b,0,n);}
            var result=Files.Parse(Encoding.UTF8.GetString(output.ToArray()));if(response.StatusCode!=HttpStatusCode.OK||Files.Str(result,"ok")!="True")throw new IOException(Files.Str(result,"error","Acesso de tester recusado"));return result;
        }
    }
    public static string Unlock(string input,string target,Dictionary<string,object> row,string key){
        if(key.Length!=64||Files.Hash(input)!=Files.Str(row,"sha256")||Files.Str(row,"encrypted")!="True")throw new IOException("Pacote protegido inválido");
        var plain=Files.Obj(row["plain"]);long expected=Convert.ToInt64(plain["size"]);if(expected<1||expected>3L*1024*1024*1024)throw new IOException("Tamanho inválido");string temp=target+".unlocking";
        try{
            using(var source=File.OpenRead(input))using(var aes=Aes.Create())using(var output=File.Create(temp)){
                byte[] iv=new byte[16];if(source.Read(iv,0,16)!=16)throw new IOException("Pacote incompleto");aes.Key=Files.Hex(key);aes.IV=iv;
                using(var decoded=new CryptoStream(source,aes.CreateDecryptor(),CryptoStreamMode.Read)){byte[] b=new byte[131072];int n;long count=0;while((n=decoded.Read(b,0,b.Length))>0){count+=n;if(count>expected)throw new IOException("Pacote maior que o esperado");output.Write(b,0,n);}if(count!=expected)throw new IOException("Pacote incompleto");}output.Flush(true);
            }
            if(Files.Hash(temp)!=Files.Str(plain,"sha256"))throw new IOException("Conteúdo de testes corrompido");if(File.Exists(target))File.Delete(target);File.Move(temp,target);return target;
        }finally{if(File.Exists(temp))File.Delete(temp);}
    }
}
partial class Launcher {
    Dictionary<string,object> testerCredentials,testerRelease;
    string TesterPath {get{return Path.Combine(home,"tester-access.dat");}}
    async Task AuthorizeTester(bool interactive){
        if(testerCredentials==null&&File.Exists(TesterPath))try{testerCredentials=Files.Parse(Encoding.UTF8.GetString(ProtectedData.Unprotect(File.ReadAllBytes(TesterPath),null,DataProtectionScope.CurrentUser)));}catch{throw new IOException("Não foi possível recuperar o acesso local. Solicite outro convite.");}
        if(testerCredentials==null){
            if(!interactive)throw new IOException("Ative um convite para entrar no canal testers");
            using(var dialog=new Form{Text="Convite de tester",Width=520,Height=210,StartPosition=FormStartPosition.CenterParent}){
                var label=new Label{Text="Cole sua chave individual. O acesso será vinculado a este dispositivo.\nÉ necessária conexão para validar o acesso.",Dock=DockStyle.Top,Height=55};
                var entry=new TextBox{Dock=DockStyle.Top,UseSystemPasswordChar=true};var confirm=new Button{Text="Ativar convite",Dock=DockStyle.Bottom,Height=40,DialogResult=DialogResult.OK};dialog.Controls.Add(entry);dialog.Controls.Add(label);dialog.Controls.Add(confirm);dialog.AcceptButton=confirm;
                if(dialog.ShowDialog(this)!=DialogResult.OK)throw new IOException("Ativação cancelada");
                string code=entry.Text.Trim().ToUpperInvariant();
                var credentials=await Task.Run(()=>TesterAccess.Call(new Dictionary<string,object>{{"action","tester_redeem"},{"code",code},{"device",Guid.NewGuid().ToString("N")}}));
                testerCredentials=Files.Obj(credentials["credentials"]);Directory.CreateDirectory(home);File.WriteAllBytes(TesterPath,ProtectedData.Protect(Encoding.UTF8.GetBytes(Files.Json.Serialize(testerCredentials)),null,DataProtectionScope.CurrentUser));
            }
        }
        var result=await Task.Run(()=>TesterAccess.Call(new Dictionary<string,object>{{"action","tester_access"},{"tester",testerCredentials}}));testerRelease=result["release"]==null?null:Files.Obj(result["release"]);
    }
    async Task<Dictionary<string,object>> ChannelCatalog(bool interactive){
        if(Channel!="testers")return await Task.Run(()=>Files.Verify(Files.Catalog(Files.Str(preferences,"catalog",DefaultCatalog))));
        await AuthorizeTester(interactive);if(testerRelease==null)throw new IOException("Convite ativo. Aguarde a publicação da versão de testes.");return Files.Verify(Files.Json.Serialize(testerRelease["catalog"]));
    }
    string DownloadChannel(Dictionary<string,object> row,string directory){
        string file=Files.Download(row,directory,Progress);if(Files.Str(row,"encrypted")!="True")return file;
        if(testerRelease==null)throw new IOException("Valide seu convite novamente");
        try{return TesterAccess.Unlock(file,Path.Combine(directory,"testers.zip"),row,Files.Str(Files.Obj(testerRelease["keys"]),"windows"));}finally{if(File.Exists(file))File.Delete(file);}
    }
    Task ResetTester(){if(MessageBox.Show("Remover o acesso deste PC? Será necessário um convite novo para ativar novamente.","Trocar convite",MessageBoxButtons.YesNo)!=DialogResult.Yes)return Task.CompletedTask;if(File.Exists(TesterPath))File.Delete(TesterPath);testerCredentials=null;testerRelease=null;status.Text="Acesso removido deste PC. Solicite um convite novo para ativar novamente.";return Task.CompletedTask;}
}
}
