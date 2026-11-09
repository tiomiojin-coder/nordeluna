"""Local Windows gift editor; publishes via authenticated Discloud console."""
import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import queue
import re
import shlex
import sys
import threading
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.gifts import rewards_data, code_text
from scripts.updater_core import DEFAULT_GAME


def catalog(game=DEFAULT_GAME):
    data={}
    for group in ('pokemon','items','moves'):
        path=game/'PBS'/(group+'.txt')
        rows={};current=None
        if path.is_file():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                match=re.fullmatch(r'\[([A-Z][A-Z0-9_]*)\]',line.strip())
                if match:current=match[1];rows[current]=current
                elif current and re.match(r'^Name\s*=',line):rows[current]=line.split('=',1)[1].strip()
        data[group]=rows
    forms={key:{0} for key in data['pokemon']}
    path=game/'PBS/pokemon_forms.txt'
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            match=re.fullmatch(r'\[([A-Z][A-Z0-9_]*),\s*([0-9]+)\]',line.strip())
            if match:forms.setdefault(match[1],{0}).add(int(match[2]))
    data['forms']=forms
    return data


def console_command(payload, service='gift'):
    if service not in ('gift','content','update','notice','moderation','tester'):raise ValueError('Servico administrativo invalido.')
    encoded=base64.b64encode(json.dumps(payload,ensure_ascii=False).encode()).decode('ascii')
    source=("import base64,json;from relay import Store;s=Store('data/relay.sqlite3')\n"
            "try:\n r=s."+service+"_admin(json.loads(base64.b64decode("+repr(encoded)+")))\n"
            "except ValueError as e:\n r={'error':str(e)[:200]}\n"
            "finally:\n s.db.close()\n"
            "print('NORDELUNA_GIFT_RESULT='+json.dumps(r,ensure_ascii=True))")
    return 'python -c '+shlex.quote(source)


class AdminSession:
    def __init__(self,token):
        self.client=None;self.token=token
    def __enter__(self):
        spec=importlib.util.spec_from_file_location('gift_discloud',ROOT/'scripts/discloud-local-deploy.py')
        deploy=importlib.util.module_from_spec(spec);spec.loader.exec_module(deploy)
        self.client=deploy.Client(self.token);self.token=''
        try:
            apps=self.client.request('/app/all').get('apps',[])
            apps=apps if isinstance(apps,list) else [apps]
            matches=[app for app in apps if app.get('id') in ('nordeluna-online','nordeluna-online.discloud.dev','nordeluna-online.discloud.app')]
            if len(matches)!=1:raise ValueError('Nao foi possivel identificar a aplicacao Nordeluna Online.')
            self.app_id=matches[0]['id'];return self
        except Exception:
            self.client.token='';raise
    def __exit__(self,*args):
        if self.client:self.client.token=''
        self.token=''
    def publish(self,payload,service='gift'):
        return send_admin(self.client,self.app_id,payload,service)


def send_admin(client,app_id,payload,service='gift'):
    result=client.request('/app/'+urllib.parse.quote(app_id,safe='')+'/console','PUT',
        json.dumps({'command':console_command(payload,service)}).encode(),'application/json')
    shell=result.get('apps',{}).get('shell',{})
    for line in str(shell.get('stdout','')).splitlines():
        if line.startswith('NORDELUNA_GIFT_RESULT='):
            reply=json.loads(line.split('=',1)[1])
            if 'error' in reply:raise ValueError(reply['error'])
            return reply
    raise ValueError('O servidor nao confirmou a operacao. Confira a versao instalada: presentes requerem 0.7.0; painel requer 0.9.0; moderacao requer 0.10.0.')


def publish(token,payload,service='gift'):
    with AdminSession(token) as session:return session.publish(payload,service)


