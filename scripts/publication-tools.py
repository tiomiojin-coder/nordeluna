"""Reviewable, deterministic summaries for configuration and map publication."""
import json
from pathlib import PurePosixPath

LABELS={'title':'Titulo','price':'Preco','rewards':'Recompensas','enabled':'Ativo','kind':'Atividade','target':'Meta','coins':'Luna Coins','id':'ID'}


def display(value,key=''):
    if value is None:return '—'
    if type(value) is bool:return 'Sim' if value else 'Nao'
    if key in ('price','coins'):return str(value)+' LC'
    if isinstance(value,(dict,list)):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
    return str(value)


def content_diff(before,after):
    rows=[]
    for group,label in [('missions','Missao'),('shop','Produto')]:
        old=before[group];new=after[group]
        for key in sorted(set(old)|set(new)):
            title=(new.get(key) or old[key])['title'];name=f'{label}: {title} [{key}]'
            if key not in new:rows.append(dict(name=name,change='Removido',before=display(old[key]),after='—'));continue
            if key not in old:rows.append(dict(name=name,change='Adicionado',before='—',after=display(new[key])));continue
            for field in sorted(set(old[key])|set(new[key])):
                if old[key].get(field)!=new[key].get(field):rows.append(dict(name=name,change=LABELS.get(field,field),before=display(old[key].get(field),field),after=display(new[key].get(field),field)))
    for field in sorted(set(before['community'])|set(after['community'])):
        if before['community'].get(field)!=after['community'].get(field):rows.append(dict(name='Evento comunitario',change=LABELS.get(field,field),before=display(before['community'].get(field),field),after=display(after['community'].get(field),field)))
    return rows


def package_diff(manifest):
    rows=[]
    for item in manifest['files']:
        name=item['path'];kind='Recurso'
        if name.startswith('Data/Map') and PurePosixPath(name).stem[3:].isdigit():kind='Mapa '+str(int(PurePosixPath(name).stem[3:]))
        elif name=='Data/MapInfos.rxdata':kind='Lista de mapas'
        elif name=='Data/Tilesets.rxdata':kind='Tilesets'
        elif name=='Data/CommonEvents.rxdata':kind='Eventos comuns'
        elif name.startswith('Data/'):kind='Dados dos mapas'
        rows.append(dict(name=f'{kind}: {name}',change='Novo' if item['base_sha256'] is None else 'Alterado',before='Ausente' if item['base_sha256'] is None else 'Na base do APK',after=f"{item['size']:,} bytes"))
    return rows


def show_preview(parent,rows,title='Previa da publicacao',subtitle='',confirm='Publicar'):
    import tkinter as tk
    from tkinter import ttk
    dialog=tk.Toplevel(parent);dialog.title(title);dialog.geometry('900x540');dialog.minsize(720,400);dialog.transient(parent)
    body=ttk.Frame(dialog,padding=14);body.pack(fill='both',expand=True)
    ttk.Label(body,text=title,font=('Segoe UI',16,'bold')).pack(anchor='w')
    ttk.Label(body,text=subtitle,wraplength=840).pack(anchor='w',pady=8)
    container=ttk.Frame(body);container.pack(fill='both',expand=True)
    table=ttk.Treeview(container,columns=('change','before','after'),show='tree headings',selectmode='browse')
    for key,label,width in [('#0','Mapa / produto / opcao',310),('change','Mudanca',100),('before','Antes',190),('after','Depois',210)]:table.heading(key,text=label);table.column(key,width=width,minwidth=60)
    scroll=ttk.Scrollbar(container,orient='vertical',command=table.yview);table.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y');table.pack(fill='both',expand=True)
    for i,row in enumerate(rows):table.insert('','end',iid=str(i),text=row['name'],values=(row['change'],row['before'],row['after']))
    details=tk.Text(body,height=4,wrap='word',state='disabled');details.pack(fill='x',pady=8)
    def selected(event):
        choice=table.selection()
        if not choice:return
        row=rows[int(choice[0])];details.configure(state='normal');details.delete('1.0','end');details.insert('1.0',row['name']+'\nAntes: '+row['before']+'\nDepois: '+row['after']);details.configure(state='disabled')
    table.bind('<<TreeviewSelect>>',selected)
    accepted=False
    def finish():
        nonlocal accepted
        accepted=True;dialog.destroy()
    actions=ttk.Frame(body);actions.pack(fill='x')
    ttk.Button(actions,text='Voltar e editar',command=dialog.destroy).pack(side='left')
    ttk.Button(actions,text=confirm,command=finish).pack(side='right')
    dialog.bind('<Escape>',lambda event:dialog.destroy());dialog.grab_set();parent.wait_window(dialog)
    return accepted
