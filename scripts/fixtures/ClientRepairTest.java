import com.mkxpz.launcher.ClientFiles;
import com.mkxpz.launcher.ClientRepair;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;
import org.json.*;

public class ClientRepairTest {
    static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    static byte[] bytes(String s){return s.getBytes(StandardCharsets.UTF_8);}
    static String hash(String s)throws Exception{return ClientFiles.hex(MessageDigest.getInstance("SHA-256").digest(bytes(s)));}
    static JSONObject row(String name,String s)throws Exception{JSONObject r=new JSONObject();r.put("path",name);r.put("size",bytes(s).length);r.put("sha256",hash(s));r.put("mutable",name.equals("mkxp.json"));return r;}
    static byte[] bundle(Map<String,String> files)throws Exception{
        JSONObject meta=new JSONObject();meta.put("schema",1);meta.put("platform","android");JSONArray rows=new JSONArray();for(Map.Entry<String,String> entry:files.entrySet())rows.put(row(entry.getKey(),entry.getValue()));meta.put("files",rows);
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(buffer)){zip.putNextEntry(new ZipEntry("client-repair.json"));zip.write(bytes(meta.toString()));zip.closeEntry();for(Map.Entry<String,String> entry:files.entrySet()){zip.putNextEntry(new ZipEntry(entry.getKey()));zip.write(bytes(entry.getValue()));zip.closeEntry();}}return buffer.toByteArray();
    }
    public static void main(String[] args)throws Exception{
        File game=new File(args[0]);game.mkdirs();Map<String,String> files=new LinkedHashMap<>();files.put("Game.ini","correct-ini");files.put("Data/PluginScripts.rxdata","correct-plugins");files.put("Graphics/Tilesets/Árvore.png","original-image");files.put("mkxp.json","{\"fullscreen\":false}");byte[] archive=bundle(files);
        File image=new File(game,"Graphics/Tilesets/Árvore.png");ClientFiles.write(image,bytes("original-image"));ClientFiles.write(new File(game,"mkxp.json"),bytes("{\"fullscreen\":true}"));ClientFiles.write(new File(game,"Saves/Save_1.rxdata"),bytes("private-progress"));
        ClientRepair.Source source=()->new ByteArrayInputStream(archive);String config=new String(ClientFiles.read(new File(game,"mkxp.json")),StandardCharsets.UTF_8);long timestamp=image.lastModified();
        check(ClientRepair.repair(game,source,(t,p)->{})==2,"Wrong missing-file count");check(new String(ClientFiles.read(new File(game,"mkxp.json")),StandardCharsets.UTF_8).equals(config),"Preferences reset");check(image.lastModified()==timestamp,"Healthy image overwritten");
        check(ClientRepair.repair(game,source,(t,p)->{})==0,"Healthy installation changed");
        JSONObject update=row("Graphics/Tilesets/Árvore.png","updated-image"),installed=new JSONObject();installed.put("files",new JSONArray().put(update));ClientFiles.write(new File(game,".nordeluna-updates/installed.json"),bytes(installed.toString()));
        File cache=new File(game,".nordeluna-updates/stage/Graphics/Tilesets/Árvore.png");ClientFiles.write(cache,bytes("updated-image"));ClientFiles.write(image,bytes("updated-image"));check(ClientRepair.repair(game,source,(t,p)->{})==0,"Updated sprite reverted to APK base");
        ClientFiles.write(image,bytes("damaged"));check(ClientRepair.repair(game,source,(t,p)->{})==1&&new String(ClientFiles.read(image),StandardCharsets.UTF_8).equals("updated-image"),"Updated sprite not recovered from cache");
        ClientFiles.write(image,bytes("still-damaged"));cache.delete();try{ClientRepair.repair(game,source,(t,p)->{});throw new AssertionError("Missing update cache ignored");}catch(IOException expected){}check(new String(ClientFiles.read(image),StandardCharsets.UTF_8).equals("still-damaged"),"Missing cache downgraded sprite");
        File work=new File(game,".client-repair-work"),old=new File(work,"backup/Game.ini");ClientFiles.write(old,bytes("previous-ini"));JSONObject record=new JSONObject();record.put("files",new JSONArray().put(new JSONObject().put("path","Game.ini").put("existed",true).put("sha256",hash("previous-ini"))));ClientFiles.write(new File(work,"journal.json"),bytes(record.toString()));ClientFiles.write(new File(game,"Game.ini"),bytes("partial-ini"));ClientRepair.recover(game);check(new String(ClientFiles.read(new File(game,"Game.ini")),StandardCharsets.UTF_8).equals("previous-ini"),"Interrupted repair not recovered");
        check(new String(ClientFiles.read(new File(game,"Saves/Save_1.rxdata")),StandardCharsets.UTF_8).equals("private-progress"),"Repair touched saves");
        System.out.println("PASS: Android offline selective repair, preferences, updated sprites, missing-cache protection and crash recovery");
    }
}
