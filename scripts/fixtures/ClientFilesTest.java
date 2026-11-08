import com.mkxpz.launcher.ClientFiles;
import java.io.*;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

public class ClientFilesTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception{
        File root=new File(args[0]),saves=new File(root,"saves"),backups=new File(root,"backups");saves.mkdirs();
        try{ClientFiles.child(root,"../escape");throw new AssertionError("Traversal accepted");}catch(IOException expected){}
        for(int i=0;i<7;i++){ClientFiles.write(new File(saves,"Save_1.rxdata"),("save-"+i).getBytes(StandardCharsets.UTF_8));ClientFiles.write(new File(saves,"launcher-save-info.json"),("{\"play_seconds\":"+i*3600+"}").getBytes(StandardCharsets.UTF_8));ClientFiles.backup(saves,backups,"stable");Thread.sleep(5);}
        File[] history=backups.listFiles(f->f.getName().endsWith(".zip"));check(history.length==5,"Retention failed");check(ClientFiles.describeBackup(history[0]).contains("h"),"Playtime missing");
        String old;try(ZipFile zip=new ZipFile(history[0])){try(InputStream in=zip.getInputStream(zip.getEntry("saves/Save_1.rxdata"))){old=new String(ClientFiles.bounded(in,1024),StandardCharsets.UTF_8);}}
        ClientFiles.restore(history[0],saves,backups,"stable");check(new String(ClientFiles.read(new File(saves,"Save_1.rxdata")),StandardCharsets.UTF_8).equals(old),"Restore failed");
        File bad=new File(root,"bad.zip");try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(bad))){zip.putNextEntry(new ZipEntry("saves/../../escape.rxdata"));zip.write("bad".getBytes(StandardCharsets.UTF_8));zip.closeEntry();}
        try{ClientFiles.restore(bad,saves,backups,"stable");throw new AssertionError("Bad ZIP accepted");}catch(IOException expected){}
        check(new String(ClientFiles.read(new File(saves,"Save_1.rxdata")),StandardCharsets.UTF_8).equals(old),"Bad ZIP changed saves");
        try{ClientFiles.verifyCatalog("{\"manifest\":\"{}\",\"signature\":\"00\"}","ff");throw new AssertionError("Bad signature accepted");}catch(Exception expected){}
        System.out.println("PASS: Android five backups, restore, metadata, traversal and unsigned-catalog rejection");
    }
}