def main():
    import tkinter as tk
    from tkinter import ttk, messagebox
    root=tk.Tk();root.title('Presentes Nordeluna');root.geometry('850x720');root.minsize(760,630)
    frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Presentes Nordeluna',font=('Segoe UI',19,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Novos codigos sem recompilar o APK, depois de instalar o sistema de presentes.').pack(anchor='w',pady=5)
    ttk.Label(frame,text='Token Discloud (mascarado, somente nesta janela; nao sera salvo):').pack(anchor='w')
    token=ttk.Entry(frame,show='*');token.pack(fill='x',pady=(3,10))
    tabs=ttk.Notebook(frame);tabs.pack(fill='both',expand=True)
    create=ttk.Frame(tabs,padding=12);published=ttk.Frame(tabs,padding=12)
    tabs.add(create,text='Criar presente');tabs.add(published,text='Publicados')
    fields={}
    def entry(parent,label,key,row,default=''):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=4)
        value=tk.StringVar(value=default);ttk.Entry(parent,textvariable=value,width=48).grid(row=row,column=1,sticky='ew',padx=8)
        fields[key]=value
    create.columnconfigure(1,weight=1)
    entry(create,'Codigo','code',0)
    entry(create,'Titulo','title',1)
    entry(create,'Validade (AAAA-MM-DD HH:MM, UTC-3)','expires',2)
    entry(create,'Limite total (vazio = ilimitado)','limit',3)
    data=catalog();rewards=[]
    builder=ttk.LabelFrame(create,text='Adicionar recompensa',padding=8);builder.grid(row=4,column=0,columnspan=2,sticky='ew',pady=10)
    kind=tk.StringVar(value='Item');ttk.Combobox(builder,textvariable=kind,values=['Item','Pokemon','Dinheiro'],state='readonly',width=13).grid(row=0,column=0,padx=4)
    identity=tk.StringVar();combo=ttk.Combobox(builder,textvariable=identity,width=36);combo.grid(row=0,column=1,columnspan=3,padx=4,sticky='ew')
    amount=tk.StringVar(value='5');form=tk.StringVar(value='0');shiny=tk.BooleanVar()
    ttk.Label(builder,text='Quantidade / nivel / valor').grid(row=1,column=0,columnspan=2,sticky='w',pady=6)
    ttk.Entry(builder,textvariable=amount,width=10).grid(row=1,column=2)
    ttk.Label(builder,text='Forma').grid(row=2,column=0,sticky='w')
    ttk.Entry(builder,textvariable=form,width=8).grid(row=2,column=1,sticky='w')
    ttk.Checkbutton(builder,text='Shiny',variable=shiny).grid(row=2,column=2)
    moves=tk.StringVar();held=tk.StringVar()
    ttk.Label(builder,text='Golpes (IDs separados por virgula; opcional)').grid(row=3,column=0,columnspan=2,sticky='w',pady=5)
    ttk.Entry(builder,textvariable=moves,width=30).grid(row=3,column=2,columnspan=2)
    ttk.Label(builder,text='Item segurado (ID; opcional)').grid(row=4,column=0,columnspan=2,sticky='w')
    ttk.Entry(builder,textvariable=held,width=30).grid(row=4,column=2,columnspan=2)
    def suggestions(*args):
        group='pokemon' if kind.get()=='Pokemon' else 'items'
        query=identity.get().casefold()
        combo['values']=[f'{key} - {name}' for key,name in data[group].items() if query in key.casefold() or query in name.casefold()][:1000]
    kind.trace_add('write',lambda *args:(identity.set(''),suggestions()))
    combo.bind('<KeyRelease>',suggestions);suggestions()
    reward_list=tk.Listbox(create,height=5);reward_list.grid(row=5,column=0,columnspan=2,sticky='nsew')
    create.rowconfigure(5,weight=1)
    def add_reward():
        try:
            name=identity.get().split(' - ',1)[0].strip().upper()
            if kind.get()=='Dinheiro':row=dict(kind='money',amount=int(amount.get()))
            elif kind.get()=='Item':
                if name not in data['items']:raise ValueError('Escolha um item existente no PBS do jogo.')
                row=dict(kind='item',id=name,quantity=int(amount.get()))
            else:
                if name not in data['pokemon']:raise ValueError('Escolha uma especie existente no PBS do jogo.')
                row=dict(kind='pokemon',species=name,level=int(amount.get()),form=int(form.get()),shiny=shiny.get())
                if row['form'] not in data['forms'].get(name,{0}):raise ValueError('Esta forma nao existe no PBS local.')
                if moves.get().strip():row['moves']=[v.strip().upper() for v in moves.get().split(',')]
                if held.get().strip():row['item']=held.get().strip().upper()
                if any(v not in data['moves'] for v in row.get('moves',[])):raise ValueError('Golpe nao encontrado no PBS.')
                if row.get('item') and row['item'] not in data['items']:raise ValueError('Item segurado nao encontrado.')
            rewards_data(rewards+[row]);rewards.append(row)
            reward_list.insert('end',json.dumps(row,ensure_ascii=False))
        except (ValueError,TypeError) as error:messagebox.showerror('Recompensa',str(error),parent=root)
    ttk.Button(builder,text='Adicionar',command=add_reward).grid(row=0,column=4,padx=6)
    def remove():
        selected=reward_list.curselection()
        if selected:rewards.pop(selected[0]);reward_list.delete(selected[0])
    ttk.Button(create,text='Remover recompensa selecionada',command=remove).grid(row=6,column=0,columnspan=2,sticky='w',pady=6)
    status=tk.StringVar(value='Aguardando. Nenhum codigo sera publicado automaticamente.')
    ttk.Label(frame,textvariable=status,wraplength=780).pack(anchor='w',pady=10)
    events=queue.Queue();busy=False
    published_rows=[]
    table=ttk.Treeview(published,columns=('title','claims','enabled'),show='tree headings',height=12)
    table.heading('#0',text='Codigo');table.heading('title',text='Titulo');table.heading('claims',text='Resgates');table.heading('enabled',text='Ativo')
    table.column('#0',width=180);table.column('title',width=240);table.column('claims',width=80);table.column('enabled',width=70)
    table.pack(fill='both',expand=True)
    def run(payload):
        nonlocal busy
        secret=token.get().strip()
        if busy:return
        if not secret:status.set('Informe o token somente no campo mascarado desta janela.');return
        busy=True;status.set('Consultando o Discloud...')
        def work():
            try:events.put((True,publish(secret,payload)))
            except Exception as error:events.put((False,str(error).replace(secret,'[token oculto]')))
        threading.Thread(target=work,daemon=True).start()
    def submit():
        try:
            expiration=fields['expires'].get().strip()
            expires=int(datetime.strptime(expiration,'%Y-%m-%d %H:%M').replace(tzinfo=timezone(timedelta(hours=-3))).timestamp()) if expiration else None
            value=fields['limit'].get().strip()
            payload=dict(action='create',code=code_text(fields['code'].get()),title=fields['title'].get().strip(),
                rewards=rewards_data(rewards),expires=expires,limit=int(value) if value else None)
            if not payload['title']:raise ValueError('Preencha o titulo.')
            run(payload)
        except ValueError as error:messagebox.showerror('Presente',str(error),parent=root)
    ttk.Button(create,text='Publicar presente',command=submit).grid(row=7,column=0,columnspan=2,sticky='ew',pady=6)
    ttk.Button(published,text='Atualizar lista',command=lambda:run({'action':'list'})).pack(side='left',pady=8)
    def disable():
        selected=table.selection()
        if selected:run({'action':'disable','code':table.item(selected[0],'text')})
    ttk.Button(published,text='Encerrar codigo selecionado',command=disable).pack(side='left',padx=8)
    def poll():
        nonlocal busy
        while not events.empty():
            ok,result=events.get();busy=False
            if ok and 'gifts' in result:
                for item in table.get_children():table.delete(item)
                for gift in result['gifts']:table.insert('','end',text=gift['code'],values=(gift['title'],gift['claims'],'Sim' if gift['enabled'] else 'Nao'))
                status.set('Lista atualizada. Encerrar nao remove presentes ja reservados.')
            else:status.set(('Concluido: '+json.dumps(result,ensure_ascii=False)) if ok else str(result))
        root.after(150,poll)
    root.protocol('WM_DELETE_WINDOW',lambda:(token.delete(0,'end'),root.destroy()))
    poll();root.mainloop()


if __name__=='__main__':main()
