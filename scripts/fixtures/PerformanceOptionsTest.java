import com.mkxpz.launcher.PerformanceOptions;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;

public class PerformanceOptionsTest {
    static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
    public static void main(String[] args) throws Exception {
        File directory = new File(args[0]);
        check(Arrays.equals(PerformanceOptions.load(directory), new int[]{2,2,2}), "defaults");
        check(PerformanceOptions.save(directory, new int[]{0,1,2}), "initial save");
        check(Arrays.equals(PerformanceOptions.load(directory), new int[]{0,1,2}), "independent levels");
        File file = new File(directory, PerformanceOptions.FILE_NAME);
        String content = new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        check(content.equals("version=1\nparticles=0\nshadows=1\ndecorations=2\n"), "Ruby-compatible format");
        boolean replaced = PerformanceOptions.save(directory, new int[]{2,0,1});
        // Android/Linux rename replaces atomically; a filesystem that refuses
        // replacement must leave the last valid settings intact and report it.
        check(Arrays.equals(PerformanceOptions.load(directory), replaced ? new int[]{2,0,1} : new int[]{0,1,2}), "atomic replace/failure");
        check(!PerformanceOptions.save(directory, new int[]{-1,0,1}), "invalid value accepted");
        Files.write(file.toPath(), "version=1\nparticles=9\nshadows=0\ndecorations=1\n".getBytes(StandardCharsets.UTF_8));
        check(Arrays.equals(PerformanceOptions.load(directory), new int[]{2,0,1}), "bad entry must not corrupt other levels");
        Files.write(file.toPath(), "version=7\nparticles=0\n".getBytes(StandardCharsets.UTF_8));
        check(Arrays.equals(PerformanceOptions.load(directory), new int[]{2,2,2}), "unknown version");
        Files.write(file.toPath(), new byte[2048]);
        check(Arrays.equals(PerformanceOptions.load(directory), new int[]{2,2,2}), "size limit");
        check(!PerformanceOptions.save(null, new int[]{0,0,0}), "missing directory");
        System.out.println("PASS: device preferences, independent levels, atomic replacement, corrupt-file fallback");
    }
}
