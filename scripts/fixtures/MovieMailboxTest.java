import com.mkxpz.launcher.MovieMailbox;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.UUID;

public class MovieMailboxTest {
    static int assertions;
    static void check(boolean value, String message) { assertions++; if (!value) throw new AssertionError(message); }
    static void write(File file, String value) throws Exception { Files.write(file.toPath(), value.getBytes(StandardCharsets.UTF_8)); }
    static String read(File file) throws Exception { return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8); }
    static class Fake implements MovieMailbox.Player {
        int starts, cancels; boolean resumed;
        MovieMailbox.Request request; MovieMailbox.Completion completion;
        public void start(MovieMailbox.Request r, MovieMailbox.Completion c) { starts++; request=r; completion=c; }
        public void setResumed(boolean value) { resumed=value; }
        public void cancel() { cancels++; }
    }
    static File directory;
    static String session;
    static String packet(String path) { return session+"\n"+path+"\n75\n1\n1.2\n0.35\n0.35\n0"; }
    static String submit(String body) throws Exception {
        String id=UUID.randomUUID().toString().replace("-", "");
        write(new File(directory,id+".request"),body); return id;
    }
    static String response(String id) throws Exception { return read(new File(directory,id+".response")); }
    public static void main(String[] args) throws Exception {
        File game=new File(args[0]); new File(game,"Movies").mkdirs();
        File video=new File(game,"Movies/cena a\u00e7\u00e3o.mp4"); write(video,"test media");
        Fake backend=new Fake(); MovieMailbox bridge=new MovieMailbox(game,backend);
        directory=new File(game,".nordeluna-movie-bridge"); session=read(new File(directory,"session"));
        check(read(new File(directory,"status")).startsWith("0\n"),"Initially paused");
        String id=submit(packet("Movies/"+video.getName())); bridge.tick();
        check(backend.starts==0,"Must not start in background");
        bridge.setResumed(true); bridge.tick();
        check(backend.starts==1 && backend.request.file.equals(video.getCanonicalFile()),"UTF-8 local path");
        check(backend.request.volume==75 && backend.request.skippable && backend.request.holdSeconds==1.2,"Options preserved");
        check(backend.request.entrance==0.35 && backend.request.exit==0.35,"Fade options preserved");
        bridge.tick(); check(backend.starts==1,"Single-flight player");
        bridge.setResumed(false); check(!backend.resumed,"Pause propagated");
        bridge.setResumed(true); check(backend.resumed,"Resume propagated");
        backend.completion.finish("OK\ncompleted"); check(response(id).equals("OK\ncompleted"),"Completion published");

        String[] bad={packet("Movies/../../outside.mp4"),packet("Data/cena.mp4"),packet("Movies/cena.exe"),
            packet("Movies/missing.mp4"),packet("Movies/"+video.getName()).replace("\n75\n","\n101\n"),
            packet("Movies/"+video.getName()).replace("\n1.2\n","\nNaN\n"),
            packet("Movies/"+video.getName()).replace("\n1.2\n","\n0\n"),
            packet("Movies/"+video.getName()).replace(session,"wrong-session"),"x".repeat(9000)};
        for(String body:bad){id=submit(body);bridge.tick();check(response(id).startsWith("ERROR\n"),"Invalid request accepted");}
        check(backend.starts==1,"Invalid data reached decoder");

        id=submit(packet("Movies/"+video.getName()));
        write(new File(directory,id+".cancel"),"1");bridge.tick();
        check(response(id).startsWith("ERROR\n"),"Pre-start cancellation");
        check(backend.starts==1,"Cancelled movie started");
        id=submit(packet("Movies/"+video.getName()));bridge.tick();
        MovieMailbox.Completion old=backend.completion;
        write(new File(directory,id+".cancel"),"1");bridge.tick();
        check(backend.cancels==1 && response(id).startsWith("ERROR\n"),"Active cancellation");
        String next=submit(packet("Movies/"+video.getName()));bridge.tick();
        old.finish("OK\ncompleted");
        check(!new File(directory,next+".response").exists(),"Late callback completed newer job");
        backend.completion.finish("OK\nskipped");check(response(next).equals("OK\nskipped"),"Skipped response");
        id=submit(packet("Movies/"+video.getName()));bridge.tick();bridge.close();bridge.close();
        check(response(id).startsWith("ERROR\n"),"Shutdown did not finish pending playback");
        check(read(new File(directory,"status")).startsWith("0\n"),"Shutdown status");
        System.out.println("PASS: "+assertions+" movie mailbox checks; UTF-8, options, lifecycle, validation, cancellation and late callbacks");
    }
}
