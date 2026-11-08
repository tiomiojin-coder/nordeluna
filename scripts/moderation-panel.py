"""Shared moderation widgets and the restricted HTTPS staff transport.

This module never imports the Discloud client. The owner window supplies its
existing console transport; the separate staff window supplies StaffClient.
"""
import csv
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import queue
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = 'https://nordeluna-online.discloud.dev/moderation'
LOCAL_ZONE = timezone(timedelta(hours=-3))
STAFF_KEY = re.compile(r'nmod_[0-9a-f]{64}')
ACCOUNT_ID = re.compile(r'[0-9a-f]{32}')
READ_ACTIONS = {'session', 'accounts', 'history', 'audit'}
STAFF_ACTIONS = READ_ACTIONS | {'mute', 'unmute', 'kick', 'ban', 'unban', 'hide_message', 'restore_message'}
ACTION_LABELS = {'set_owner': 'Marcar como minha conta', 'grant': 'Conceder / renovar chave',
                 'revoke': 'Revogar moderador', 'mute': 'Silenciar chat', 'unmute': 'Retirar silencio',
                 'kick': 'Retirar da praca por 60 segundos', 'ban': 'Banir acesso online',
                 'unban': 'Retirar ban online', 'hide_message': 'Ocultar mensagem',
                 'restore_message': 'Restaurar mensagem'}


class StaffAuthorizationError(ValueError):
    pass


def redacted(value, secret=''):
    result = str(value)
    if secret:
        result = result.replace(secret, '[oculto]')
    return STAFF_KEY.sub('[chave oculta]', result)


def local_time(value):
    if not value:
        return '-'
    try:
        return datetime.fromtimestamp(value, LOCAL_ZONE).strftime('%d/%m/%Y %H:%M:%S')
    except (ValueError, TypeError, OSError, OverflowError):
        return '-'


def checked_endpoint(endpoint):
    parsed = urllib.parse.urlsplit(endpoint)
    try:
        local = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname or '').is_loopback
    except ValueError:
        local = False
    if (parsed.scheme != 'https' and not (parsed.scheme == 'http' and local)) or not parsed.hostname:
        raise ValueError('A moderacao exige HTTPS; HTTP so e permitido no localhost de teste.')
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != '/moderation':
        raise ValueError('Endereco de moderacao invalido.')
    return endpoint


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        return None


class StaffClient:
    """A staff key can only call the dedicated moderation endpoint."""
    def __init__(self, endpoint=ENDPOINT):
        self.endpoint = checked_endpoint(endpoint)
        self.opener = urllib.request.build_opener(NoRedirect())

    def __call__(self, secret, payload):
        if not STAFF_KEY.fullmatch(secret):
            raise StaffAuthorizationError('Chave de moderador invalida.')
        if payload.get('action') not in STAFF_ACTIONS:
            raise ValueError('Esta janela nao gerencia a equipe administrativa.')
        request = urllib.request.Request(self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), method='POST',
            headers={'Authorization': 'Bearer ' + secret, 'Content-Type': 'application/json',
                     'Accept': 'application/json', 'User-Agent': 'Nordeluna-Moderation/0.10.0'})
        try:
            with self.opener.open(request, timeout=25) as response:
                raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise ValueError('Resposta de moderacao grande demais.')
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                error.close()
                raise StaffAuthorizationError('Chave revogada, invalida ou acesso de moderacao suspenso.') from None
            if error.code == 400:
                try:
                    body = error.read(4097)
                    failure = json.loads(body) if len(body) <= 4096 else None
                    if isinstance(failure, dict) and isinstance(failure.get('error'), str):
                        message = redacted(failure['error'], secret)
                        message = ''.join(char if ord(char) >= 32 else ' ' for char in message)[:240]
                        if message:
                            raise ValueError(message) from None
                except (OSError, UnicodeError, json.JSONDecodeError):
                    pass
                finally:
                    error.close()
            # Never echo headers or URLs from transport exceptions.
            error.close()
            raise ValueError('O servidor recusou a consulta de moderacao (HTTP ' + str(error.code) + ').') from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise ValueError('Nao foi possivel consultar o servidor. Confira a conexao e tente novamente.') from None
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError('O servidor retornou uma resposta invalida.') from None
        if not isinstance(result, dict):
            raise ValueError('Resposta de moderacao invalida.')
        if result.get('error') or result.get('ok') is False:
            raise ValueError(redacted(result.get('error', 'Acao de moderacao recusada.'), secret))
        if payload['action'] == 'session':
            actor = result.get('actor', {})
            if actor.get('role') != 'moderator' or not ACCOUNT_ID.fullmatch(str(actor.get('id', ''))):
                raise StaffAuthorizationError('O servidor nao confirmou a sessao de moderador.')
        return result


