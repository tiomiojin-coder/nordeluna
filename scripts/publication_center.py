"""Simple publisher for PC, Android and server content. No action on startup."""
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

import publication_center_core as backend


class Publisher:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.stop=threading.Event();self.busy=False;self.plan=None
        root.title('Publicar Nordeluna • PC + Android');root.geometry('1040x840');root.minsize(850,700)
        root.configure(bg='#0b111d')
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('TFrame',background='#14202f');style.configure('TLabel',background='#14202f',foreground='#ebf2fa',font=('Segoe UI',10))
        style.configure('TButton',padding=(12,9));style.configure('Primary.TButton',font=('Segoe UI',11,'bold'),background='#64e0dc',foreground='#0b111d')
        style.configure('Treeview',rowheight=27);style.configure('TCombobox',padding=5)
        box=ttk.Frame(root,padding=22);box.pack(fill='both',expand=True);box.columnconfigure(0,weight=1);box.rowconfigure(9,weight=1)
        ttk.Label(box,text='Publicar Nordeluna',font=('Segoe UI',24,'bold'),foreground='#64e0dc').grid(row=0,column=0,sticky='w')
        ttk.Label(box,text='Uma publicacao para PC e Android. O programa escolhe entre pacote pelo servidor e versao completa.',wraplength=940).grid(row=1,column=0,sticky='w',pady=(5,14))
        self.source=tk.StringVar(value=str(backend.core.load_settings().get('source',backend.core.DEFAULT_GAME)))
        line=ttk.Frame(box);line.grid(row=2,column=0,sticky='ew');line.columnconfigure(1,weight=1)
        ttk.Label(line,text='Pasta do jogo:').grid(row=0,column=0,padx=(0,10));ttk.Entry(line,textvariable=self.source).grid(row=0,column=1,sticky='ew');ttk.Button(line,text='Escolher',command=self.choose).grid(row=0,column=2,padx=6)
        inputs=ttk.Frame(box);inputs.grid(row=3,column=0,sticky='ew',pady=12);inputs.columnconfigure(1,weight=1)
        self.title=tk.StringVar(value='Novidades de Nordeluna');self.audience=tk.StringVar(value='Testers');self.version=tk.StringVar(value='0')
        ttk.Label(inputs,text='Titulo:').grid(row=0,column=0,sticky='w');ttk.Entry(inputs,textvariable=self.title).grid(row=0,column=1,sticky='ew',padx=8)
        ttk.Combobox(inputs,textvariable=self.audience,values=['Testers','Todos'],state='readonly',width=14).grid(row=0,column=2)
        ttk.Label(inputs,text='Revisao (0 = automatica):').grid(row=1,column=0,sticky='w',pady=8);ttk.Entry(inputs,textvariable=self.version,width=10).grid(row=1,column=1,sticky='w',padx=8)
        ttk.Label(box,text='Novidades para os jogadores:').grid(row=4,column=0,sticky='w')
        self.notes=tk.Text(box,height=3,bg='#0b111d',fg='#ebf2fa',insertbackground='white',relief='flat',wrap='word',font=('Segoe UI',10));self.notes.grid(row=5,column=0,sticky='ew',pady=(5,10))
        auth=ttk.Frame(box);auth.grid(row=6,column=0,sticky='ew');ttk.Label(auth,text='Token Discloud:').pack(side='left')
        self.token=ttk.Entry(auth,show='*',width=40);self.token.pack(side='left',padx=8);ttk.Label(auth,text='Somente nesta janela. Nunca e salvo.').pack(side='left')
        actions=ttk.Frame(box);actions.grid(row=7,column=0,sticky='ew',pady=12)
        self.inspect=ttk.Button(actions,text='1. Conferir alteracoes',command=lambda:self.work('analyze'));self.inspect.pack(side='left')
        self.send=ttk.Button(actions,text='2. Publicar para PC e Android',style='Primary.TButton',command=self.publish,state='disabled');self.send.pack(side='left',padx=8)
        self.retake=ttk.Button(actions,text='Retomar',command=lambda:self.work('resume'));self.retake.pack(side='left')
        self.cancel=ttk.Button(actions,text='Parar',command=self.cancel_task,state='disabled');self.cancel.pack(side='right')
        self.summary=tk.StringVar(value='Salve e compile o jogo antes de conferir. Nada sera enviado ao abrir este programa.')
        ttk.Label(box,textvariable=self.summary,wraplength=940,foreground='#e8c780').grid(row=8,column=0,sticky='ew',pady=(0,8))
        table=ttk.Frame(box);table.grid(row=9,column=0,sticky='nsew')
        self.tree=ttk.Treeview(table,columns=('kind','path'),show='headings',height=8);self.tree.heading('kind',text='Alteracao');self.tree.heading('path',text='Arquivo');self.tree.column('kind',width=145,stretch=False);self.tree.column('path',width=700)
        scroll=ttk.Scrollbar(table,command=self.tree.yview);self.tree.configure(yscrollcommand=scroll.set);self.tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.status=tk.StringVar(value='Pronto.');ttk.Label(box,textvariable=self.status,wraplength=940).grid(row=10,column=0,sticky='ew',pady=(10,5))
        self.bar=ttk.Progressbar(box,mode='indeterminate');self.bar.grid(row=11,column=0,sticky='ew')
        footer=ttk.Frame(box);footer.grid(row=12,column=0,sticky='ew',pady=(12,0))
        ttk.Button(footer,text='Missoes, loja e presentes',command=self.online).pack(side='left')
        ttk.Button(footer,text='Atualizar servidor',command=self.server).pack(side='left',padx=8)
        ttk.Button(footer,text='Ajuda',command=lambda:os.startfile(str(backend.ROOT/'docs/publicador-pc-android.md'))).pack(side='right')
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(120,self.poll)

    def choose(self):
        if self.busy:return
        path=filedialog.askdirectory(parent=self.root,initialdir=self.source.get())
        if path:
            self.source.set(path);self.plan=None;self.send.configure(state='disabled')
            settings=backend.core.load_settings();settings['source']=path;backend.core.save_settings(settings)

    def online(self):
        if not self.busy:subprocess.Popen([sys.executable.replace('python.exe','pythonw.exe'),str(backend.ROOT/'scripts/online-manager.py')],cwd=backend.ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    def server(self):
        if self.busy:return
        if messagebox.askyesno('Atualizar o servidor existente','Criar um backup e instalar o servidor local atual no Discloud? As partidas online poderao ser interrompidas durante a reinicializacao.',parent=self.root):self.work('server')

    def publish(self):
        if self.busy or not self.plan:return
        if self.source.get().strip()!=self.plan['source']:self.plan=None;self.send.configure(state='disabled');self.status.set('A pasta mudou. Confira novamente.');return
        kind='Pacote rapido pelo servidor' if self.plan['mode']=='content' else 'Versao completa: commit, envio ao GitHub, duas builds e catalogos'
        if messagebox.askyesno('Publicar para '+self.audience.get(),kind+'\n\nPublico: '+self.audience.get()+'\nConfira os arquivos listados. Publicar agora?',parent=self.root):self.work('publish')

    def work(self,action):
        if self.busy:return
        secret=self.token.get().strip()
        if action!='analyze' and not secret:messagebox.showerror('Token necessario','Informe o token Discloud no campo mascarado.',parent=self.root);return
        title=self.title.get().strip();notes=self.notes.get('1.0','end').strip();audience='testers' if self.audience.get()=='Testers' else 'stable'
        if action=='publish' and (not 1<=len(title)<=72 or len(notes)>1000):self.status.set('Use titulo de 1 a 72 caracteres e novidades de ate 1000 caracteres.');return
        try:version=int(self.version.get())
        except ValueError:self.status.set('O numero do pacote deve ser um inteiro.');return
        source=self.source.get().strip();self.busy=True;self.stop.clear();self.bar.start(12);self.send.configure(state='disabled');self.inspect.configure(state='disabled');self.cancel.configure(state='normal');self.retake.configure(state='disabled')
        self.status.set('Conferindo...' if action=='analyze' else 'Preparando publicacao...')
        def notify(kind,value):self.events.put((kind,value))
        def task():
            try:
                if action=='analyze':notify('plan',backend.analyze(Path(source)))
                elif action=='server':backend.deploy_server(secret,notify)
                elif action=='resume':backend.resume(secret,self.stop,notify)
                else:backend.publish(self.plan,title,notes,version,audience,secret,self.stop,notify)
                notify('done',action)
            except Exception as error:notify('error',str(error).replace(secret,'[oculto]') if secret else str(error))
        threading.Thread(target=task,daemon=True).start()

    def poll(self):
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='status':self.status.set(value)
            elif kind=='plan':
                self.plan=value;self.tree.delete(*self.tree.get_children())
                for row in value['changes']:self.tree.insert('','end',values=(row['change'],row['path']))
                for name in value['removed']:self.tree.insert('','end',values=('Removido',name))
                for name in value['code']:self.tree.insert('','end',values=('Programa / codigo',name))
                if value['mode']=='full':self.summary.set('VERSAO COMPLETA • PC '+value['versions']['pc']+' / Android '+value['versions']['android']+' • '+' '.join(value['reasons']))
                else:self.summary.set('PACOTE RAPIDO • '+str(len(value['changes']))+' arquivo(s) para PC e Android. Download pelo menu Online; aplicar ao reiniciar.')
                self.status.set('Previa pronta. Nenhum arquivo publicado.')
            elif kind in ('done','error'):
                self.busy=False;self.bar.stop();self.inspect.configure(state='normal');self.retake.configure(state='normal');self.cancel.configure(state='disabled')
                self.send.configure(state='normal' if self.plan and (self.plan['mode']=='full' or self.plan['changes']) else 'disabled')
                if kind=='error':self.status.set('Falha: '+value);messagebox.showerror('Publicacao nao concluida',value,parent=self.root)
                elif value!='analyze':self.token.delete(0,'end');self.plan=None;self.send.configure(state='disabled')
        self.root.after(120,self.poll)

    def cancel_task(self):self.stop.set();self.status.set('Parando no proximo ponto seguro. Builds ja enviadas continuam no GitHub.')
    def close(self):
        if self.busy:messagebox.showinfo('Operacao em andamento','Use Parar e aguarde antes de fechar.',parent=self.root)
        else:self.root.destroy()


if __name__=='__main__':
    root=tk.Tk()
    if '--self-check' in sys.argv:
        root.withdraw();Publisher(root);root.update_idletasks();root.destroy();print('PASS: interface criada; nenhum envio, commit ou build iniciado.')
    else:Publisher(root);root.mainloop()
