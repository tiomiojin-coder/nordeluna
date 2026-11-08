"""Windows editor for live missions, store, community events and update packages."""
import copy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.content import DEFAULT_CONTENT, validate_content


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


gifts=module('editor_gifts','gift-manager.py')
formats=module('editor_formats','online-content-tools.py')
review=module('editor_review','publication-tools.py')
operations=module('editor_operations','operations-panels.py')
moderation=module('editor_moderation','moderation-panel.py')
DRAFT=ROOT/'build/admin/conteudo-online.json'


def validate_catalog(data):
    data=validate_content(data);catalog=gifts.catalog()
    for product in data['shop'].values():
        for reward in product['rewards']:
            if reward['kind']=='item' and reward['id'] not in catalog['items']:
                raise ValueError('Item nao encontrado no jogo local: '+reward['id'])
            if reward['kind']=='pokemon':
                species=reward['species']
                if species not in catalog['pokemon']:raise ValueError('Pokemon nao encontrado: '+species)
                if reward.get('form',0) not in catalog['forms'].get(species,{0}):raise ValueError('Forma nao encontrada: '+species)
                if any(m not in catalog['moves'] for m in reward.get('moves',[])):raise ValueError('Golpe nao encontrado: '+species)
                if reward.get('item') and reward['item'] not in catalog['items']:raise ValueError('Item segurado nao encontrado: '+species)
    return data


def save_draft(data):
    DRAFT.parent.mkdir(parents=True,exist_ok=True)
    temporary=DRAFT.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(DRAFT)


