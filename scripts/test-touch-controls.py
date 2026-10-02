"""Exercise the patched Java methods with input/view doubles (no Android device).

Usage: python scripts/test-touch-controls.py path/to/patched/mkxp-z
The full Android build separately validates SDK types and integration.
"""
import subprocess
import sys
import tempfile
from pathlib import Path


def method(source, signature):
    start = source.index(signature)
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main(root):
    java = root / "android/app/src/main/java/com/mkxpz"
    activity = (java / "MainActivity.java").read_text(encoding="utf-8")
    gamepad = (java / "gamepad/Gamepad.java").read_text(encoding="utf-8")
    harness = r'''
public class TouchControlsTest {
    static class Build {
        static class VERSION { static int SDK_INT = 35; }
        static class VERSION_CODES { static final int Q = 29; }
    }
    static class InputDevice {
        static final int SOURCE_GAMEPAD = 0x401, SOURCE_JOYSTICK = 0x1000010;
        boolean virtual, external; int sources;
        InputDevice(boolean v, boolean e, int s) { virtual=v; external=e; sources=s; }
        boolean isVirtual() { return virtual; }
        boolean isExternal() {
            if (Build.VERSION.SDK_INT < 29) throw new AssertionError("API 29 called on old Android");
            return external;
        }
        boolean supportsSource(int source) { return (sources & source) == source; }
    }
    static class View {
        static final int VISIBLE=0, GONE=8;
        int visibility=VISIBLE; float alpha=1;
        void clearAnimation() {}
        void setVisibility(int v) { visibility=v; }
        void setAlpha(float a) { alpha=a; }
    }
    static class KeyEvent {
        static final int KEYCODE_BACK=4, KEYCODE_VOLUME_UP=24, KEYCODE_VOLUME_DOWN=25,
            KEYCODE_VOLUME_MUTE=164, KEYCODE_HEADSETHOOK=79;
        int getKeyCode() { return 66; }
    }
    static class Parent { boolean dispatchKeyEvent(KeyEvent e) { return false; } }
    static class Pad {
        boolean mInvisible;
        View mGamepadLayout = new View();
        boolean processGamepadEvent(KeyEvent e) { return false; }
        // PAD_METHODS
    }
    static class Activity extends Parent {
        Pad mGamepad = new Pad();
        boolean mGamepadInvisible, mAutoHideTouchControls = true;
        boolean mPhysicalControllerConnected, mTouchControlsEnabled = true;
        boolean isAndroidTV() { return false; }
        boolean isChromebook() { return false; }
        boolean isControllerEvent(KeyEvent e) { return false; }
        void observeControllerKey(KeyEvent e) {}
        // ACTIVITY_METHODS
    }
    static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        Activity a = new Activity();
        check(!a.isPhysicalController(null), "missing device");
        check(!a.isPhysicalController(new InputDevice(true,true,0x1000411)), "virtual device");
        check(!a.isPhysicalController(new InputDevice(false,false,0x1000411)), "phone input driver must not hide touch");
        check(!a.isPhysicalController(new InputDevice(false,true,0x101)), "keyboard shares source class bits");
        check(!a.isPhysicalController(new InputDevice(false,true,0x1002)), "touchscreen is not a controller");
        check(a.isPhysicalController(new InputDevice(false,true,0x401)), "external gamepad");
        check(a.isPhysicalController(new InputDevice(false,true,0x1000010)), "external joystick");
        Build.VERSION.SDK_INT = 28;
        check(a.isPhysicalController(new InputDevice(false,true,0x401)), "old Android remains supported");
        Build.VERSION.SDK_INT = 35;
        a.dispatchKeyEvent(new KeyEvent());
        check(!a.mGamepadInvisible && !a.mGamepad.mInvisible, "system/keyboard key must not hide controls");
        a.mPhysicalControllerConnected=true;
        a.refreshTouchControlsVisibility();
        check(a.mGamepadInvisible && a.mGamepad.mGamepadLayout.visibility==View.GONE, "connected controller hides touch");
        a.mPhysicalControllerConnected=false;
        a.refreshTouchControlsVisibility();
        check(!a.mGamepadInvisible && a.mGamepad.mGamepadLayout.visibility==View.VISIBLE, "disconnect restores touch");
        a.mPhysicalControllerConnected=true;
        a.mAutoHideTouchControls=false;
        a.refreshTouchControlsVisibility();
        check(!a.mGamepadInvisible, "user can disable auto-hide");
        a.mTouchControlsEnabled=false;
        a.refreshTouchControlsVisibility();
        check(a.mGamepadInvisible, "explicit user preference respected");
        Pad p = new Pad();
        for (int i=0; i<100; i++) { p.hideView(); p.showView(); }
        check(!p.mInvisible && p.mGamepadLayout.visibility==View.VISIBLE && p.mGamepadLayout.alpha==1,
            "rapid hide/show leaves controls visible");
        p.mGamepadLayout=null;
        p.hideView(); check(p.mInvisible, "hide before attachment");
        p.showView(); check(!p.mInvisible, "show before attachment");
        System.out.println("Touch controls: device detection, keys, reconnect and visibility checks passed.");
    }
}
'''
    harness = harness.replace("// PAD_METHODS", "\n".join(method(gamepad, name) for name in (
        "public void showView()", "public void hideView()")))
    harness = harness.replace("// ACTIVITY_METHODS", "\n".join(method(activity, name) for name in (
        "private boolean isPhysicalController(", "public boolean dispatchKeyEvent(",
        "private void refreshTouchControlsVisibility()")))
    with tempfile.TemporaryDirectory(prefix="nordeluna-touch-tests-") as directory:
        source = Path(directory) / "TouchControlsTest.java"
        source.write_text(harness, encoding="utf-8")
        subprocess.run(["javac", "-encoding", "UTF-8", "-d", directory, str(source)], check=True)
        subprocess.run(["java", "-cp", directory, "TouchControlsTest"], check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
