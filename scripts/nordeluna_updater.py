"""Interactive Windows launcher; opening the window never publishes anything."""
import os
import queue
import re
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import updater_core as core


class Updater:
    def __init__(self, window):
        self.window = window
        self.settings = core.load_settings()
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        window.title("Atualizar Nordeluna — Android")
        window.geometry("850x650")
        window.minsize(700, 560)
        window.configure(bg="#101827")
        style = ttk.Style(window)
        style.theme_use("clam")
        style.configure("TFrame", background="#101827")
        style.configure("TLabel", background="#101827", foreground="#edf3ff", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=9)
        style.configure("Publish.TButton", font=("Segoe UI", 12, "bold"), padding=13)
        frame = ttk.Frame(window, padding=22)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(10, weight=1)
        ttk.Label(frame, text="🌙 Atualizar Nordeluna", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Salve e compile o jogo no editor antes de começar. Feche o editor durante a preparação.",
                  wraplength=760).grid(row=1, column=0, sticky="w", pady=(6, 16))
        self.source = tk.StringVar(value=self.settings.get("source", str(core.DEFAULT_GAME)))
        self.downloads = tk.StringVar(value=self.settings.get("downloads", str(core.ROOT / "build-android/APKs")))
        self.inputs = []
        self.folder_row(frame, 2, "Pasta do jogo (contém Game.ini)", self.source)
        self.folder_row(frame, 4, "Salvar APKs em", self.downloads)
        self.revision = tk.StringVar()
        self.refresh_revision()
        ttk.Label(frame, textvariable=self.revision).grid(row=6, column=0, sticky="w", pady=(10, 6))
        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, sticky="ew", pady=8)
        self.publish = ttk.Button(buttons, text="Gerar novo APK e enviar", style="Publish.TButton", command=self.start)
        self.publish.pack(side="left")
        self.resume = ttk.Button(buttons, text="Acompanhar / retomar envio", command=lambda: self.start(True))
        self.resume.pack(side="left", padx=8)
        self.cancel = ttk.Button(buttons, text="Parar", command=self.cancel_task, state="disabled")
        self.cancel.pack(side="right")
        self.status = tk.StringVar(value="Pronto. Nada será enviado até você clicar em Gerar novo APK e enviar.")
        ttk.Label(frame, textvariable=self.status, wraplength=760).grid(row=8, column=0, sticky="w", pady=6)
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=9, column=0, sticky="ew", pady=(0, 12))
        logs = ttk.Frame(frame)
        logs.grid(row=10, column=0, sticky="nsew")
        self.log = tk.Text(logs, bg="#080f1c", fg="#c8dbef", insertbackground="white", font=("Consolas", 10),
                           wrap="word", state="disabled", relief="flat", height=10)
        scrollbar = ttk.Scrollbar(logs, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        footer = ttk.Frame(frame)
        footer.grid(row=11, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(footer, text="Abrir GitHub", command=self.open_github).pack(side="left")
        self.open_apk = ttk.Button(footer, text="Abrir pasta do APK", command=self.open_downloads)
        self.open_apk.pack(side="left", padx=8)
        ttk.Button(footer, text="Ajuda", command=self.help).pack(side="right")
        window.protocol("WM_DELETE_WINDOW", self.close)
        window.after(100, self.poll)

    def folder_row(self, frame, row, label, variable):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=(5, 3))
        line = ttk.Frame(frame)
        line.grid(row=row + 1, column=0, sticky="ew")
        entry = ttk.Entry(line, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True)
        def browse():
            folder = filedialog.askdirectory(parent=self.window, initialdir=variable.get())
            if folder:
                variable.set(folder)
        button = ttk.Button(line, text="Escolher…", command=browse)
        button.pack(side="right", padx=(8, 0))
        self.inputs.extend((entry, button))

    def refresh_revision(self):
        try:
            patch = (core.ROOT / "android/nordeluna.patch").read_text(encoding="utf-8")
            code = re.search(r"(?m)^\+\s*versionCode\s+(\d+)", patch).group(1)
            name = re.search(r'(?m)^\+\s*versionName\s+"([^"]+)"', patch)
            self.revision.set(f"Android {name.group(1) if name else ''} • revisão local {code} • a próxima atualização aumenta a revisão")
        except (OSError, AttributeError):
            self.revision.set("Não foi possível ler a revisão local do APK.")

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", str(text) + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self, resume=False):
        if self.busy:
            return
        self.settings.update(source=self.source.get().strip(), downloads=self.downloads.get().strip())
        if not self.settings["source"] or not self.settings["downloads"]:
            messagebox.showerror("Pastas necessárias", "Escolha a pasta do jogo e a pasta para os APKs.")
            return
        self.stop.clear()
        self.busy = True
        for widget in (*self.inputs, self.publish, self.resume):
            widget.configure(state="disabled")
        self.cancel.configure(state="normal")
        self.progress.start(12)
        self.status.set("Iniciando…")
        self.append("Acompanhando último envio…" if resume else "Iniciando uma nova atualização do jogo…")
        def worker():
            try:
                # The lock in update serializes all writes, including persisted settings.
                core.update(self.settings, self.stop, lambda kind, value: self.events.put((kind, value)), resume=resume)
                self.events.put(("done", "Concluído. APK disponível para instalar ou compartilhar."))
            except core.Cancelled as exc:
                self.events.put(("stopped", str(exc)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.status.set(value)
            elif kind == "log":
                self.append(value)
            elif kind == "url":
                self.settings["last_run_url"] = value
            elif kind == "apk":
                self.settings["last_apk"] = value
                self.append("APK: " + value)
            elif kind in ("done", "error", "stopped"):
                self.busy = False
                self.progress.stop()
                for widget in (*self.inputs, self.publish, self.resume):
                    widget.configure(state="normal")
                self.cancel.configure(state="disabled")
                self.status.set(value)
                self.append(value)
                self.refresh_revision()
                if kind == "error":
                    messagebox.showerror("Atualização interrompida", value, parent=self.window)
        self.window.after(100, self.poll)

    def cancel_task(self):
        self.stop.set()
        self.status.set("Parando no próximo ponto seguro. A build já enviada continua no GitHub.")
        self.cancel.configure(state="disabled")

    def open_github(self):
        webbrowser.open(self.settings.get("last_run_url", "https://github.com/" + core.REPOSITORY + "/actions"))

    def open_downloads(self):
        path = Path(self.settings.get("last_apk", "")).parent if self.settings.get("last_apk") else Path(self.downloads.get())
        if path.is_dir():
            os.startfile(str(path))
        else:
            messagebox.showinfo("APKs", "A pasta será criada quando o APK for baixado.")

    def help(self):
        os.startfile(str(core.ROOT / "docs/atualizador-windows.md"))

    def close(self):
        if self.busy:
            messagebox.showinfo("Operação em andamento", "Clique em Parar e aguarde antes de fechar. Uma build já enviada não será cancelada.")
            return
        self.window.destroy()


def main():
    window = tk.Tk()
    if "--self-check" in sys.argv:
        window.withdraw()
        Updater(window)
        window.update_idletasks()
        window.destroy()
        print("Interface verificada. Nenhum pacote, commit, envio ou build foi criado.")
        return
    Updater(window)
    window.mainloop()


if __name__ == "__main__":
    main()