def review_action(parent, title, details):
    """Every write needs an explicit review in the local window."""
    import tkinter as tk
    from tkinter import ttk
    dialog = tk.Toplevel(parent)
    dialog.title('Conferir moderacao'); dialog.transient(parent)
    dialog.geometry('650x385'); dialog.minsize(520, 330)
    body = ttk.Frame(dialog, padding=18); body.pack(fill='both', expand=True)
    ttk.Label(body, text=title, font=('Segoe UI', 15, 'bold'), wraplength=590).pack(anchor='w')
    text = tk.Text(body, height=9, wrap='word', padx=10, pady=8)
    text.insert('1.0', details); text.configure(state='disabled'); text.pack(fill='both', expand=True, pady=14)
    accepted = False
    def finish():
        nonlocal accepted
        accepted = True; dialog.destroy()
    actions = ttk.Frame(body); actions.pack(fill='x')
    ttk.Button(actions, text='Voltar', command=dialog.destroy).pack(side='left')
    ttk.Button(actions, text='Confirmar acao', command=finish).pack(side='right')
    dialog.bind('<Escape>', lambda event: dialog.destroy())
    dialog.grab_set(); parent.wait_window(dialog)
    return accepted


def show_issued_key(parent, key, target):
    """One presentation, masked, with clipboard cleanup when it still matches."""
    import tkinter as tk
    from tkinter import ttk
    if not isinstance(key, str) or not STAFF_KEY.fullmatch(key):
        raise ValueError('O servidor nao retornou uma chave valida.')
    dialog = tk.Toplevel(parent); dialog.title('Chave de moderador emitida')
    dialog.transient(parent); dialog.geometry('650x290'); dialog.minsize(560, 265)
    body = ttk.Frame(dialog, padding=18); body.pack(fill='both', expand=True)
    ttk.Label(body, text='Entregue esta chave ao moderador por um canal privado.', wraplength=590).pack(anchor='w')
    ttk.Label(body, text='Conta: ' + target, wraplength=590).pack(anchor='w', pady=8)
    ttk.Label(body, text='Exibida apenas nesta janela. Ao fechar, ela nao podera ser recuperada.\nRenovar invalida a chave anterior. Nenhum arquivo sera criado.', wraplength=590).pack(anchor='w')
    secret = tk.StringVar(value=key)
    field = ttk.Entry(body, textvariable=secret, show='*', state='readonly')
    field.pack(fill='x', pady=12)
    copied = False
    note = tk.StringVar(value='A chave permanece mascarada.')
    def copy():
        nonlocal copied
        dialog.clipboard_clear(); dialog.clipboard_append(secret.get()); copied = True
        note.set('Copiada localmente. A copia sera limpa ao fechar esta janela.')
    def close():
        if copied:
            try:
                if dialog.clipboard_get() == secret.get():
                    dialog.clipboard_clear()
            except tk.TclError:
                pass
        secret.set(''); dialog.destroy()
    actions = ttk.Frame(body); actions.pack(fill='x')
    ttk.Button(actions, text='Copiar chave', command=copy).pack(side='left')
    ttk.Button(actions, text='Fechar e descartar', command=close).pack(side='right')
    ttk.Label(body, textvariable=note, wraplength=590).pack(anchor='w', pady=9)
    dialog.protocol('WM_DELETE_WINDOW', close); dialog.bind('<Escape>', lambda event: close())
    key = ''; dialog.grab_set(); parent.wait_window(dialog)


