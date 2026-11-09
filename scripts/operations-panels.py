"""Local administration for tester access, promotion and timed notices."""
from datetime import datetime,timedelta,timezone
import queue
import re
import threading


def worker(root,status,token,manager,service,done):
    events=queue.Queue();busy=False
    def run(payload):
        nonlocal busy
        if busy:return
        secret=token.get().strip()
        if not secret:status.set('Informe o token no campo mascarado.');return
        busy=True;status.set('Consultando o servidor...')
        def task():
            try:events.put((True,manager.publish(secret,payload,service)))
            except Exception as error:events.put((False,str(error).replace(secret,'[oculto]')))
        threading.Thread(target=task,daemon=True).start()
    def poll():
        nonlocal busy
        while not events.empty():
            ok,value=events.get();busy=False
            if ok:done(value)
            else:status.set('Falha: '+value)
        root.after(150,poll)
    poll();return run


def make_testers(parent,root,status,token,manager,review):
    import tkinter as tk
    from tkinter import ttk
    from tkinter import filedialog,messagebox
    import json
    # Invites govern launcher access; the older list below governs map packs.
    access=ttk.LabelFrame(parent,text='Convites individuais para baixar e jogar a versão de testes');access.pack(fill='x',pady=6)
    form=ttk.Frame(access);form.pack(fill='x');label=tk.StringVar();days=tk.IntVar(value=30)
    ttk.Label(form,text='Nome do tester:').pack(side='left');ttk.Entry(form,textvariable=label,width=22).pack(side='left')
    ttk.Label(form,text='Validade (dias):').pack(side='left');ttk.Spinbox(form,from_=1,to=365,textvariable=days,width=5).pack(side='left')
    invitations=ttk.Treeview(access,columns=('label','state'),show='headings',height=4);invitations.heading('label',text='Tester');invitations.heading('state',text='Acesso');invitations.pack(fill='x')
    def access_done(value):
        if 'invitation' in value:
            # Selectable, never automatically copied or persisted in the panel.
            dialog=tk.Toplevel(root);dialog.title('Convite — mostrado uma única vez');ttk.Label(dialog,text='Envie esta chave somente ao tester. Não será exibida novamente.').pack(padx=15,pady=12)
            entry=ttk.Entry(dialog,width=48);entry.insert(0,value['invitation']);entry.pack(padx=15,pady=10);entry.selection_range(0,'end');entry.focus_set();ttk.Button(dialog,text='Fechar',command=dialog.destroy).pack(pady=10)
        if 'invitations' in value:
            for child in invitations.get_children():invitations.delete(child)
            now=datetime.now().timestamp()
            for row in value['invitations']:
                state='Revogado' if row['revoked'] else 'Expirado' if row['expires']<=now else 'Ativado' if row['claimed'] else 'Aguardando resgate'
                invitations.insert('','end',iid=row['id'],values=(row['label'],state))
        if value.get('published'):status.set('Versão protegida publicada para os testers autorizados.')
        if value.get('revoked'):status.set('Acesso revogado. A próxima validação será recusada.')
    access_run=worker(root,status,token,manager,'tester',access_done)
    controls=ttk.Frame(access);controls.pack(fill='x',pady=5)
    def create():
        try:validity=days.get()
        except (ValueError,tk.TclError):status.set('Informe a validade em dias.');return
        access_run(dict(action='create',label=label.get(),days=validity))
    ttk.Button(controls,text='Gerar chave',command=create).pack(side='left');ttk.Button(controls,text='Listar convites',command=lambda:access_run(dict(action='list'))).pack(side='left',padx=4)
    def revoke():
        selected=invitations.selection()
        if selected and messagebox.askyesno('Revogar acesso','Bloquear novas entradas e downloads deste tester?',parent=root):access_run(dict(action='revoke',id=selected[0]))
    ttk.Button(controls,text='Revogar selecionado',command=revoke).pack(side='left')
    def publish_protected():
        name=filedialog.askopenfilename(parent=root,title='Publicação privada dos testers',initialdir=str(manager.ROOT/'.cache/testers'),filetypes=[('JSON','*.json')])
        if not name:return
        try:
            from pathlib import Path
            path=Path(name)
            if path.stat().st_size>200000:raise ValueError('Arquivo grande demais')
            payload=json.loads(path.read_text(encoding='utf-8'))
            if messagebox.askyesno('Publicar testes','Liberar este pacote protegido para os testers com acesso ativo?',parent=root):access_run(dict(action='publish',payload=payload))
        except (ValueError,OSError) as error:status.set('Arquivo inválido: '+str(error)[:120])
    ttk.Button(controls,text='Publicar versão protegida',command=publish_protected).pack(side='left',padx=4)
    ttk.Label(parent,text='Somente as contas cadastradas podem consultar e baixar pacotes de teste.\nInforme os nicks online ou IDs das contas, um por linha. Trocar de nick nao remove a permissao.',wraplength=850).pack(anchor='w',pady=7)
    names=tk.Text(parent,height=4,wrap='word');names.pack(fill='x')
    packages={};table=ttk.Treeview(parent,columns=('title','channel'),show='tree headings',height=5,selectmode='browse')
    table.heading('#0',text='Pacote');table.column('#0',width=70)
    table.heading('title',text='Titulo');table.heading('channel',text='Publico');table.column('channel',width=120)
    def done(value):
        if 'testers' in value:
            names.delete('1.0','end');names.insert('1.0','\n'.join(row['nickname'] for row in value['testers']));status.set(f"Grupo de testers: {len(value['testers'])} conta(s).")
        if 'packages' in value:
            packages.clear()
            for child in table.get_children():table.delete(child)
            for row in value['packages']:
                packages[row['version']]=row;table.insert('','end',iid=str(row['version']),text=row['version'],values=(row['title'],'Testers' if row['channel']=='testers' else 'Todos'))
            status.set('Publicacoes carregadas.')
        if 'promoted' in value:status.set('Pacote '+str(value['promoted'])+' liberado para todos, sem reenviar arquivos.');run(dict(action='list'))
    run=worker(root,status,token,manager,'update',done)
    buttons=ttk.Frame(parent);buttons.pack(fill='x',pady=8)
    ttk.Button(buttons,text='Carregar testers',command=lambda:run(dict(action='testers_get'))).pack(side='left')
    def save():
        selected=[value for value in re.split(r'[,\s]+',names.get('1.0','end').strip()) if value]
        if review.show_preview(root,[dict(name='Grupo de testers',change='Substituir lista',before='Grupo atual no servidor',after=', '.join(selected) or 'Nenhum tester')],'Conferir testers','As permissoes ficam vinculadas as contas, sem alterar o acesso aos pacotes publicos.',confirm='Salvar grupo'):
            run(dict(action='testers_set',testers=selected))
    ttk.Button(buttons,text='Conferir e salvar grupo',command=save).pack(side='left',padx=8)
    ttk.Label(parent,text='Pacotes publicados:').pack(anchor='w',pady=5);table.pack(fill='both',expand=True)
    actions=ttk.Frame(parent);actions.pack(fill='x',pady=8)
    ttk.Button(actions,text='Atualizar publicacoes',command=lambda:run(dict(action='list'))).pack(side='left')
    def promote():
        selected=table.selection()
        if not selected:status.set('Selecione um pacote na lista.');return
        row=packages[int(selected[0])]
        if row['channel']=='stable':status.set('Este pacote ja esta disponivel para todos.');return
        rows=[dict(name='Pacote '+str(row['version']),change='Publico',before='Testers',after='Todos')]+review.package_diff(dict(files=row['files']))
        if review.show_preview(root,rows,'Liberar pacote para todos',row['title'],confirm='Liberar para todos'):
            run(dict(action='promote',version=row['version'],signature=row['signature']))
    ttk.Button(actions,text='Conferir e liberar para todos',command=promote).pack(side='left',padx=8)


