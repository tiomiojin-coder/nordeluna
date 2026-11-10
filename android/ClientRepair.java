package com.mkxpz.launcher;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;
import org.json.*;

/** Repairs extracted game data from the installed, signed APK without downloads. */
public final class ClientRepair {
    public interface Source { InputStream open() throws Exception; }
    private ClientRepair(){}
    public static boolean runtimePath(String path){
        if(path==null||path.length()>250||path.contains("\\")||path.contains(":")||path.startsWith("/"))return false;
        for(String part:path.split("/",-1))if(part.isEmpty()||part.startsWith(".")||part.endsWith(".")||part.endsWith(" "))return false;
        for(String part:path.split("/"))if(part.equalsIgnoreCase("Saves"))return false;
        if(new File(path).getName().matches("(?i)(?:Save_?[0-9]*|Game)\\.(?:rxdata|rvdata2?)"))return false;
        return path.matches("(?:Data|Graphics|Audio|Movies|Fonts|Plugins)/.+")||Arrays.asList("Game.exe","Game.ini","mkxp.json","RGSS104E.dll","x64-msvcrt-ruby310.dll","zlib1.dll","soundfont.sf2","achievements.dat").contains(path);
    }
    public static boolean contentPath(String path){
        if(!runtimePath(path))return false;
        return path.matches("Data/Map[0-9]{3,6}\\.rxdata")||Arrays.asList("Data/MapInfos.rxdata","Data/Tilesets.rxdata","Data/CommonEvents.rxdata","Data/map_metadata.dat","Data/map_connections.dat","Data/encounters.dat","Data/species.dat","Data/species_metrics.dat","Data/types.dat","Data/abilities.dat","Data/moves.dat","Data/items.dat","Data/regional_dexes.dat").contains(path)||path.matches("(?:Graphics|Audio|Movies)/.+");
    }
    private static JSONObject json(File file)throws Exception{return new JSONObject(new String(ClientFiles.read(file),StandardCharsets.UTF_8));}
    private static File safe(File root,String name)throws Exception{
        File base=root.getCanonicalFile(),file=ClientFiles.child(base,name),current=base;
        for(String part:name.split("/")){current=new File(current,part);if(!current.getAbsoluteFile().equals(current.getCanonicalFile()))throw new IOException("Link não permitido na reparação");}
        return file;
    }
    private static void validateRow(JSONObject row,boolean content)throws Exception{
        String path=row.getString("path");long size=row.getLong("size");
        if(!(content?contentPath(path):runtimePath(path))||size<0||size>512L*1024*1024||!row.getString("sha256").matches("[0-9a-f]{64}"))throw new IOException("Registro de reparação inválido");
    }
    private static boolean healthy(File file,JSONObject row)throws Exception{
        if(!file.isFile())return false;
        if(row.optBoolean("mutable",false)&&row.getString("path").equals("mkxp.json")){try{json(file);return true;}catch(Exception corrupt){return false;}}
        return file.length()==row.getLong("size")&&ClientFiles.hash(file).equals(row.getString("sha256"));
    }
    private static void copy(InputStream in,File target,long size)throws Exception{
        target.getParentFile().mkdirs();try(FileOutputStream out=new FileOutputStream(target)){long written=0;int n;byte[] b=new byte[65536];while((n=in.read(b))!=-1){written+=n;if(written>size)throw new IOException("Arquivo maior que o manifesto");out.write(b,0,n);}if(written!=size)throw new IOException("Arquivo incompleto");out.getFD().sync();}
    }
    private static void remove(File root)throws IOException{if(root.getAbsoluteFile().equals(root.getCanonicalFile())){File[] list=root.listFiles();if(list!=null)for(File f:list)remove(f);}root.delete();}
    private static void replace(File source,File target)throws Exception{
        File temp=new File(target+".repair.tmp");if(!temp.getAbsoluteFile().equals(temp.getCanonicalFile()))throw new IOException("Link não permitido no arquivo temporário");
        try{try(InputStream in=new FileInputStream(source)){copy(in,temp,source.length());}
            if(!temp.renameTo(target)){if(target.exists()&&!target.delete())throw new IOException("Arquivo em uso");if(!temp.renameTo(target))throw new IOException("Não foi possível restaurar arquivo");}
        }finally{if(temp.exists())temp.delete();}
    }
    public static synchronized int repair(File game,Source source,ClientFiles.Progress progress)throws Exception{
        File updates=new File(game,".nordeluna-updates");
        if(new File(updates,"pending.json").exists()||new File(updates,"journal.json").exists())throw new IOException("Abra e feche o jogo para concluir a atualização pendente antes de reparar");
        Map<String,JSONObject> expected=new LinkedHashMap<>();Set<String> seen=new HashSet<>();
        try(ZipInputStream zip=new ZipInputStream(source.open())){
            ZipEntry first=zip.getNextEntry();if(first==null||!first.getName().equals("client-repair.json"))throw new IOException("Este APK ainda não tem o índice de reparação. Instale uma versão com esse recurso");
            JSONObject data=new JSONObject(new String(ClientFiles.bounded(zip,8*1024*1024),StandardCharsets.UTF_8));
            if(data.getInt("schema")!=1||!data.getString("platform").equals("android"))throw new IOException("Índice de outra plataforma");
            JSONArray rows=data.getJSONArray("files");if(rows.length()>60000)throw new IOException("Índice grande demais");
            for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);validateRow(row,false);String name=row.getString("path");if(!seen.add(name.toLowerCase(Locale.ROOT)))throw new IOException("Caminho duplicado");expected.put(name,row);}
        }
        Set<String> content=new HashSet<>();File installed=new File(updates,"installed.json");
        if(installed.exists()){
            JSONArray rows=json(installed).getJSONArray("files");if(rows.length()>500)throw new IOException("Registro de atualização inválido");
            for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);validateRow(row,true);String path=row.getString("path");if(!content.add(path))throw new IOException("Atualização duplicada");expected.put(path,row);}
        }
        Map<String,JSONObject> broken=new LinkedHashMap<>();int scanned=0;
        for(Map.Entry<String,JSONObject> row:expected.entrySet()){
            if(!healthy(safe(game,row.getKey()),row.getValue()))broken.put(row.getKey(),row.getValue());
            if(++scanned%100==0)progress.show("Conferindo arquivos",scanned*100/Math.max(1,expected.size()));
        }
        if(broken.isEmpty())return 0;
        // Stage everything before replacing anything. A lost OTA cache never restores old base maps.
        File work=safe(game,".client-repair-work");if(work.exists())throw new IOException("Existe uma recuperação pendente. Reabra o aplicativo para recuperá-la");
        work.mkdirs();File stage=new File(work,"stage"),backup=new File(work,"backup");JSONArray journal=new JSONArray();Set<String> staged=new HashSet<>();
        try{
            for(String name:broken.keySet())if(content.contains(name)){
                File cache=safe(new File(updates,"stage"),name);JSONObject row=broken.get(name);
                if(!healthy(cache,row))throw new IOException("O cache da atualização também está danificado: "+name+". Preserve o save e reinstale o pacote de conteúdo pelo jogo");
                try(InputStream in=new FileInputStream(cache)){copy(in,safe(stage,name),row.getLong("size"));}staged.add(name);
            }
            try(ZipInputStream zip=new ZipInputStream(source.open())){ZipEntry entry;while((entry=zip.getNextEntry())!=null){String name=entry.getName();if(!broken.containsKey(name)||staged.contains(name))continue;
                JSONObject row=broken.get(name);File file=safe(stage,name);copy(zip,file,row.getLong("size"));if(!ClientFiles.hash(file).equals(row.getString("sha256")))throw new IOException("Recurso do APK não corresponde ao índice: "+name);staged.add(name);progress.show("Preparando reparação",staged.size()*100/broken.size());
            }}
            if(staged.size()!=broken.size())throw new IOException("O APK não contém todos os arquivos necessários");
            for(String name:broken.keySet()){
                File target=safe(game,name);JSONObject row=new JSONObject();row.put("path",name);row.put("existed",target.isFile());
                if(target.isFile()){row.put("sha256",ClientFiles.hash(target));try(InputStream in=new FileInputStream(target)){copy(in,safe(backup,name),target.length());}}
                journal.put(row);
            }
            JSONObject record=new JSONObject();record.put("files",journal);ClientFiles.write(new File(work,"journal.json"),record.toString().getBytes(StandardCharsets.UTF_8));
            for(String name:broken.keySet()){
                File stagedFile=safe(stage,name),target=safe(game,name);replace(stagedFile,target);
            }
            if(!new File(work,"journal.json").delete())throw new IOException("Não foi possível concluir a reparação");
        }catch(Exception error){if(new File(work,"journal.json").isFile())recover(game);throw error;}
        finally{if(!new File(work,"journal.json").exists())remove(work);}
        return broken.size();
    }
    public static synchronized void recover(File game)throws Exception{
        File work=safe(game,".client-repair-work"),record=new File(work,"journal.json");
        if(!record.isFile()){if(work.exists())remove(work);return;}
        JSONArray rows=json(record).getJSONArray("files");
        // Validate every backup before restoring any file.
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);String name=row.getString("path");if(!runtimePath(name))throw new IOException("Diário de reparação inválido");safe(game,name);
            if(row.getBoolean("existed")){File old=safe(new File(work,"backup"),name);if(!old.isFile()||!ClientFiles.hash(old).equals(row.getString("sha256")))throw new IOException("Backup de recuperação incompleto");}}
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);String name=row.getString("path");File target=safe(game,name);
            if(row.getBoolean("existed")){File old=safe(new File(work,"backup"),name);replace(old,target);}
            else if(target.exists()&&!target.delete())throw new IOException("Falha na recuperação");
        }
        if(!record.delete())throw new IOException("Não foi possível concluir a recuperação; os backups foram preservados");
        remove(work);
    }
}
