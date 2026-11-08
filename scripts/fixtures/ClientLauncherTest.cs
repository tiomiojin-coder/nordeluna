using System;
using System.IO;
using System.IO.Compression;
using System.Collections.Generic;
using Nordeluna;

class ClientLauncherTest {
    static void Check(bool test,string message){if(!test)throw new Exception(message);}
    static void Reject(Action action){try{action();}catch{return;}throw new Exception("Expected rejection");}
    static void Zip(string path,Dictionary<string,string> values){using(var zip=ZipFile.Open(path,ZipArchiveMode.Create))foreach(var row in values){var entry=zip.CreateEntry(row.Key);using(var writer=new StreamWriter(entry.Open()))writer.Write(row.Value);}}
    public static int Main(string[] args){try{Run(args);return 0;}catch(Exception error){Console.Error.WriteLine(error);return 1;}}
    static void Run(string[] args){
        string root=args[0],saves=Path.Combine(root,"saves"),backups=Path.Combine(root,"backups");Directory.CreateDirectory(saves);
        Reject(()=>Files.Child(root,"../secret"));Reject(()=>Files.Child(root,"C:/secret"));Reject(()=>Files.Child(root,"a\\b"));
        var conf=Files.Parse(Files.Configure("{\n// comment\n\"windowTitle\":\"Nordeluna\",\n}",true,1536));Check(Files.Num(conf,"defScreenH")==1152&&Convert.ToBoolean(conf["fullscreen"]),"Screen settings lost");
        for(int i=0;i<7;i++){File.WriteAllText(Path.Combine(saves,"Save_1.rxdata"),"version-"+i);Files.Save(Path.Combine(saves,"launcher-save-info.json"),new{play_seconds=i*3600});Files.Backup(saves,backups,"stable");System.Threading.Thread.Sleep(5);}
        var history=Directory.GetFiles(backups,"save-*.zip");Check(history.Length==5,"Wrong retention");Check(Files.DescribeBackup(history[0]).Contains("h"),"Missing play time");
        string selected=history[0];string old;using(var zip=ZipFile.OpenRead(selected))using(var input=new StreamReader(zip.GetEntry("saves/Save_1.rxdata").Open()))old=input.ReadToEnd();
        Files.Restore(selected,saves,backups,"stable");Check(File.ReadAllText(Path.Combine(saves,"Save_1.rxdata"))==old,"Restore lost save");
        string malicious=Path.Combine(root,"bad.zip");Zip(malicious,new Dictionary<string,string>{{"saves/../../escape.rxdata","bad"}});Reject(()=>Files.Restore(malicious,saves,backups,"stable"));Check(File.ReadAllText(Path.Combine(saves,"Save_1.rxdata"))==old,"Invalid ZIP modified saves");
        string game=Path.Combine(root,"game");Directory.CreateDirectory(game);File.WriteAllText(Path.Combine(game,"Game.exe"),"old-engine");Directory.CreateDirectory(Path.Combine(game,"Saves"));File.WriteAllText(Path.Combine(game,"Saves/Save_1.rxdata"),"private-save");
        string pack=Path.Combine(root,"full.zip");Zip(pack,new Dictionary<string,string>{{"Game.exe","new-engine"},{"Data/PluginScripts.rxdata","new-plugin"},{"Graphics/UI/new.png","new-image"}});Files.Apply(pack,game,(t,p)=>{});Check(File.ReadAllText(Path.Combine(game,"Game.exe"))=="new-engine","Engine not replaced");Check(File.ReadAllText(Path.Combine(game,"Saves/Save_1.rxdata"))=="private-save","Save overwritten by update");
        string badFull=Path.Combine(root,"bad-full.zip");Zip(badFull,new Dictionary<string,string>{{"Game.exe","bad"},{"Data/../outside.txt","bad"}});Reject(()=>Files.Apply(badFull,game,(t,p)=>{}));Check(File.ReadAllText(Path.Combine(game,"Game.exe"))=="new-engine","Invalid update touched engine");
        string recovery=Path.Combine(game,".launcher/rollback-test");Directory.CreateDirectory(recovery);File.WriteAllText(Path.Combine(recovery,"Game.exe"),"known-engine");Files.Save(Path.Combine(game,".launcher-update-journal.json"),new{rollback=".launcher/rollback-test",files=new[]{new{path="Game.exe",existed=true},new{path="Data/added.dat",existed=false}}});File.WriteAllText(Path.Combine(game,"Data/added.dat"),"partial");Files.Recover(game);Check(File.ReadAllText(Path.Combine(game,"Game.exe"))=="known-engine"&&!File.Exists(Path.Combine(game,"Data/added.dat")),"Interrupted update not rolled back");
        Reject(()=>Files.Verify("{\"manifest\":\"{}\",\"signature\":\"00\"}"));
        Console.WriteLine("PASS: launcher settings, safe paths, five backups, restore, invalid ZIPs, full engine update, save preservation and interrupted-update rollback");
    }
}
