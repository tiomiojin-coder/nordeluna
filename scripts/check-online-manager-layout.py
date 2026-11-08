"""Exercise only the editors' own Tk widgets, offline and without saving drafts."""
import importlib.util
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


def check_window(root, name, sizes, expected_tabs):
    root.update()
    notebook = next(w for w in widgets(root) if isinstance(w, ttk.Notebook))
    assert len(notebook.tabs()) == expected_tabs, (name, len(notebook.tabs()))
    rows = []
    for size in sizes:
        root.geometry(size); root.update()
        for tab in notebook.tabs():
            notebook.select(tab); root.update(); page = root.nametowidget(tab)
            nested = [w for w in widgets(page) if isinstance(w, ttk.Notebook)]
            choices = [(notebook, tab)]
            for child in nested:
                choices.extend((child, value) for value in child.tabs())
            for current, value in choices:
                current.select(value); root.update(); chosen = root.nametowidget(value)
                row = dict(editor=name, window=size, tab=notebook.tab(tab, 'text'),
                    section=current.tab(value, 'text'), width=chosen.winfo_width(), height=chosen.winfo_height(),
                    requested_width=chosen.winfo_reqwidth(), requested_height=chosen.winfo_reqheight())
                rows.append(row)
                assert chosen.winfo_height() >= chosen.winfo_reqheight(), row
                assert chosen.winfo_width() >= chosen.winfo_reqwidth(), row
        assert notebook.winfo_rootx() + notebook.winfo_width() <= root.winfo_rootx() + root.winfo_width(), name
    for pending in root.tk.call('after', 'info'):
        root.after_cancel(pending)
    root.destroy()
    return rows


def main():
    editor = module('layout_editor', 'online-manager.py')
    staff = module('layout_staff', 'moderation-manager.py')
    # The production editor saves on refresh. Layout checks must preserve all drafts.
    editor.save_draft = lambda data: None
    rows = []
    tk.Tk.mainloop = lambda root: rows.extend(check_window(root, 'Central Online', ('1080x800', '940x720'), 10))
    editor.main()
    tk.Tk.mainloop = lambda root: rows.extend(check_window(root, 'Moderador', ('1080x760', '940x680'), 3))
    staff.main()
    output = ROOT / 'build/admin/layout-check.json'; output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS: ten owner tabs, all moderation sections and the staff window fit; no draft writes or network.')


if __name__ == '__main__':
    main()
