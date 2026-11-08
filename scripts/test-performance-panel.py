"""Run actual SideMenu performance methods with lightweight Android view doubles."""
import importlib.util
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def main(engine):
    spec = importlib.util.spec_from_file_location("touch", Path(__file__).with_name("test-touch-controls.py"))
    touch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(touch)
    main_dir = engine / "android/app/src/main"
    source = (main_dir / "java/com/mkxpz/launcher/SideMenu.java").read_text(encoding="utf-8")
    strings = {node.attrib["name"]: node.text for node in ET.parse(main_dir / "res/values/strings.xml").getroot() if node.tag == "string"}
    names = ["performance_" + name for name in ("particles", "shadows", "decorations", "off", "reduced", "normal", "save_error")]
    assert all(strings[name] for name in names)
    assert "cyclePerformanceOption(selected)" in source
    methods = "\n".join(touch.method(source, signature) for signature in (
        "public void setGamePath(", "private void refreshPerformanceOptions()", "private void cyclePerformanceOption("))
    harness = r'''
import java.io.File;
import com.mkxpz.launcher.PerformanceOptions;
public class PerformancePanelTest {
    static class R { static class string { CONSTANTS } }
    static class Context { String getString(int id) { return Integer.toString(id); } }
    static class Button {
        String text; boolean enabled;
        void setText(String s) {text=s;}
        void setEnabled(boolean value) {enabled=value;}
    }
    static class Toast {
        static final int LENGTH_SHORT=0; static int shown;
        static Toast makeText(Context c,int message,int duration) {return new Toast();}
        void show() {shown++;}
    }
    static class Panel {
        File mPerformanceDirectory; Context mContext=new Context();
        Button[] mPerformanceButtons={new Button(),new Button(),new Button()};
        Button mGamePathView=new Button();
        METHODS
    }
    static void check(boolean value,String message) {if(!value)throw new AssertionError(message);}
    public static void main(String[] args) {
        Panel p=new Panel(); p.setGamePath(null);
        check(!p.mPerformanceButtons[0].enabled,"unprepared game exposed writable options");
        p.setGamePath(args[0]);
        check(p.mPerformanceButtons[2].enabled,"prepared directory stayed disabled");
        p.cyclePerformanceOption(0);
        int[] values=PerformanceOptions.load(new File(args[0]));
        check(values[0]==1 && values[1]==2 && values[2]==2,"particles changed other options");
        p.cyclePerformanceOption(0); values=PerformanceOptions.load(new File(args[0]));
        // Windows filesystems may reject atomic replacement; the last good value must survive.
        if(Toast.shown==0) {
            check(values[0]==0,"second click did not disable particles");
            p.cyclePerformanceOption(0);
            check(PerformanceOptions.load(new File(args[0]))[0]==2,"third click did not restore normal");
        } else check(values[0]==1,"failed replacement destroyed previous setting");
        PerformanceOptions.save(new File(args[1]),new int[]{0,1,2});
        p.setGamePath(args[1]);
        check(p.mPerformanceButtons[0].text.endsWith(":"+" "+R.string.performance_off),"external Ruby setting not reflected");
        p.setGamePath(new File(args[0],"missing").getPath());
        int before=Toast.shown; p.cyclePerformanceOption(1);
        check(Toast.shown==before+1 && !p.mPerformanceButtons[1].enabled,"write failure hidden from player");
        System.out.println("Performance panel: independent levels, reload, missing directory and write failure passed.");
    }
}
'''
    harness = harness.replace("CONSTANTS", " ".join(f"static final int {name}={i};" for i, name in enumerate(names)))
    harness = harness.replace("METHODS", methods)
    with tempfile.TemporaryDirectory(prefix="nordeluna-performance-panel-") as tmp:
        directory = Path(tmp)
        (directory / "game1").mkdir()
        (directory / "game2").mkdir()
        test = directory / "PerformancePanelTest.java"
        test.write_text(harness, encoding="utf-8")
        helper = Path(__file__).resolve().parents[1] / "android/PerformanceOptions.java"
        subprocess.run(["javac", "-encoding", "UTF-8", "-d", tmp, str(helper), str(test)], check=True)
        subprocess.run(["java", "-cp", tmp, "PerformancePanelTest", str(directory / "game1"), str(directory / "game2")], check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
