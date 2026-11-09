package com.mkxpz.launcher;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.crypto.*;
import javax.crypto.spec.*;
import org.json.*;

/** The public catalogue contains no usable test APK or unlock key. */
public final class TesterAccess {
    public static final String ENDPOINT="https://nordeluna-online.discloud.dev/api";
    public static JSONObject call(JSONObject body)throws Exception{
        body.put("protocol",1);HttpURLConnection c=(HttpURLConnection)new URL(ENDPOINT).openConnection();
        c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(30000);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");
        try{try(OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}
            int status=c.getResponseCode();InputStream input=status==200?c.getInputStream():c.getErrorStream();
            JSONObject result;try(InputStream in=input){if(in==null)throw new IOException("Servidor indisponível");result=new JSONObject(new String(ClientFiles.bounded(in,262144),StandardCharsets.UTF_8));}
            if(status!=200||!result.optBoolean("ok"))throw new IOException(result.optString("error","Acesso de tester recusado"));return result;
        }finally{c.disconnect();}
    }
    public static JSONObject authorize(JSONObject credentials)throws Exception{return call(new JSONObject().put("action","tester_access").put("tester",credentials));}
    public static JSONObject redeem(String code)throws Exception{return call(new JSONObject().put("action","tester_redeem").put("code",code.trim().toUpperCase(Locale.ROOT)).put("device",UUID.randomUUID().toString().replace("-",""))).getJSONObject("credentials");}
    public static void unlock(File encrypted,File target,JSONObject row,String key)throws Exception{
        if(!key.matches("[0-9a-f]{64}")||!row.optBoolean("encrypted")||!ClientFiles.hash(encrypted).equals(row.getString("sha256")))throw new IOException("Pacote protegido inválido");
        JSONObject plain=row.getJSONObject("plain");long expected=plain.getLong("size");if(expected<1||expected>3L*1024*1024*1024)throw new IOException("Tamanho inválido");
        File temp=new File(target+".unlocking");
        try{try(FileInputStream input=new FileInputStream(encrypted);FileOutputStream output=new FileOutputStream(temp)){
            byte[] iv=new byte[16];int pos=0,n;while(pos<16&&(n=input.read(iv,pos,16-pos))>0)pos+=n;if(pos!=16)throw new IOException("Pacote incompleto");
            byte[] secret=new byte[32];for(int i=0;i<32;i++)secret[i]=(byte)Integer.parseInt(key.substring(i*2,i*2+2),16);
            Cipher cipher=Cipher.getInstance("AES/CBC/PKCS5Padding");cipher.init(Cipher.DECRYPT_MODE,new SecretKeySpec(secret,"AES"),new IvParameterSpec(iv));
            long count=0;try(CipherInputStream decoded=new CipherInputStream(input,cipher)){byte[] b=new byte[131072];while((n=decoded.read(b))!=-1){count+=n;if(count>expected)throw new IOException("Pacote maior que o esperado");output.write(b,0,n);}}
            if(count!=expected)throw new IOException("Pacote incompleto");output.getFD().sync();
        }
        if(!ClientFiles.hash(temp).equals(plain.getString("sha256")))throw new IOException("Conteúdo de testes corrompido");
        if(target.exists()&&!target.delete())throw new IOException("Arquivo em uso");if(!temp.renameTo(target))throw new IOException("Falha ao concluir pacote");
        }finally{temp.delete();}
    }
}
