package com.mkxpz.launcher;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/** Device-local visual budgets shared with the game's Ruby options menu. */
public final class PerformanceOptions {
    public static final String FILE_NAME = ".nordeluna-performance.cfg";
    private static final String[] KEYS = {"particles", "shadows", "decorations"};

    private PerformanceOptions() { }

    public static int[] load(File directory) {
        int[] values = {2, 2, 2};
        if (directory == null) return values;
        File file = new File(directory, FILE_NAME);
        try {
            if (!file.isFile() || file.length() > 1024) return values;
            int[] parsed = {2, 2, 2};
            boolean supported = false;
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.equals("version=1")) supported = true;
                    for (int i = 0; i < KEYS.length; i++) {
                        if (line.matches(KEYS[i] + "=[012]")) parsed[i] = line.charAt(line.length() - 1) - '0';
                    }
                }
            }
            return supported ? parsed : values;
        } catch (Exception ignored) {
            return values;
        }
    }

    public static boolean save(File directory, int[] values) {
        if (directory == null || !directory.isDirectory() || values == null || values.length != 3) return false;
        StringBuilder text = new StringBuilder("version=1\n");
        for (int i = 0; i < KEYS.length; i++) {
            if (values[i] < 0 || values[i] > 2) return false;
            text.append(KEYS[i]).append('=').append(values[i]).append('\n');
        }
        File temporary = new File(directory, FILE_NAME + ".tmp");
        try {
            try (FileOutputStream output = new FileOutputStream(temporary)) {
                output.write(text.toString().getBytes(StandardCharsets.UTF_8));
                output.getFD().sync();
            }
            if (!temporary.renameTo(new File(directory, FILE_NAME))) {
                temporary.delete();
                return false;
            }
            return true;
        } catch (Exception ignored) {
            temporary.delete();
            return false;
        }
    }
}