def make_notices(parent,root,status,token,manager,review):
    import tkinter as tk
    from tkinter import ttk
    from tkinter import messagebox
    ttk.Label(parent,text='Faixa pequena no mapa online, sem interromper dialogos ou batalhas.\nCada aviso aparece uma vez por sessao e desaparece sozinho. Recebimento automatico enquanto estiver online.',wraplength=850).pack(anchor='w',pady=7)
    text=tk.StringVar();ttk.Entry(parent,textvariable=text).pack(fill='x',pady=6)
    form=ttk.Frame(parent);form.pack(fill='x',pady=6)
    kind=tk.StringVar(value='Aviso');hours=tk.StringVar(value='24');duration=tk.StringVar(value='8')
    ttk.Combobox(form,textvariable=kind,values=['Aviso','Evento','Manutencao'],state='readonly',width=15).pack(side='left')
    ttk.Label(form,text='Validade (horas):').pack(side='left',padx=(14,4));ttk.Entry(form,textvariable=hours,width=5).pack(side='left')
    ttk.Label(form,text='Na tela (6 a 12 s):').pack(side='left',padx=(14,4));ttk.Entry(form,textvariable=duration,width=5).pack(side='left')
    table=ttk.Treeview(parent,columns=('text','ends','active'),show='tree headings',selectmode='browse',height=5)
    for key,label,width in [('#0','Tipo',105),('text','Mensagem',430),('ends','Valido ate (UTC-3)',150),('active','Ativo',55)]:table.heading(key,text=label);table.column(key,width=width)
    def done(value):
        for child in table.get_children():table.delete(child)
        for row in value['notices']:
            ends=datetime.fromtimestamp(row['ends'],timezone(timedelta(hours=-3))).strftime('%d/%m %H:%M')
            table.insert('','end',iid=row['id'],text=row['kind'],values=(row['text'],ends,'Sim' if row['active'] else 'Nao'))
        status.set('Avisos atualizados. O jogo recebe pela conexao online existente.')
    run=worker(root,status,token,manager,'notice',done)
    def create():
        try:
            body=text.get().strip();lifetime=int(hours.get());seconds=int(duration.get())
            if not 1<=len(body)<=180 or any(ord(c)<32 for c in body):raise ValueError('Escreva de 1 a 180 caracteres, sem quebras de linha.')
            if not 1<=lifetime<=168 or not 6<=seconds<=12:raise ValueError('Validade: 1 a 168 horas; exibicao: 6 a 12 segundos.')
            selected={'Aviso':'info','Evento':'event','Manutencao':'maintenance'}[kind.get()]
            if review.show_preview(root,[dict(name=kind.get(),change='Novo aviso',before='—',after=body),dict(name='Validade',change='Duracao',before='—',after=f'{lifetime} hora(s); {seconds}s na tela')],'Previa do aviso','Envio para jogadores conectados. O aviso nao pausa o jogo.',confirm='Publicar aviso'):
                ends=int(datetime.now(timezone.utc).timestamp())+lifetime*3600
                run(dict(action='create',text=body,kind=selected,ends=ends,duration=seconds))
        except ValueError as error:messagebox.showerror('Aviso',str(error),parent=root)
    buttons=ttk.Frame(parent);buttons.pack(fill='x',pady=7)
    ttk.Button(buttons,text='Conferir e publicar aviso',command=create).pack(side='left')
    ttk.Button(buttons,text='Atualizar lista',command=lambda:run(dict(action='list'))).pack(side='left',padx=8)
    def disable():
        selected=table.selection()
        if selected:run(dict(action='disable',id=selected[0]))
    ttk.Button(buttons,text='Encerrar selecionado',command=disable).pack(side='left')
    table.pack(fill='both',expand=True)
