package com.mkxpz;

/** Run with javac/java; does not require an Android emulator. */
public final class GameSurfaceSizeTest {
    private static void expect(int w, int h, int mode, int percent, int ew, int eh) {
        int[] size = GameSurfaceSize.calculate(w, h, mode, percent);
        if (size[0] != ew || size[1] != eh)
            throw new AssertionError(w + "x" + h + ": " + size[0] + "x" + size[1]);
        if (size[0] > w || size[1] > h || size[0] < 1 || size[1] < 1)
            throw new AssertionError("Game extends beyond the measured container");
    }

    public static void main(String[] args) {
        expect(1560, 837, 0, 150, 1116, 837); // User screenshot's aspect/size.
        expect(1560, 837, 1, 150, 1560, 837);
        expect(1560, 837, 2, 150, 768, 576);
        expect(1920, 1080, 0, 150, 1440, 1080);
        expect(1080, 1920, 0, 150, 1080, 810); // Orientation/window change.
        expect(360, 240, 2, 250, 320, 240); // Must fit a small window.
        expect(2400, 1080, 2, 0, 512, 384); // Existing slider lower bound.
        expect(2400, 1080, 2, 999, 1280, 960); // Existing slider upper bound.
        expect(1000, 1000, 0, 150, 1000, 750);
        try {
            GameSurfaceSize.calculate(0, 0, 0, 150);
            throw new AssertionError("Unmeasured container was accepted");
        } catch (IllegalArgumentException expected) { }
        System.out.println("10 display geometry checks passed");
    }
}
