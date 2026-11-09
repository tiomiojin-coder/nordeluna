import com.mkxpz.launcher.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.json.*;

public class TesterAccessTest {
    public static void main(String[] args)throws Exception{
        File root=new File(args[0]),encrypted=new File(root,"test-locked.bin"),plain=new File(root,"test-plain.bin"),target=new File(root,"java-unlocked.bin");
        JSONObject row=new JSONObject(new String(ClientFiles.read(new File(root,"test-row.json")),StandardCharsets.UTF_8));
        StringBuilder key=new StringBuilder();for(int i=0;i<32;i++)key.append(String.format("%02x",i));
        TesterAccess.unlock(encrypted,target,row,key.toString());if(!ClientFiles.hash(plain).equals(ClientFiles.hash(target)))throw new Exception("Decryption failed");
        boolean rejected=false;try{TesterAccess.unlock(encrypted,target,row,"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");}catch(Exception expected){rejected=true;}
        if(!rejected||!ClientFiles.hash(target).equals(ClientFiles.hash(plain)))throw new Exception("Wrong key damaged package");
        System.out.println("PASS: Android protected tester package and wrong-key rejection");
    }
}
