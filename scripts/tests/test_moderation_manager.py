"""Offline transport and review tests; no live accounts, keys or punishments."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import queue
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('moderation_ui_test', ROOT / 'scripts/moderation-panel.py')
ui = importlib.util.module_from_spec(spec); spec.loader.exec_module(ui)
FAKE_KEY = 'nmod_' + '0' * 64
FAKE_ACCOUNT = '1' * 32


class Variable:
    def __init__(self, value=''):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class LocalHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.calls.append((self.path, self.headers.get('Authorization'), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
        if self.server.mode == 'redirect':
            self.send_response(307); self.send_header('Location', '/capture'); self.end_headers(); return
        status = 401 if self.server.mode == 'revoked' else 400 if self.server.mode == 'bad_request' else 200
        body = {'error': 'revoked'} if status == 401 else {'error': 'Conta protegida; chave ' + FAKE_KEY + '\n' + 'detalhe ' * 80} if status == 400 else {'actor': {'id': FAKE_ACCOUNT, 'nickname': 'Teste local', 'role': 'moderator'}}
        raw = json.dumps(body).encode()
        self.send_response(status); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def log_message(self, *args):
        pass


class StaffTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), LocalHandler)
        cls.server.calls = []; cls.server.mode = 'session'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.client = ui.StaffClient(f'http://127.0.0.1:{cls.server.server_port}/moderation')
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=3)
    def setUp(self):
        self.server.calls.clear(); self.server.mode = 'session'
    def test_requires_https_except_loopback_and_rejects_embedded_credentials(self):
        for url in ('http://nordeluna-online.discloud.dev/moderation', 'ftp://localhost/moderation',
                    'https://secret@example.org/moderation', 'https://example.org/api', 'https://example.org/moderation?key=unsafe'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ui.StaffClient(url)
    def test_session_sends_key_in_bearer_header_only(self):
        result = self.client(FAKE_KEY, {'action': 'session'})
        self.assertEqual(result['actor']['id'], FAKE_ACCOUNT)
        path, auth, body = self.server.calls[0]
        self.assertEqual(path, '/moderation'); self.assertEqual(auth, 'Bearer ' + FAKE_KEY)
        self.assertEqual(body, {'action': 'session'})
        self.assertNotIn(FAKE_KEY, json.dumps(body))
    def test_rejected_key_fails_and_is_not_echoed(self):
        self.server.mode = 'revoked'
        with self.assertRaises(ui.StaffAuthorizationError) as context:
            self.client(FAKE_KEY, {'action': 'session'})
        self.assertNotIn(FAKE_KEY, str(context.exception))
    def test_redirect_never_forwards_a_staff_key(self):
        self.server.mode = 'redirect'
        with self.assertRaisesRegex(ValueError, '307'):
            self.client(FAKE_KEY, {'action': 'session'})
        self.assertEqual(len(self.server.calls), 1)
    def test_bad_request_shows_bounded_reason_without_key_or_controls(self):
        self.server.mode = 'bad_request'
        with self.assertRaises(ValueError) as context:
            self.client(FAKE_KEY, {'action': 'accounts'})
        message = str(context.exception)
        self.assertIn('Conta protegida', message); self.assertNotIn(FAKE_KEY, message)
        self.assertLessEqual(len(message), 240); self.assertNotIn('\n', message)
    def test_invalid_keys_and_owner_actions_never_reach_network(self):
        for key, action in [('discloud-token', 'session'), (FAKE_KEY, 'grant'), (FAKE_KEY, 'revoke'), (FAKE_KEY, 'set_owner'), (FAKE_KEY, 'content')]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.client(key, {'action': action})
        self.assertEqual(self.server.calls, [])


class ModerationReviewTests(unittest.TestCase):
    def panel(self):
        panel = ui.ModerationPanel.__new__(ui.ModerationPanel)
        panel.busy = False; panel.connected = True; panel.root = None
        panel.status = Variable(); panel.reason = Variable('Motivo de teste'); panel.minutes = Variable('120')
        panel.run = Mock(); panel._selected_account = lambda: {'id': FAKE_ACCOUNT, 'nickname': 'Conta local', 'role': 'player'}
        return panel
    def test_cancelled_review_never_dispatches_punishment(self):
        panel = self.panel()
        with patch.object(ui, 'review_action', return_value=False) as review:
            panel.account_action('mute')
        review.assert_called_once(); panel.run.assert_not_called()
    def test_mute_sends_minutes_as_seconds_only_after_review(self):
        panel = self.panel()
        with patch.object(ui, 'review_action', return_value=True) as review:
            panel.account_action('mute')
        self.assertIn(FAKE_ACCOUNT, review.call_args.args[2])
        panel.run.assert_called_once_with({'action': 'mute', 'target': FAKE_ACCOUNT, 'reason': 'Motivo de teste', 'seconds': 7200})
    def test_invalid_minutes_and_missing_reason_never_reach_review(self):
        panel = self.panel()
        with patch.object(ui, 'review_action') as review:
            for value in ('0', '121', 'abc', '-5'):
                panel.minutes.set(value); panel.account_action('mute')
            panel.reason.set(''); panel.account_action('ban')
        review.assert_not_called(); panel.run.assert_not_called()
    def test_failed_staff_auth_clears_the_session(self):
        panel = self.panel(); panel.closed = False; panel.events = queue.Queue()
        panel.events.put((False, 'Chave revogada', {'action': 'accounts'}, True))
        panel.set_connected = Mock(); panel.on_auth_error = Mock(); panel._set_controls = Mock(); panel.root = Mock()
        panel._poll()
        panel.set_connected.assert_called_once_with(False); panel.on_auth_error.assert_called_once()
    def test_key_never_survives_error_redaction(self):
        self.assertNotIn(FAKE_KEY, ui.redacted('Falha com ' + FAKE_KEY))
        self.assertNotIn('token-local', ui.redacted('Falha token-local', 'token-local'))
    def test_utc_minus_three_is_fixed(self):
        self.assertEqual(ui.local_time(10800), '01/01/1970 00:00:00')


if __name__ == '__main__':
    unittest.main()
