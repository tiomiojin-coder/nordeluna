"""Real HTTP connections: bounded pooling, framing safety and timing metadata."""
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

spec=importlib.util.spec_from_file_location('latency_relay',Path(__file__).resolve().parents[2]/'server/relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)


class LatencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=relay.RelayHTTPServer(('127.0.0.1',0),relay.Handler)
        self.server.store=relay.Store(str(Path(self.temp.name)/'test.sqlite3'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.clients=[]
    def tearDown(self):
        for client in self.clients:client.close()
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server.store.db.close();self.temp.cleanup()
    def client(self):
        client=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        self.clients.append(client);return client
    def health(self,client):
        client.request('GET','/health');reply=client.getresponse();body=json.loads(reply.read())
        self.assertEqual(reply.status,200);self.assertTrue(body['ok'])
        self.assertGreaterEqual(body['server_ms'],0)
        return reply,body
    def test_reuses_socket_and_recycles_after_sixteen_responses(self):
        client=self.client();ports=[]
        for _ in range(15):
            reply,_=self.health(client);self.assertEqual(reply.getheader('Connection'),'keep-alive')
            ports.append(client.sock.getsockname()[1])
        self.assertEqual(len(set(ports)),1)
        reply,_=self.health(client);self.assertEqual(reply.getheader('Connection'),'close')
        self.health(client)
    def test_diagnostics_remain_readable_by_installed_integer_only_clients(self):
        def unsupported_decimal(value):
            raise AssertionError('Installed game JSON codec cannot read decimal numbers: '+value)
        client=self.client()
        for method,path,request in [('GET','/health',None),('POST','/api',json.dumps(dict(protocol=1,action='health')))]:
            client.request(method,path,request,{'Content-Type':'application/json'})
            response=client.getresponse()
            payload=json.loads(response.read(),parse_float=unsupported_decimal)
            self.assertEqual(response.status,200)
            self.assertTrue(payload['ok'])
            self.assertIs(type(payload['server_ms']),int)
    def test_idle_pool_leaves_workers_available(self):
        for _ in range(8):self.assertEqual(self.health(self.client())[0].getheader('Connection'),'keep-alive')
        reply,_=self.health(self.client())
        self.assertEqual(reply.getheader('Connection'),'close')
    def test_invalid_framing_closes_without_interpreting_second_request(self):
        for header in [b'Content-Length: -1',b'Content-Length: 300000',b'Content-Length: 2\r\nContent-Length: 2',b'Transfer-Encoding: chunked']:
            with socket.create_connection(('127.0.0.1',self.server.server_port),timeout=3) as stream:
                stream.sendall(b'POST /api HTTP/1.1\r\nHost: localhost\r\n'+header+b'\r\n\r\n{}GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n')
                result=b''
                while True:
                    try:chunk=stream.recv(4096)
                    except ConnectionResetError:break
                    if not chunk:break
                    result+=chunk
                self.assertIn(b'400 Bad Request',result)
                self.assertIn(b'Connection: close',result)
                self.assertEqual(result.count(b'HTTP/1.1'),1)
    def test_valid_api_error_does_not_poison_next_request(self):
        client=self.client();client.request('POST','/api',json.dumps(dict(protocol=1,action='missing')),{'Content-Type':'application/json'})
        reply=client.getresponse();body=json.loads(reply.read())
        self.assertEqual(reply.status,400);self.assertFalse(body['ok']);self.assertIn('server_ms',body)
        self.health(client)


if __name__=='__main__':unittest.main()
