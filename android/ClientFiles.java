package com.mkxpz.launcher;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.*;
import java.security.spec.RSAPublicKeySpec;
import java.math.BigInteger;
import java.net.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.zip.*;
import org.json.*;

/** Filesystem/network work runs off the UI thread, only with the game closed. */
public final class ClientFiles {
    public interface Progress { void show(String text, int percent); }
    public static final String DEFAULT_CATALOG="https://raw.githubusercontent.com/tiomiojin-coder/nordeluna/main/public/launcher/releases.json";
    private ClientFiles() {}
    public static byte[] read(File file) throws IOException {
        try (InputStream in=new FileInputStream(file)) { return bounded(in,4*1024*1024); }
    }
    public static byte[] bounded(InputStream in,int limit) throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[32768];int n;
        while((n=in.read(b))!=-1){if(out.size()+n>limit)throw new IOException("Arquivo grande demais");out.write(b,0,n);}return out.toByteArray();
    }
    public static void write(File file,byte[] bytes) throws IOException {
        File parent=file.getParentFile();if(parent!=null&&!parent.isDirectory()&&!parent.mkdirs())throw new IOException("Sem espaço ou permissão");
        File tmp=new File(file+".tmp");try(FileOutputStream out=new FileOutputStream(tmp)){out.write(bytes);out.getFD().sync();}
        if(!tmp.renameTo(file)){
            // Android rename replaces atomically. This fallback also supports Windows tests.
            File prior=new File(file+".previous");if(!file.isFile()||!file.renameTo(prior))throw new IOException("Não foi possível gravar "+file.getName());
            if(!tmp.renameTo(file)){prior.renameTo(file);throw new IOException("Não foi possível gravar "+file.getName());}prior.delete();
        }
    }
    public static String hash(File file) throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)md.update(b,0,n);}return hex(md.digest());
    }
    public static String hex(byte[] b){StringBuilder s=new StringBuilder();for(byte v:b)s.append(String.format(Locale.ROOT,"%02x",v&255));return s.toString();}
    static HttpURLConnection connection(String address) throws Exception {
        URL url=new URL(address);if(!url.getProtocol().equals("https"))throw new IOException("Use um endereço HTTPS");
        for(int i=0;i<6;i++){
            HttpURLConnection c=(HttpURLConnection)url.openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(30000);c.setRequestProperty("User-Agent","Nordeluna-Launcher/1.1");
            int status=c.getResponseCode();if(status>=300&&status<400){URL next=new URL(url,c.getHeaderField("Location"));c.disconnect();if(!next.getProtocol().equals("https"))throw new IOException("Redirecionamento inseguro");url=next;continue;}
            if(status!=200){c.disconnect();throw new IOException("Servidor respondeu HTTP "+status);}return c;
        }throw new IOException("Muitos redirecionamentos");
    }
    public static JSONObject catalog(String url,String modulus) throws Exception {
        HttpURLConnection c=connection(url);byte[] bytes;try(InputStream in=c.getInputStream()){bytes=bounded(in,262144);}finally{c.disconnect();}
        return verifyCatalog(new String(bytes,StandardCharsets.UTF_8),modulus);
    }
    public static JSONObject verifyCatalog(String envelope,String modulus) throws Exception {
        JSONObject outer=new JSONObject(envelope);String raw=outer.getString("manifest"),signature=outer.getString("signature");
        if(raw.length()>180000||!signature.matches("[0-9a-f]{512}"))throw new IOException("Catálogo inválido");
        Signature check=Signature.getInstance("SHA256withRSA");check.initVerify(KeyFactory.getInstance("RSA").generatePublic(new RSAPublicKeySpec(new BigInteger(modulus,16),BigInteger.valueOf(65537))));check.update(raw.getBytes(StandardCharsets.UTF_8));
        byte[] signed=new byte[256];for(int i=0;i<256;i++)signed[i]=(byte)Integer.parseInt(signature.substring(i*2,i*2+2),16);
        if(!check.verify(signed))throw new IOException("A assinatura da atualização não confere");
        JSONObject data=new JSONObject(raw);if(data.getInt("schema")!=1)throw new IOException("Atualize o launcher");return data;
    }
    public static File download(JSONObject row,File destination,Progress progress) throws Exception {
        long size=row.getLong("size");String expected=row.getString("sha256");if(size<1||size>3L*1024*1024*1024||!expected.matches("[0-9a-f]{64}"))throw new IOException("Pacote inválido");
        File temporary=new File(destination+".part");destination.getParentFile().mkdirs();HttpURLConnection c=connection(row.getString("url"));long count=0;
        try(InputStream in=c.getInputStream();FileOutputStream out=new FileOutputStream(temporary)){
            byte[] buffer=new byte[131072];int n,last=-1;while((n=in.read(buffer))!=-1){count+=n;if(count>size)throw new IOException("Tamanho do download não confere");out.write(buffer,0,n);int p=(int)(count*100/size);if(p!=last){progress.show("Baixando atualização",p);last=p;}}out.getFD().sync();
        }catch(Exception error){temporary.delete();throw error;}finally{c.disconnect();}
        if(count!=size||!hash(temporary).equals(expected)){temporary.delete();throw new IOException("Download incompleto ou corrompido");}
        if(destination.exists()&&!destination.delete())throw new IOException("Pacote em uso");if(!temporary.renameTo(destination))throw new IOException("Falha ao concluir download");return destination;
    }
    public static File child(File root,String path) throws IOException {
        if(path.contains("\\")||path.startsWith("/")||path.contains(":"))throw new IOException("Caminho inválido");
        File target=new File(root,path).getCanonicalFile();if(!target.getPath().startsWith(root.getCanonicalPath()+File.separator))throw new IOException("Caminho fora da pasta");return target;
    }
    public static List<File> saveFiles(File root) throws IOException {
        List<File> result=new ArrayList<>();collect(root,root,result,0);return result;
    }
    private static void collect(File root,File folder,List<File> result,int depth) throws IOException {
        if(depth>4)return;File[] files=folder.listFiles();if(files==null)return;
        for(File file:files){if(!file.getCanonicalPath().startsWith(root.getCanonicalPath()+File.separator))continue;if(file.isDirectory()){if(!file.getName().startsWith("."))collect(root,file,result,depth+1);}else if(file.getName().matches("(?i).+\\.(rxdata|rvdata2?|preview|dat|json)")){if(file.length()>64*1024*1024)throw new IOException("Save grande demais");result.add(file);}}
    }
    public static File backup(File saves,File directory,String channel) throws Exception {
        List<File> files=saveFiles(saves);if(files.isEmpty())return null;directory.mkdirs();
        Map<String,String> hashes=new TreeMap<>();for(File f:files)hashes.put(saves.toURI().relativize(f.toURI()).getPath(),hash(f));String snapshot=new JSONObject(hashes).toString();
        File[] prior=directory.listFiles(f->f.getName().matches("save-.*\\.zip"));if(prior!=null&&prior.length>0){Arrays.sort(prior,(a,b)->b.getName().compareTo(a.getName()));try(ZipFile zip=new ZipFile(prior[0]);InputStream in=zip.getInputStream(zip.getEntry("backup-info.json"))){JSONObject info=new JSONObject(new String(bounded(in,262144),StandardCharsets.UTF_8));if(snapshot.equals(info.optString("snapshot")))return prior[0];}catch(Exception ignored){}}
        String name=new SimpleDateFormat("yyyyMMdd-HHmmss-SSS",Locale.ROOT).format(new Date());File target=new File(directory,"save-"+name+".zip");
        File temp=new File(target+".tmp");try(ZipOutputStream zip=new ZipOutputStream(new FileOutputStream(temp))){
            JSONObject meta=new JSONObject();meta.put("date",new Date().toString());meta.put("channel",channel);meta.put("hashes",new JSONObject(hashes));meta.put("snapshot",snapshot);
            File info=new File(saves,"launcher-save-info.json");if(info.isFile())meta.put("save",new JSONObject(new String(read(info),StandardCharsets.UTF_8)));
            zip.putNextEntry(new ZipEntry("backup-info.json"));zip.write(meta.toString().getBytes(StandardCharsets.UTF_8));zip.closeEntry();
            for(File f:files){String relative=saves.toURI().relativize(f.toURI()).getPath();zip.putNextEntry(new ZipEntry("saves/"+relative));try(InputStream in=new FileInputStream(f)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)zip.write(b,0,n);}zip.closeEntry();}
        }catch(Exception error){temp.delete();throw error;}
        if(!temp.renameTo(target))throw new IOException("Falha ao concluir backup");
        File[] history=directory.listFiles(f->f.getName().matches("save-.*\\.zip"));if(history!=null){Arrays.sort(history,Comparator.comparing(File::getName).reversed());for(int i=5;i<history.length;i++)history[i].delete();}return target;
    }
    public static String describeBackup(File file){
        try(ZipFile zip=new ZipFile(file)){try(InputStream in=zip.getInputStream(zip.getEntry("backup-info.json"))){JSONObject meta=new JSONObject(new String(bounded(in,8192),StandardCharsets.UTF_8));long seconds=meta.optJSONObject("save")==null?0:meta.getJSONObject("save").optLong("play_seconds",0);return meta.optString("date")+" • "+seconds/3600+"h "+(seconds/60)%60+"min";}}
        catch(Exception ignored){return file.getName();}
    }
    public static void restore(File archive,File saves,File backups,String channel) throws Exception {
        // Validate/extract completely before touching existing slots.
        JSONObject hashes;try(ZipFile check=new ZipFile(archive);InputStream in=check.getInputStream(check.getEntry("backup-info.json"))){JSONObject info=new JSONObject(new String(bounded(in,262144),StandardCharsets.UTF_8));if(!channel.equals(info.optString("channel")))throw new IOException("Backup de outro canal");hashes=info.getJSONObject("hashes");}catch(Exception error){throw new IOException("Backup inválido",error);}
        File stage=new File(backups,"restore-"+System.nanoTime());stage.mkdirs();long total=0;int count=0;Set<String> names=new HashSet<>();
        try {
        try(ZipInputStream zip=new ZipInputStream(new FileInputStream(archive))){ZipEntry entry;while((entry=zip.getNextEntry())!=null){if(entry.isDirectory()||entry.getName().equals("backup-info.json"))continue;
            if(!entry.getName().startsWith("saves/")||!names.add(entry.getName().toLowerCase(Locale.ROOT))||++count>1000)throw new IOException("Backup inválido");
            String relative=entry.getName().substring(6);File f=child(stage,relative);byte[] b=bounded(zip,64*1024*1024);total+=b.length;if(total>128*1024*1024)throw new IOException("Backup grande demais");write(f,b);if(!hash(f).equals(hashes.optString(relative)))throw new IOException("Backup corrompido");
        }}
        if(count==0)throw new IOException("Backup sem saves");File safety=backup(saves,backups,channel);
        Map<File,byte[]> previous=new LinkedHashMap<>();List<File> added=new ArrayList<>();
        try{for(File file:saveFiles(stage)){File to=child(saves,stage.toURI().relativize(file.toURI()).getPath());if(to.exists())previous.put(to,readLarge(to));else added.add(to);write(to,readLarge(file));}}
        catch(Exception error){for(Map.Entry<File,byte[]> row:previous.entrySet())write(row.getKey(),row.getValue());for(File f:added)f.delete();throw error;}
        } finally{deleteTree(stage);}
    }
    private static byte[] readLarge(File file)throws IOException{try(InputStream in=new FileInputStream(file)){return bounded(in,64*1024*1024);}}
    private static void deleteTree(File root){File[] files=root.listFiles();if(files!=null)for(File f:files)deleteTree(f);root.delete();}
}