def main():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    root=tk.Tk();root.title('Central Online Nordeluna 0.10.0');root.geometry('1080x800');root.minsize(940,720)
    root.configure(bg='#0c1726')
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('TFrame',background='#142339');style.configure('TLabel',background='#142339',foreground='#e8f2fa',font=('Segoe UI',10))
    style.configure('TLabelframe',background='#142339');style.configure('TLabelframe.Label',background='#142339',foreground='#7bdce2')
    style.configure('TButton',padding=7);style.configure('TCheckbutton',background='#142339',foreground='#e8f2fa')
    style.configure('Treeview',rowheight=27);style.configure('TNotebook.Tab',padding=(10,8))
    outer=ttk.Frame(root,padding=18);outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='Central Online Nordeluna',font=('Segoe UI',22,'bold')).pack(anchor='w')
    ttk.Label(outer,text='Missoes, precos e desafios chegam pelo servidor. Mapas e recursos usam pacotes de atualizacao.').pack(anchor='w',pady=(4,12))
    auth=ttk.Frame(outer);auth.pack(fill='x')
    ttk.Label(auth,text='Token Discloud:').pack(side='left')
    token=ttk.Entry(auth,show='*',width=42);token.pack(side='left',padx=8)
    ttk.Label(auth,text='Somente nesta janela; nao e salvo.').pack(side='left')
    status=tk.StringVar(value='Rascunho local. Carregue o servidor antes de publicar.')
    revision=tk.StringVar(value='Servidor: ainda nao consultado')
    ttk.Label(outer,textvariable=revision,foreground='#7bdce2').pack(anchor='w',pady=7)
    tabs=ttk.Notebook(outer);tabs.pack(fill='both',expand=True,pady=5)
    pages={}
    for key,label in [('missions','Missoes'),('shop','Loja'),('community','Evento'),('files','Ruby'),('history','Historico'),('updates','Pacotes'),('testers','Testers'),('notices','Avisos'),('gifts','Presentes'),('moderation','Moderacao')]:
        pages[key]=ttk.Frame(tabs,padding=12);tabs.add(pages[key],text=label)
    try:data=validate_content(json.loads(DRAFT.read_text(encoding='utf-8')))
    except (OSError,ValueError):data=copy.deepcopy(DEFAULT_CONTENT)
    current=None;remote_data=None;busy=False;events=queue.Queue();fields={};trees={};rewards=[]

    def report(error):messagebox.showerror('Nordeluna',str(error),parent=root)
    def entry(parent,label,key,row,default='',values=None):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=5)
        value=tk.StringVar(value=default)
        widget=ttk.Combobox(parent,textvariable=value,values=values,state='readonly') if values else ttk.Entry(parent,textvariable=value)
        widget.grid(row=row,column=1,sticky='ew',padx=8,pady=4);fields[key]=value
        return widget
    def refresh():
        for group,tree in trees.items():
            for child in tree.get_children():tree.delete(child)
            for key,row in data[group].items():
                tree.insert('','end',iid=key,text=key,values=(row['title'],row.get('coins',row.get('price')),'Sim' if row['enabled'] else 'Nao'))
        for key,value in data['community'].items():fields['event_'+key].set(value)
        save_draft(data)
    def apply_group(group):
        nonlocal data
        try:
            key=fields[group+'_id'].get().strip();value=dict(title=fields[group+'_title'].get().strip(),enabled=fields[group+'_enabled'].get())
            if group=='missions':value.update(kind=fields[group+'_kind'].get(),target=int(fields[group+'_target'].get()),coins=int(fields[group+'_coins'].get()))
            else:value.update(price=int(fields[group+'_price'].get()),rewards=copy.deepcopy(rewards))
            candidate=copy.deepcopy(data);candidate[group][key]=value
            data=validate_catalog(candidate);refresh();status.set('Rascunho salvo. Publique para enviar ao servidor.')
        except (ValueError,TypeError) as error:report(error)
    def remove(group):
        selection=trees[group].selection()
        if selection:
            data[group].pop(selection[0],None);refresh();status.set('Removido apenas do rascunho; publique para atualizar.')
    def load_row(group):
        selected=trees[group].selection()
        if not selected:return
        key=selected[0];row=data[group][key];fields[group+'_id'].set(key)
        for field,value in row.items():
            if group+'_'+field in fields:fields[group+'_'+field].set(value)
        if group=='shop':rewards[:]=copy.deepcopy(row['rewards']);show_rewards()

    for group in ('missions','shop'):
        page=pages[group];page.columnconfigure(0,weight=1);page.columnconfigure(1,weight=1);page.rowconfigure(0,weight=1)
        left=ttk.Frame(page);left.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        tree=ttk.Treeview(left,columns=('title','coins','active'),show='tree headings',selectmode='browse');trees[group]=tree
        for key,label,width in [('#0','ID',100),('title','Titulo',180),('coins','LC',55),('active','Ativo',50)]:tree.heading(key,text=label);tree.column(key,width=width)
        scroll=ttk.Scrollbar(left,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        tree.bind('<<TreeviewSelect>>',lambda event,g=group:load_row(g))
        holder=ttk.Frame(page);holder.grid(row=0,column=1,sticky='nsew')
        canvas=tk.Canvas(holder,bg='#142339',highlightthickness=0,width=410,height=300)
        form_scroll=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=form_scroll.set)
        canvas.pack(side='left',fill='both',expand=True);form_scroll.pack(side='right',fill='y')
        form=ttk.Frame(canvas);form.columnconfigure(1,weight=1)
        window=canvas.create_window(0,0,window=form,anchor='nw')
        form.bind('<Configure>',lambda event,c=canvas:c.configure(scrollregion=c.bbox('all')))
        canvas.bind('<Configure>',lambda event,c=canvas,w=window:c.itemconfigure(w,width=event.width))
        def wheel(event,c=canvas):
            if c.winfo_ismapped() and c.winfo_rootx()<=event.x_root<c.winfo_rootx()+c.winfo_width() and c.winfo_rooty()<=event.y_root<c.winfo_rooty()+c.winfo_height():
                c.yview_scroll(-int(event.delta/120),'units')
        root.bind_all('<MouseWheel>',wheel,add='+')
        entry(form,'ID estavel',group+'_id',0)
        entry(form,'Titulo',group+'_title',1)
        enabled=tk.BooleanVar(value=True);fields[group+'_enabled']=enabled
        ttk.Checkbutton(form,text='Ativo',variable=enabled).grid(row=2,column=1,sticky='w')
        if group=='missions':
            entry(form,'Atividade',group+'_kind',3,'visit',['visit','battle','trade'])
            entry(form,'Meta',group+'_target',4,'1');entry(form,'Luna Coins',group+'_coins',5,'10')
            ttk.Label(form,text='visit = visita diaria\nbattle = batalha confirmada (2+ turnos)\ntrade = troca concluida\n\nIDs iguais preservam os resgates.\nUse um ID novo para outra missao.',wraplength=310).grid(row=6,column=0,columnspan=2,sticky='w',pady=16)
        else:
            entry(form,'Preco em Luna Coins',group+'_price',3,'25')
            reward_box=ttk.LabelFrame(form,text='Recompensas do produto',padding=8);reward_box.grid(row=4,column=0,columnspan=2,sticky='nsew',pady=8);reward_box.columnconfigure(1,weight=1)
            entry(reward_box,'Tipo','reward_kind',0,'Item',['Item','Pokemon','Ovo','Dinheiro'])
            catalog=gifts.catalog()
            combo=entry(reward_box,'ID / especie','reward_id',1,values=list(catalog['items']))
            def choices(*args):
                group='pokemon' if fields['reward_kind'].get() in ('Pokemon','Ovo') else 'items'
                combo.configure(values=list(catalog[group]),state='normal')
            fields['reward_kind'].trace_add('write',choices);choices()
            entry(reward_box,'Qtd. / nivel / valor','reward_amount',2,'1')
            entry(reward_box,'Forma','reward_form',3,'0')
            shiny=tk.BooleanVar();ttk.Checkbutton(reward_box,text='Shiny',variable=shiny).grid(row=4,column=1,sticky='w')
            reward_list=tk.Listbox(reward_box,height=4);reward_list.grid(row=6,column=0,columnspan=2,sticky='ew',pady=6)
            def show_rewards():
                reward_list.delete(0,'end')
                for row in rewards:reward_list.insert('end',json.dumps(row,ensure_ascii=False))
            def add_reward():
                try:
                    kind=fields['reward_kind'].get();amount=int(fields['reward_amount'].get());identity=fields['reward_id'].get().strip().upper()
                    if kind=='Item':row=dict(kind='item',id=identity,quantity=amount)
                    elif kind=='Dinheiro':row=dict(kind='money',amount=amount)
                    else:
                        row=dict(kind='pokemon',species=identity,level=1 if kind=='Ovo' else amount,form=int(fields['reward_form'].get()),shiny=shiny.get())
                        if kind=='Ovo':row['egg']=True
                    gifts.rewards_data(rewards+[row]);rewards.append(row);show_rewards()
                except ValueError as error:report(error)
            def remove_reward():
                selected=reward_list.curselection()
                if selected:rewards.pop(selected[0]);show_rewards()
            ttk.Button(reward_box,text='Adicionar recompensa',command=add_reward).grid(row=5,column=0,columnspan=2,sticky='ew')
            ttk.Button(reward_box,text='Remover recompensa',command=remove_reward).grid(row=7,column=0,columnspan=2,sticky='ew')
        ttk.Button(page,text='Salvar / adicionar no rascunho',command=lambda g=group:apply_group(g)).grid(row=1,column=1,sticky='ew',pady=8)
        ttk.Button(page,text='Remover selecionado',command=lambda g=group:remove(g)).grid(row=1,column=0,sticky='w')

    event=pages['community'];event.columnconfigure(1,weight=1)
    for row,(key,label,default) in enumerate([('id','ID do evento','praca-50-v1'),('title','Titulo',''),('target','Meta de batalhas','50'),('coins','Luna Coins por participante','100')]):entry(event,label,'event_'+key,row,default)
    fields['event_enabled']=tk.BooleanVar(value=True);ttk.Checkbutton(event,text='Evento ativo',variable=fields['event_enabled']).grid(row=4,column=1,sticky='w',pady=10)
    ttk.Label(event,text='Uma batalha confirmada soma uma vez para a comunidade.\nPara iniciar outro desafio, use outro ID. Meta e premio de um ID publicado ficam fixos.\nProgresso, moedas e comprovantes anteriores sao preservados.',wraplength=800).grid(row=5,column=0,columnspan=2,sticky='w',pady=15)
    def apply_event():
        nonlocal data
        try:
            candidate=copy.deepcopy(data);candidate['community']={key:fields['event_'+key].get() for key in ('id','title','target','coins','enabled')}
            for key in ('target','coins'):candidate['community'][key]=int(candidate['community'][key])
            data=validate_catalog(candidate);refresh();status.set('Evento salvo no rascunho.')
        except ValueError as error:report(error)
    ttk.Button(event,text='Salvar evento no rascunho',command=apply_event).grid(row=6,column=0,columnspan=2,sticky='ew')

    def export():
        try:
            path=filedialog.asksaveasfilename(parent=root,title='Exportar configuracao Ruby',defaultextension='.rb',initialfile='conteudo-online.rb',filetypes=[('Ruby','*.rb')])
            if path:Path(path).write_text(formats.export_ruby(validate_catalog(data)),encoding='utf-8');status.set('Arquivo Ruby exportado: '+path)
        except (ValueError,OSError) as error:report(error)
    def import_file():
        nonlocal data
        path=filedialog.askopenfilename(parent=root,title='Abrir configuracao local',filetypes=[('Configuracao','*.rb *.json')])
        if not path:return
        try:
            if Path(path).suffix.lower()=='.rb':
                process=subprocess.run([sys.executable.replace('pythonw.exe','python.exe'),str(ROOT/'scripts/online-content-tools.py'),'--read-ruby',path],capture_output=True,encoding='utf-8',timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if process.returncode:raise ValueError(process.stderr.strip() or 'Falha ao interpretar Ruby.')
                incoming=json.loads(process.stdout)
            else:incoming=json.loads(Path(path).read_text(encoding='utf-8-sig'))
            data=validate_catalog(incoming);refresh();status.set('Arquivo carregado no rascunho. Publique para enviar.')
        except (ValueError,OSError,subprocess.TimeoutExpired) as error:report(error)
    ttk.Label(pages['files'],text='Prefere editar em Ruby? Exporte o arquivo, altere os hashes e importe de volta.\nO programa usa o Ruby do jogo local para interpretar e validar os dados.\nO servidor recebe os dados prontos; nao precisa executar Ruby.',wraplength=850).pack(anchor='w',pady=14)
    ttk.Button(pages['files'],text='Exportar arquivo Ruby',command=export).pack(anchor='w',pady=6)
    ttk.Button(pages['files'],text='Importar Ruby ou JSON local',command=import_file).pack(anchor='w',pady=6)

    history=ttk.Treeview(pages['history'],columns=('date',),show='tree headings',selectmode='browse');history.heading('#0',text='Revisao');history.heading('date',text='Publicado em (horario local)');history.pack(fill='both',expand=True)
    ttk.Label(pages['history'],text='Uma restauracao vira uma nova publicacao e preserva o historico.').pack(anchor='w',pady=6)

    def run(payload):
        nonlocal busy
        if busy:return
        secret=token.get().strip()
        if not secret:status.set('Informe o token no campo mascarado.');return
        busy=True;status.set('Consultando Nordeluna no Discloud...')
        for widget in (tabs,):widget.state(['disabled'])
        def work():
            try:events.put((True,gifts.publish(secret,payload,'content'),payload['action']))
            except Exception as error:events.put((False,str(error).replace(secret,'[oculto]'),payload['action']))
        threading.Thread(target=work,daemon=True).start()
    def publish():
        if busy:return
        if current is None or remote_data is None:status.set('Carregue o servidor primeiro para comparar as alteracoes.');return
        try:
            candidate=validate_catalog(data)
            changes=review.content_diff(remote_data,candidate)
            if not changes:status.set('Nenhuma alteracao no rascunho em relacao ao servidor.');return
            if not review.show_preview(root,changes,'Previa do conteudo online',f'{len(changes)} alteracao(oes) / Base: revisao {current}',confirm='Publicar alteracoes'):return
            save_draft(candidate)
            backup=ROOT/'build/admin/backups'/('rascunho-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json');backup.parent.mkdir(parents=True,exist_ok=True);backup.write_text(json.dumps(candidate,ensure_ascii=False,indent=2),encoding='utf-8')
            run(dict(action='set',expected_revision=current,content=candidate))
        except ValueError as error:report(error)
    def historical():
        selected=history.selection()
        if selected:run(dict(action='get_revision',revision=int(selected[0])))
    ttk.Button(pages['history'],text='Consultar historico',command=lambda:run(dict(action='history'))).pack(side='left',pady=8)
    ttk.Button(pages['history'],text='Carregar revisao no rascunho',command=historical).pack(side='left',padx=8)
    ttk.Label(pages['gifts'],text='Crie e encerre codigos de presente sem gerar outro APK.\nOs resgates e limites ficam no banco do servidor.',wraplength=800).pack(anchor='w',pady=18)
    ttk.Button(pages['gifts'],text='Abrir editor de codigos de presente',command=lambda:subprocess.Popen([sys.executable,str(ROOT/'scripts/gift-manager.py')])).pack(anchor='w')

    # Package builder UI is installed by the update tooling below.
    update_panel=module('editor_update_panel','content-update-tools.py')
    update_panel.make_panel(pages['updates'],root,status,token)
    operations.make_testers(pages['testers'],root,status,token,gifts,review)
    operations.make_notices(pages['notices'],root,status,token,gifts,review)
    moderation_panel=moderation.make_owner_panel(pages['moderation'],root,status,token,gifts)

    footer=ttk.Frame(outer);footer.pack(fill='x',pady=(10,0))
    ttk.Button(footer,text='Carregar do servidor',command=lambda:run(dict(action='get'))).pack(side='left')
    ttk.Button(footer,text='Publicar rascunho no servidor',command=publish).pack(side='left',padx=10)
    ttk.Button(footer,text='Salvar arquivo Ruby',command=export).pack(side='right')
    ttk.Label(outer,textvariable=status,wraplength=1000).pack(anchor='w',pady=(10,0))
    def poll():
        nonlocal busy,data,current,remote_data
        while not events.empty():
            ok,result,action=events.get();busy=False;tabs.state(['!disabled'])
            if not ok:status.set('Falha: '+result);continue
            if 'content' in result:
                if action in ('get','set'):remote_data=copy.deepcopy(result['content'])
                data=validate_content(result['content']);current=result['revision'];refresh();revision.set('Servidor: revisao '+str(current))
                status.set('Publicado. Jogadores recebem ao abrir a loja/missoes novamente.' if action=='set' else 'Rascunho carregado. Edite, salve as linhas e publique quando terminar.')
            elif 'history' in result:
                for child in history.get_children():history.delete(child)
                history.insert('','end',iid='0',text='0',values=('Conteudo inicial',))
                for row in result['history']:history.insert('','end',iid=str(row['revision']),text=row['revision'],values=(datetime.fromtimestamp(row['created']).strftime('%d/%m/%Y %H:%M'),))
                status.set('Historico carregado.')
        root.after(150,poll)
    root.protocol('WM_DELETE_WINDOW',lambda:(moderation_panel.close(),token.delete(0,'end'),root.destroy()))
    refresh();poll();root.mainloop()


if __name__=='__main__':main()
