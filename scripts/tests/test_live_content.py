import copy
import importlib.util
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
from server.content import DEFAULT_CONTENT,validate_content
from server.relay import Store


class LiveContentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'relay.sqlite3');self.store=Store(self.path);self.addCleanup(lambda:self.store.db.close())
        self.account=dict(id=secrets.token_hex(16),secret=secrets.token_hex(32))
        self.call('account_register',nickname='Lunar')
    def call(self,action,**data):return self.store.handle(dict(protocol=1,action=action,account=self.account,**data))
    def publish(self,data,revision=0):return self.store.content_admin(dict(action='set',content=data,expected_revision=revision))
    def test_live_edits_preserve_claims_and_reject_stale_admin(self):
        self.call('economy_sync');self.call('economy_claim',mission='visit')
        data=copy.deepcopy(DEFAULT_CONTENT);data['missions']['visit']['coins']=40
        data['shop']['balls5']['price']=33
        result=self.publish(data)
        self.assertEqual(result['revision'],1)
        self.assertEqual(self.call('economy_claim',mission='visit')['balance'],10)
        with self.assertRaises(ValueError):self.publish(DEFAULT_CONTENT)
        reopened=Store(self.path)
        try:
            self.assertEqual(reopened.content_admin(dict(action='get'))['content']['shop']['balls5']['price'],33)
            self.assertEqual(reopened.balance(self.account['id']),10)
        finally:reopened.db.close()
    def test_new_store_instance_edit_reaches_running_server(self):
        self.call('economy_sync')
        editor=Store(self.path);data=copy.deepcopy(DEFAULT_CONTENT);data['missions']['visit']['title']='Nova visita'
        try:editor.content_admin(dict(action='set',content=data,expected_revision=0))
        finally:editor.db.close()
        self.store._content_checked=0
        self.assertEqual(self.call('economy_sync')['missions'][0]['title'],'Nova visita')
    def test_noctgeist_removed_but_completed_orders_remain_recoverable(self):
        self.assertNotIn('noctgeist',{r['id'] for r in self.call('economy_sync')['shop']})
        with self.store.db:self.store.credit(self.account['id'],'test',200)
        with self.assertRaises(ValueError):self.call('economy_buy',sku='noctgeist',order='1'*32)
        claim=self.call('economy_buy',sku='aipom_egg',order='2'*32)['claim']
        data=copy.deepcopy(DEFAULT_CONTENT);data['shop'].pop('aipom_egg');self.publish(data)
        self.assertEqual(self.call('economy_buy',sku='aipom_egg',order='2'*32)['claim']['id'],claim['id'])
        self.assertEqual(self.call('economy_order',order='2'*32)['balance'],120)
    def test_price_change_does_not_charge_more_than_preview(self):
        with self.store.db:self.store.credit(self.account['id'],'test',200)
        data=copy.deepcopy(DEFAULT_CONTENT);data['shop']['balls5']['price']=40;self.publish(data)
        with self.assertRaises(ValueError):self.call('economy_buy',sku='balls5',order='3'*32,expected_price=25)
        self.assertEqual(self.store.balance(self.account['id']),200)
        self.assertEqual(self.call('economy_buy',sku='balls5',order='3'*32,expected_price=40)['balance'],160)
    def test_invalid_edits_do_not_replace_published_config(self):
        for change in [lambda d:d['shop']['balls5'].update(price=-1),lambda d:d['missions']['visit'].update(target=3),lambda d:d['community'].update(id='visit'),lambda d:d['missions']['visit'].update(kind='battle'),lambda d:d['community'].update(target=5)]:
            data=copy.deepcopy(DEFAULT_CONTENT);change(data)
            with self.assertRaises(ValueError):self.publish(data)
            self.assertEqual(self.store.content_admin(dict(action='get'))['revision'],0)
    def test_disabled_and_new_missions_are_live_without_duplicate_old_rewards(self):
        data=copy.deepcopy(DEFAULT_CONTENT);data['missions']['visit']['enabled']=False
        data['missions']['welcome2']=dict(title='Nova visita',kind='visit',target=1,coins=15,enabled=True)
        self.publish(data)
        view=self.call('economy_sync')
        self.assertNotIn('visit',[r['id'] for r in view['missions']])
        self.assertEqual(self.call('economy_claim',mission='welcome2')['balance'],15)
        with self.assertRaises(ValueError):self.call('economy_claim',mission='visit')
    def test_player_cannot_administer_content(self):
        before=self.store.content_admin(dict(action='get'))
        for action in ('content_admin','content_set','update_admin'):
            with self.assertRaises(Exception):self.call(action,content=DEFAULT_CONTENT,expected_revision=0)
        self.assertEqual(self.store.content_admin(dict(action='get')),before)
    def test_historical_revision_is_read_only_until_published_again(self):
        data=copy.deepcopy(DEFAULT_CONTENT);data['missions']['visit']['title']='Edicao 1';self.publish(data)
        old=self.store.content_admin(dict(action='get_revision',revision=0))
        self.assertEqual(old['revision'],1);self.assertEqual(old['source_revision'],0)
        self.assertEqual(self.store.content_admin(dict(action='get'))['content'],data)
        self.assertEqual(self.publish(old['content'],1)['revision'],2)


class RubyContentTests(unittest.TestCase):
    def test_ruby_roundtrip_in_child_process_has_no_string_interpolation(self):
        import subprocess,sys
        spec=importlib.util.spec_from_file_location('online_formats',ROOT/'scripts/online-content-tools.py');formats=importlib.util.module_from_spec(spec);spec.loader.exec_module(formats)
        data=copy.deepcopy(DEFAULT_CONTENT);data['missions']['visit']['title']="Lua #{raise 'erro'} \\ ' teste"
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.rb';path.write_text(formats.export_ruby(data),encoding='utf-8')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/online-content-tools.py'),'--read-ruby',str(path)],capture_output=True,text=True,encoding='utf-8',timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout),data)
