"""Restricted Windows moderation window: no Discloud credentials or other tools."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('staff_moderation_panel', ROOT / 'scripts/moderation-panel.py')
moderation = importlib.util.module_from_spec(spec); spec.loader.exec_module(moderation)


def main():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk(); root.title('Moderacao Nordeluna 0.10.0')
    root.geometry('1080x760'); root.minsize(940, 680); root.configure(bg='#0c1726')
    style = ttk.Style(root); style.theme_use('clam')
    style.configure('TFrame', background='#142339')
    style.configure('TLabel', background='#142339', foreground='#e8f2fa', font=('Segoe UI', 10))
    style.configure('TButton', padding=7); style.configure('Treeview', rowheight=27)
    style.configure('TNotebook.Tab', padding=(10, 7))
    outer = ttk.Frame(root, padding=18); outer.pack(fill='both', expand=True)
    ttk.Label(outer, text='Moderacao Nordeluna', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
    ttk.Label(outer, text='Acesso exclusivo de moderador. A chave fica somente na memoria desta janela.').pack(anchor='w', pady=(4, 10))
    auth = ttk.Frame(outer); auth.pack(fill='x', pady=5)
    ttk.Label(auth, text='Chave de moderador:').pack(side='left')
    key = ttk.Entry(auth, show='*', width=43); key.pack(side='left', padx=8)
    status = tk.StringVar(value='Entre com a chave fornecida pelo proprietario. Nenhuma consulta e automatica.')
    active = {'key': ''}
    def secret():
        return active['key'] or key.get().strip()
    def session(actor):
        login.state(['disabled']); logout.state(['!disabled'])
    def forget():
        active['key'] = ''; key.state(['!disabled']); key.delete(0, 'end')
        login.state(['!disabled']); logout.state(['disabled'])
    def enter():
        if panel.busy or panel.connected:
            return
        if moderation.STAFF_KEY.fullmatch(key.get().strip()):
            active['key'] = key.get().strip(); key.delete(0, 'end'); key.state(['disabled'])
            login.state(['disabled'])
            if not panel.run(dict(action='session'), session=True):
                forget()
        else:
            status.set('Informe uma chave de moderador valida no campo mascarado.')
    def leave():
        if panel.busy:
            status.set('Aguarde a consulta atual antes de sair.'); return
        forget(); panel.set_connected(False); status.set('Sessao encerrada. Chave removida da janela.')
    login = ttk.Button(auth, text='Entrar', command=enter); login.pack(side='left')
    logout = ttk.Button(auth, text='Sair', command=leave); logout.pack(side='left', padx=6); logout.state(['disabled'])
    key.bind('<Return>', lambda event: enter())
    ttk.Label(outer, text='HTTPS: nordeluna-online.discloud.dev/moderation', foreground='#7bdce2').pack(anchor='w', pady=5)
    body = ttk.Frame(outer); body.pack(fill='both', expand=True, pady=7)
    panel = moderation.ModerationPanel(body, root, status, secret, moderation.StaffClient(),
        on_session=session, on_auth_error=forget)
    ttk.Label(outer, textvariable=status, wraplength=890).pack(anchor='w', pady=(10, 0))
    def close():
        panel.close(); forget(); root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    root.mainloop()


if __name__ == '__main__':
    main()