class ModerationPanel:
    def __init__(self, parent, root, status, secret_getter, transport, owner=False, on_session=None, on_auth_error=None):
        import tkinter as tk
        from tkinter import ttk
        self.root = root; self.status = status; self.secret_getter = secret_getter
        self.transport = transport; self.owner = owner
        self.on_session = on_session; self.on_auth_error = on_auth_error
        self.events = queue.Queue(); self.busy = False; self.connected = owner; self.closed = False
        self.buttons = []; self.accounts = {}; self.messages = {}; self.audit_rows = []
        self.accounts_offset = 0; self.account_query = ''; self.history_before = None; self.audit_before = None
        self.actor = tk.StringVar(value='Administrador via Discloud' if owner else 'Entre com sua chave para consultar o servidor.')
        ttk.Label(parent, textvariable=self.actor, wraplength=790).pack(anchor='w', pady=(0, 5))
        self.tabs = ttk.Notebook(parent); self.tabs.pack(fill='both', expand=True)
        self.pages = {}
        for key, title in [('accounts', 'Contas'), ('history', 'Historico do chat'), ('audit', 'Auditoria')]:
            page = ttk.Frame(self.tabs, padding=7); self.tabs.add(page, text=title); self.pages[key] = page
        self.search = tk.StringVar(); self.selection = tk.StringVar(value='Selecione uma conta cadastrada pelo ID.')
        self.reason = tk.StringVar(); self.minutes = tk.StringVar(value='10')
        self.account_page = tk.StringVar(value='Nenhuma conta carregada.')
        self.room = tk.StringVar(value='PRACA'); self.history_target = tk.StringVar()
        self.history_page = tk.StringVar(value='Mensagens preservadas, inclusive as ocultas.')
        self.audit_page = tk.StringVar(value='Horario de todas as listas: UTC-3.')
        self._make_accounts(); self._make_history(); self._make_audit()
        self._set_controls(); self._poll()

    def _button(self, parent, text, command):
        from tkinter import ttk
        button = ttk.Button(parent, text=text, command=command); self.buttons.append(button)
        return button

    def _table(self, parent, columns, height=5):
        from tkinter import ttk
        frame = ttk.Frame(parent); frame.pack(fill='both', expand=True)
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=tuple(row[0] for row in columns), show='headings', height=height, selectmode='browse')
        for key, title, width in columns:
            table.heading(key, text=title); table.column(key, width=width, minwidth=45, stretch=False)
        vertical = ttk.Scrollbar(frame, orient='vertical', command=table.yview)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.grid(row=0, column=0, sticky='nsew'); vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        # The table's many columns scroll horizontally instead of widening a tab.
        frame.configure(width=500, height=150); frame.grid_propagate(False)
        return table

    def _make_accounts(self):
        from tkinter import ttk
        page = self.pages['accounts']
        search = ttk.Frame(page); search.pack(fill='x', pady=(0, 5))
        ttk.Label(search, text='Nick / ID:').pack(side='left')
        entry = ttk.Entry(search, textvariable=self.search, width=24); entry.pack(side='left', padx=5)
        entry.bind('<Return>', lambda event: self.load_accounts())
        self._button(search, 'Pesquisar / atualizar', self.load_accounts).pack(side='left')
        self._button(search, 'Anterior', lambda: self.load_accounts(max(0, self.accounts_offset - 100))).pack(side='left', padx=5)
        self._button(search, 'Proximas 100', lambda: self.load_accounts(self.accounts_offset + 100)).pack(side='left')
        self._button(search, 'CSV', lambda: self.export_csv('accounts')).pack(side='right')
        ttk.Label(page, textvariable=self.account_page).pack(anchor='w')
        self.account_table = self._table(page, [
            ('nickname', 'Nick', 135), ('id', 'ID da conta', 265), ('role', 'Papel', 95),
            ('created', 'Cadastro (UTC-3)', 165), ('updated', 'Atualizada (UTC-3)', 165),
            ('muted_until', 'Silencio ate (UTC-3)', 165), ('kicked_until', 'Fora da praca ate (UTC-3)', 175),
            ('banned', 'Ban online', 80)])
        self.account_table.bind('<<TreeviewSelect>>', self._account_selected)
        ttk.Label(page, textvariable=self.selection, wraplength=790).pack(anchor='w', pady=(5, 3))
        reason = ttk.Frame(page); reason.pack(fill='x', pady=3)
        ttk.Label(reason, text='Motivo:').pack(side='left')
        ttk.Entry(reason, textvariable=self.reason).pack(side='left', fill='x', expand=True, padx=5)
        actions = ttk.Frame(page); actions.pack(fill='x', pady=3)
        ttk.Label(actions, text='Minutos:').pack(side='left')
        ttk.Spinbox(actions, from_=1, to=120, textvariable=self.minutes, width=4).pack(side='left', padx=(4, 7))
        for label, action in [('Silenciar', 'mute'), ('Retirar silencio', 'unmute'), ('Kick praca (60s)', 'kick'), ('Ban online', 'ban'), ('Retirar ban', 'unban')]:
            self._button(actions, label, lambda a=action: self.account_action(a)).pack(side='left', padx=2)
        if self.owner:
            team = ttk.Frame(page); team.pack(fill='x', pady=3)
            for label, action in [('Marcar como minha conta', 'set_owner'), ('Conceder / renovar chave', 'grant'), ('Revogar moderador', 'revoke')]:
                self._button(team, label, lambda a=action: self.account_action(a)).pack(side='left', padx=2)

    def _make_history(self):
        import tkinter as tk
        from tkinter import ttk
        page = self.pages['history']
        filters = ttk.Frame(page); filters.pack(fill='x', pady=(0, 5))
        ttk.Label(filters, text='Sala:').pack(side='left')
        ttk.Entry(filters, textvariable=self.room, width=10).pack(side='left', padx=4)
        ttk.Label(filters, text='Conta (ID):').pack(side='left')
        ttk.Entry(filters, textvariable=self.history_target, width=27).pack(side='left', padx=4)
        self._button(filters, 'Usar conta selecionada', self._filter_selected).pack(side='left')
        self._button(filters, 'CSV', lambda: self.export_csv('history')).pack(side='right')
        controls = ttk.Frame(page); controls.pack(fill='x', pady=(0, 4))
        self._button(controls, 'Recentes / filtrar', self.load_history).pack(side='left')
        self._button(controls, '100 anteriores', lambda: self.load_history(older=True)).pack(side='left', padx=5)
        ttk.Label(controls, text='Sala vazia = todas; PRACA ou codigo de 8 letras/numeros.').pack(side='left', padx=5)
        self.history_table = self._table(page, [('id', '#', 55), ('timestamp', 'Quando (UTC-3)', 165),
            ('room', 'Sala', 100), ('nickname', 'Nick', 125), ('hidden', 'Oculta', 60), ('text', 'Mensagem', 400),
            ('account_id', 'ID da conta', 265), ('build', 'Build', 115)])
        self.message_details = tk.Text(page, height=3, wrap='word', state='disabled')
        self.message_details.pack(fill='x', pady=4)
        self.history_table.bind('<<TreeviewSelect>>', self._message_selected)
        reason = ttk.Frame(page); reason.pack(fill='x', pady=3)
        ttk.Label(reason, text='Motivo:').pack(side='left')
        ttk.Entry(reason, textvariable=self.reason).pack(side='left', fill='x', expand=True, padx=5)
        actions = ttk.Frame(page); actions.pack(fill='x', pady=3)
        self._button(actions, 'Conferir e ocultar', lambda: self.message_action('hide_message')).pack(side='left')
        self._button(actions, 'Conferir e restaurar', lambda: self.message_action('restore_message')).pack(side='left', padx=5)
        ttk.Label(page, textvariable=self.history_page, wraplength=790).pack(anchor='w')

    def _make_audit(self):
        from tkinter import ttk
        page = self.pages['audit']
        actions = ttk.Frame(page); actions.pack(fill='x', pady=(0, 6))
        self._button(actions, 'Atualizar auditoria', self.load_audit).pack(side='left')
        self._button(actions, '100 anteriores', lambda: self.load_audit(older=True)).pack(side='left', padx=5)
        self._button(actions, 'Exportar pagina CSV', lambda: self.export_csv('audit')).pack(side='right')
        self.audit_table = self._table(page, [('id', '#', 55), ('timestamp', 'Quando (UTC-3)', 165),
            ('actor', 'Quem', 145), ('action', 'Acao', 165), ('target', 'ID da conta', 265), ('detail', 'Motivo / detalhe', 500)])
        ttk.Label(page, textvariable=self.audit_page, wraplength=790).pack(anchor='w', pady=5)

    def _set_controls(self):
        for button in self.buttons:
            button.state(['!disabled'] if self.connected and not self.busy else ['disabled'])

    def set_connected(self, value):
        self.connected = value
        if not value:
            self.actor.set('Entre com sua chave para consultar o servidor.')
            self.accounts.clear(); self.messages.clear(); self.audit_rows.clear()
            for table in (self.account_table, self.history_table, self.audit_table):
                table.delete(*table.get_children())
            self._details(''); self.selection.set('Selecione uma conta cadastrada pelo ID.')
            self.reason.set(''); self.history_target.set('')
            self.history_before = self.audit_before = None
            self.account_page.set('Nenhuma conta carregada.')
        self._set_controls()

    def close(self):
        self.closed = True; self.connected = False
        self.secret_getter = lambda: ''
        while not self.events.empty():
            self.events.get()

    def run(self, payload, session=False):
        if self.closed or self.busy:
            return False
        if not self.connected and not session:
            self.status.set('Entre com sua chave de moderador.'); return False
        secret = self.secret_getter().strip()
        if not secret:
            self.status.set('Informe o token Discloud mascarado.' if self.owner else 'Informe sua chave de moderador mascarada.')
            return False
        self.busy = True; self._set_controls(); self.status.set('Consultando moderacao...')
        def work():
            try:
                result = self.transport(secret, payload)
                if not self.closed:
                    self.events.put((True, result, payload, False))
            except Exception as error:
                if not self.closed:
                    self.events.put((False, redacted(error, secret), payload, isinstance(error, StaffAuthorizationError)))
        threading.Thread(target=work, daemon=True).start()
        return True

    def _poll(self):
        if self.closed:
            return
        while not self.events.empty():
            ok, result, payload, auth_error = self.events.get(); self.busy = False
            if not ok:
                self.status.set('Falha: ' + result)
                if auth_error or payload['action'] == 'session':
                    self.set_connected(False)
                    if self.on_auth_error:
                        self.on_auth_error()
            else:
                try:
                    self._received(result, payload)
                except (ValueError, TypeError, KeyError) as error:
                    self.status.set('Falha ao interpretar moderacao: ' + redacted(error))
            self._set_controls()
        self.root.after(100, self._poll)

    def _received(self, result, payload):
        action = payload['action']
        actor = result.get('actor')
        if actor:
            self.actor.set(('Administrador: ' if self.owner else 'Moderador: ') + actor.get('nickname', '') + ' | ID: ' + actor.get('id', ''))
        if action == 'session':
            self.set_connected(True)
            if self.on_session:
                self.on_session(result['actor'])
            self.status.set('Sessao de moderacao validada. Carregue as contas para comecar.')
        elif action == 'accounts':
            self.accounts_offset = payload.get('offset', 0); self.account_query = payload.get('search', '')
            self.account_table.delete(*self.account_table.get_children()); self.accounts.clear()
            for row in result['accounts']:
                self.accounts[row['id']] = row
                self.account_table.insert('', 'end', iid=row['id'], values=(row['nickname'], row['id'], row['role'],
                    local_time(row['created']), local_time(row['updated']), local_time(row['muted_until']),
                    local_time(row['kicked_until']), 'Sim' if row['banned'] else 'Nao'))
            count = len(self.accounts)
            self.account_page.set(f"Pagina {self.accounts_offset // 100 + 1}: {count} conta(s) | Total cadastrado: {result['total']} | UTC-3")
            self.selection.set('Selecione uma conta cadastrada pelo ID.')
            self.status.set('Contas reais do servidor carregadas. Toda alteracao exige revisao.')
        elif action == 'history':
            self._history_filters = (payload.get('room', 'PRACA'), payload.get('target', ''))
            self.history_before = result.get('next_before')
            self.messages = {str(row['id']): row for row in result['messages']}
            self.history_table.delete(*self.history_table.get_children()); self._details('')
            for identity, row in self.messages.items():
                self.history_table.insert('', 'end', iid=identity, values=(row['id'], local_time(row['timestamp']),
                    row['room'], row['nickname'], 'Sim' if row['hidden'] else 'Nao', row['text'], row['account_id'], row['build']))
            self.history_page.set(f'{len(self.messages)} mensagem(ns). Ocultar preserva o registro; restaurar reexibe no chat.')
            self.status.set('Historico do chat carregado (UTC-3).')
        elif action == 'audit':
            self.audit_before = result.get('next_before'); self.audit_rows = result['audit']
            self.audit_table.delete(*self.audit_table.get_children())
            for row in self.audit_rows:
                self.audit_table.insert('', 'end', iid=str(row['id']), values=(row['id'], local_time(row['timestamp']),
                    row['actor'], ACTION_LABELS.get(row['action'], row['action']), row['target'], row['detail']))
            self.audit_page.set(f'{len(self.audit_rows)} registro(s). Quem, acao, conta e motivo; horario UTC-3.')
            self.status.set('Auditoria carregada.')
        else:
            key = result.pop('moderator_key', None)
            if key:
                try:
                    show_issued_key(self.root, key, payload['target'])
                finally:
                    key = ''
            self.status.set(ACTION_LABELS.get(action, action) + ': servidor confirmou a acao. Atualize as listas para conferir.')
            if action in ('hide_message', 'restore_message'):
                row = self.messages.get(str(payload['message_id']))
                if row:
                    row['hidden'] = action == 'hide_message'
                    self.history_table.set(str(row['id']), 'hidden', 'Sim' if row['hidden'] else 'Nao')
                    self._message_selected()
            else:
                self.load_accounts(self.accounts_offset)

    def load_accounts(self, offset=0):
        query = self.search.get().strip()
        if len(query) > 48:
            self.status.set('Pesquisa: use ate 48 caracteres.'); return
        if query != self.account_query:
            offset = 0
        self.run(dict(action='accounts', search=query, offset=offset, limit=100))

    def _selected_account(self):
        selected = self.account_table.selection()
        return self.accounts.get(selected[0]) if selected else None

    def _account_selected(self, event=None):
        row = self._selected_account()
        if row:
            self.selection.set(row['nickname'] + ' | ID: ' + row['id'] + ' | Papel: ' + row['role'])

    def _validated_reason(self):
        reason = self.reason.get().strip()
        if not 1 <= len(reason) <= 200 or any(ord(char) < 32 for char in reason):
            raise ValueError('Informe um motivo de 1 a 200 caracteres, sem quebras de linha.')
        return reason

    def account_action(self, action):
        if self.busy or not self.connected:
            return
        row = self._selected_account()
        if not row:
            self.status.set('Selecione uma conta cadastrada na lista.'); return
        try:
            reason = self._validated_reason(); payload = dict(action=action, target=row['id'], reason=reason)
            extra = ''
            if action == 'mute':
                try:
                    minutes = int(self.minutes.get())
                except ValueError:
                    raise ValueError('Silencio: informe de 1 a 120 minutos.') from None
                if not 1 <= minutes <= 120:
                    raise ValueError('Silencio: informe de 1 a 120 minutos.')
                payload['seconds'] = minutes * 60; extra = f'\nDuracao: {minutes} minuto(s).'
            if action == 'kick':
                extra = '\nRetira da praca geral por 60 segundos.'
            elif action == 'set_owner':
                extra = '\nConfirme que este ID e da SUA conta. O nick nao comprova propriedade.\nEsta conta passa a ser o proprietario protegido pelo servidor.'
            elif action == 'grant':
                extra = '\nEmite uma chave exclusiva de moderacao e invalida qualquer chave anterior desta conta.'
            elif action == 'revoke':
                extra = '\nA chave desta conta perde o acesso imediatamente.'
            details = f"Conta: {row['nickname']}\nID: {row['id']}\nPapel atual: {row['role']}\nMotivo: {reason}" + extra
            if review_action(self.root, ACTION_LABELS[action], details):
                self.run(payload)
        except ValueError as error:
            self.status.set(str(error))

    def _filter_selected(self):
        row = self._selected_account()
        if row:
            self.history_target.set(row['id'])
        else:
            self.status.set('Selecione primeiro uma conta na aba Contas.')

    def load_history(self, older=False):
        room = self.room.get().strip().upper(); target = self.history_target.get().strip()
        if room not in ('', 'PRACA') and not re.fullmatch(r'[A-Z2-9]{8}', room):
            self.status.set('Sala: PRACA, codigo de 8 letras/numeros ou vazio para todas.'); return
        if target and not ACCOUNT_ID.fullmatch(target):
            self.status.set('Filtro de conta: informe o ID completo de uma conta cadastrada.'); return
        filters = (room, target)
        if older and getattr(self, '_history_filters', None) != filters:
            self.status.set('Os filtros mudaram. Clique em Recentes / filtrar.'); return
        payload = dict(action='history', room=room, target=target, limit=100)
        if older:
            if not self.history_before:
                self.status.set('Nao ha mensagens anteriores nesta consulta.'); return
            payload['before'] = self.history_before
        self.run(payload)

    def _details(self, value):
        self.message_details.configure(state='normal'); self.message_details.delete('1.0', 'end')
        self.message_details.insert('1.0', value); self.message_details.configure(state='disabled')

    def _message_selected(self, event=None):
        selected = self.history_table.selection(); row = self.messages.get(selected[0]) if selected else None
        if row:
            self._details(f"#{row['id']} | {local_time(row['timestamp'])} UTC-3 | {row['nickname']} | Conta: {row['account_id']}\n" + row['text'])

    def message_action(self, action):
        if self.busy or not self.connected:
            return
        selected = self.history_table.selection(); row = self.messages.get(selected[0]) if selected else None
        if not row:
            self.status.set('Selecione uma mensagem no historico.'); return
        try:
            reason = self._validated_reason()
            details = f"Mensagem #{row['id']} | Sala: {row['room']}\nConta: {row['nickname']} [{row['account_id']}]\nTexto: {row['text']}\nMotivo: {reason}\nO registro permanece no historico."
            if review_action(self.root, ACTION_LABELS[action], details):
                self.run(dict(action=action, message_id=row['id'], reason=reason))
        except ValueError as error:
            self.status.set(str(error))

    def load_audit(self, older=False):
        payload = dict(action='audit', limit=100)
        if older:
            if not self.audit_before:
                self.status.set('Nao ha registros anteriores nesta consulta.'); return
            payload['before'] = self.audit_before
        self.run(payload)

    def export_csv(self, kind):
        from tkinter import filedialog
        rows = list(self.accounts.values()) if kind == 'accounts' else list(self.messages.values()) if kind == 'history' else list(self.audit_rows)
        if not rows:
            self.status.set('Carregue uma pagina antes de exportar.'); return
        path = filedialog.asksaveasfilename(parent=self.root, title='Exportar pagina carregada',
            defaultextension='.csv', initialfile='moderacao-' + kind + '.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        try:
            fields = list(rows[0])
            with Path(path).open('w', encoding='utf-8-sig', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=fields, delimiter=';'); writer.writeheader()
                for source in rows:
                    row = dict(source)
                    for name in ('created', 'updated', 'timestamp', 'muted_until', 'kicked_until'):
                        if name in row:
                            row[name] = local_time(row[name]) + ' UTC-3' if row[name] else ''
                    # Prevent player-controlled nick/chat text from becoming a spreadsheet formula.
                    for name, value in row.items():
                        if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
                            row[name] = "'" + value
                    writer.writerow(row)
            self.status.set('Pagina exportada em CSV local: ' + path)
        except OSError as error:
            self.status.set('Falha ao exportar CSV: ' + str(error))


def make_owner_panel(parent, root, status, token, manager):
    return ModerationPanel(parent, root, status, token.get,
        lambda secret, payload: manager.publish(secret, payload, 'moderation'), owner=True)
