import http.client
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER_DIR = os.path.join(HERE, '..', '..', 'helper')
sys.path.insert(0, HELPER_DIR)

import keychain  # noqa: E402
import server  # noqa: E402
import store as store_mod  # noqa: E402

FIXTURES = os.path.join(HERE, '..', 'fixtures')
EXT_ORIGIN = 'chrome-extension://abcdefghijklmnopabcdefghijklmnop'


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class CountingStore(store_mod.Store):
    """Records every JSON file the store reads, so refusals can prove they touched nothing."""

    def __init__(self, *a, **kw):
        store_mod.Store.__init__(self, *a, **kw)
        self.reads = []

    def _read_json(self, name, default):
        self.reads.append(name)
        return store_mod.Store._read_json(self, name, default)


class ServerCase(unittest.TestCase):
    def setUp(self):
        base = os.environ.get('TMPDIR') or None
        self.tmp = tempfile.mkdtemp(prefix='jaf-server-', dir=base)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, 'workspace')
        os.makedirs(os.path.join(self.root, 'resume'))
        shutil.copy(os.path.join(FIXTURES, 'master.fixture.md'),
                    os.path.join(self.root, 'resume', 'master.md'))
        self.home = os.path.join(self.tmp, 'home')
        self.store = CountingStore(self.home, root=self.root, env={})
        self.store.ensure()
        self.start()

    def start(self):
        self.httpd, self.warnings = server.create_server(self.store, port=0, env={})
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.token = self.store.token()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(5)

    def request(self, method, path, body=None, token='default', origin='default', headers=None):
        h = dict(headers or {})
        tok = self.token if token == 'default' else token
        org = EXT_ORIGIN if origin == 'default' else origin
        if tok is not None:
            h['X-Job-Autofill-Token'] = tok
        if org is not None:
            h['Origin'] = org
        data = None
        if body is not None:
            data = body if isinstance(body, (bytes, str)) else json.dumps(body)
            h['Content-Type'] = 'application/json'
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            conn.request(method, path, body=data, headers=h)
            r = conn.getresponse()
            return r.status, dict(r.getheaders()), r.read()
        finally:
            conn.close()

    def json(self, *a, **kw):
        status, headers, body = self.request(*a, **kw)
        return status, json.loads(body.decode('utf-8')) if body else None


class F7RefusalTest(ServerCase):
    def test_F7_four_refusals_get_403_empty_body_and_never_touch_the_store(self):
        profile_json = os.path.join(self.home, 'profile.json')
        self.store.save_manual({'country': 'United States'})
        before = os.stat(profile_json).st_atime_ns
        self.store.reads.clear()
        cases = {
            'no token': dict(token=None),
            'wrong token': dict(token='not-the-token'),
            'evil origin': dict(origin='https://evil.example'),
            'no origin': dict(origin=None),
        }
        for label, kw in cases.items():
            status, headers, body = self.request('GET', '/profile', **kw)
            self.assertEqual(status, 403, label)
            self.assertEqual(body, b'', label)
            self.assertNotIn('Access-Control-Allow-Origin', headers, label)
        self.assertEqual(self.store.reads, [])
        self.assertEqual(os.stat(profile_json).st_atime_ns, before)

    def test_F7_extension_origin_with_correct_token_gets_200(self):
        status, payload = self.json('GET', '/profile')
        self.assertEqual(status, 200)
        self.assertEqual(payload['imported']['fullName'], 'Jordan Avery')
        self.assertIn('profile.json', self.store.reads)

    def test_F7_every_route_and_method_refuses_without_credentials(self):
        self.store.reads.clear()
        for method, path in (('GET', '/health'), ('PUT', '/profile'), ('GET', '/resume.pdf'),
                             ('GET', '/config'), ('PUT', '/config'), ('POST', '/runs'),
                             ('GET', '/nope'), ('POST', '/draft'), ('GET', '/models?provider=x')):
            status, _, body = self.request(method, path, body={} if method != 'GET' else None,
                                           token=None, origin='https://evil.example')
            self.assertEqual((status, body), (403, b''), '%s %s' % (method, path))
        self.assertEqual(self.store.reads, [])

    def test_F7_refused_request_with_body_does_not_poison_the_connection(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        conn.request('PUT', '/config', body=json.dumps({'daily_cap': 1}),
                     headers={'Origin': 'https://evil.example'})
        r = conn.getresponse()
        self.assertEqual((r.status, r.read()), (403, b''))
        conn.close()
        self.assertEqual(self.store.config()['daily_cap'], 30)

    def test_F7_preflight_only_for_extension_origins(self):
        status, headers, body = self.request(
            'OPTIONS', '/profile', token=None, origin=EXT_ORIGIN,
            headers={'Access-Control-Request-Method': 'PUT',
                     'Access-Control-Request-Headers': 'x-job-autofill-token'})
        self.assertEqual(status, 204)
        self.assertEqual(body, b'')
        self.assertEqual(headers['Access-Control-Allow-Origin'], EXT_ORIGIN)
        self.assertIn('X-Job-Autofill-Token', headers['Access-Control-Allow-Headers'])
        for origin in ('https://evil.example', None, 'null'):
            status, headers, body = self.request('OPTIONS', '/profile', token=None, origin=origin)
            self.assertEqual((status, body), (403, b''), str(origin))
            self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_F7_empty_extension_origin_is_not_accepted(self):
        status, _, body = self.request('GET', '/health', origin='chrome-extension://')
        self.assertEqual((status, body), (403, b''))


class F8LoopbackTest(unittest.TestCase):
    def make_store(self, config=None):
        base = os.environ.get('TMPDIR') or None
        tmp = tempfile.mkdtemp(prefix='jaf-f8-', dir=base)
        self.addCleanup(shutil.rmtree, tmp, True)
        home = os.path.join(tmp, 'home')
        os.makedirs(home)
        if config is not None:
            with open(os.path.join(home, 'config.json'), 'w') as f:
                json.dump(config, f)
        return store_mod.Store(home, root=tmp, env={})

    def bind(self, store):
        httpd, warnings = server.create_server(store, port=0, env={})
        self.addCleanup(httpd.server_close)
        return httpd, warnings

    def test_F8_default_config_binds_loopback_without_warning(self):
        httpd, warnings = self.bind(self.make_store())
        self.assertEqual(httpd.server_address[0], '127.0.0.1')
        self.assertEqual(warnings, [])

    def test_F8_host_override_is_ignored_with_warning(self):
        for host in ('0.0.0.0', '::', '192.168.1.5', 'example.test'):
            httpd, warnings = self.bind(self.make_store({'host': host}))
            self.assertEqual(httpd.server_address[0], '127.0.0.1', host)
            self.assertEqual(warnings, ['Ignoring host %s; helper binds 127.0.0.1 only' % host])

    def test_F8_host_cannot_be_set_through_put_config(self):
        store = self.make_store()
        with self.assertRaises(ValueError):
            store.save_config({'host': '0.0.0.0'})

    def test_F8_port_comes_from_env_then_config(self):
        store = self.make_store({'port': 9123})
        self.assertEqual(server.resolve_port(store, {}), 9123)
        self.assertEqual(server.resolve_port(store, {'JOB_AUTOFILL_PORT': '9124'}), 9124)
        with self.assertRaises(SystemExit):
            server.resolve_port(store, {'JOB_AUTOFILL_PORT': 'abc'})


class RoutesTest(ServerCase):
    def test_health(self):
        status, payload = self.json('GET', '/health')
        self.assertEqual((status, payload), (200, {'ok': True, 'version': server.VERSION}))

    def test_profile_get_has_documented_keys_and_no_grounding_text(self):
        status, headers, body = self.request('GET', '/profile')
        payload = json.loads(body)
        self.assertEqual(status, 200)
        for key in ('imported', 'manual', 'missing', 'synced_at', 'grounding_hash'):
            self.assertIn(key, payload)
        self.assertEqual(headers['Access-Control-Allow-Origin'], EXT_ORIGIN)
        self.assertNotIn(b'Fabrikam', body)
        self.assertNotIn(b'grounding"', body)

    def test_U3_profile_put_saves_manual_values_and_returns_profile(self):
        status, payload = self.json('PUT', '/profile', {'manual': {
            'country': 'United States', 'workAuthorization': 'Yes', 'needsSponsorship': 'No',
            'veteran': 'Leave blank'}})
        self.assertEqual(status, 200)
        self.assertEqual(payload['manual']['country'], 'United States')
        self.assertEqual(payload['manual']['veteran'], '')
        status, payload = self.json('GET', '/profile')
        self.assertEqual(payload['manual']['needsSponsorship'], 'No')
        self.assertEqual(mode(os.path.join(self.home, 'profile.json')), 0o600)
        # A flat body works too.
        status, payload = self.json('PUT', '/profile', {'zip': '00000'})
        self.assertEqual((status, payload['manual']['zip']), (200, '00000'))
        self.assertEqual(payload['manual']['country'], 'United States')

    def test_profile_put_rejects_bad_fields(self):
        for body in ({'manual': {'fullName': 'X'}}, {'country': 3}, {'nope': 'x'}):
            status, payload = self.json('PUT', '/profile', body)
            self.assertEqual(status, 400, str(body))
            self.assertIn('error', payload)

    def test_F18_missing_resume_markdown_reports_error_and_keeps_import(self):
        self.json('GET', '/profile')
        os.unlink(os.path.join(self.root, 'resume', 'master.md'))
        status, payload = self.json('GET', '/profile')
        self.assertEqual(status, 200)
        self.assertEqual(payload['error'], 'resume/master.md not found')
        self.assertEqual(payload['imported']['fullName'], 'Jordan Avery')

    def test_config_get_and_put(self):
        status, cfg = self.json('GET', '/config')
        self.assertEqual((status, cfg['daily_cap'], cfg['resume_pdf']), (200, 30, ''))
        self.assertNotIn('host', cfg)
        pdf = os.path.join(FIXTURES, 'resume.fixture.pdf')
        status, cfg = self.json('PUT', '/config', {'resume_pdf': pdf, 'provider': 'openai',
                                                   'models': {'openai': 'pick'}})
        self.assertEqual(status, 200)
        self.assertEqual((cfg['resume_pdf'], cfg['provider'], cfg['models']),
                         (pdf, 'openai', {'openai': 'pick'}))
        self.assertEqual(self.json('GET', '/config')[1], cfg)
        self.assertEqual(mode(os.path.join(self.home, 'config.json')), 0o600)

    def test_config_put_rejects_unknown_and_invalid(self):
        for body in ({'host': '0.0.0.0'}, {'provider': 'other'}, {'daily_cap': 'x'}):
            status, payload = self.json('PUT', '/config', body)
            self.assertEqual(status, 400, str(body))
            self.assertIn('error', payload)

    def test_F19_resume_pdf_served_with_name_or_404_message(self):
        expected = 'AutoFill: Resume file not found \u2014 pick it in Profile'
        status, payload = self.json('GET', '/resume.pdf')
        self.assertEqual((status, payload), (404, {'error': expected}))
        pdf = os.path.join(FIXTURES, 'resume.fixture.pdf')
        self.json('PUT', '/config', {'resume_pdf': pdf})
        status, headers, body = self.request('GET', '/resume.pdf')
        with open(pdf, 'rb') as f:
            self.assertEqual(body, f.read())
        self.assertEqual((status, headers['Content-Type']), (200, 'application/pdf'))
        self.assertEqual(headers['X-Resume-Name'], 'resume.fixture.pdf')
        self.json('PUT', '/config', {'resume_pdf': os.path.join(self.tmp, 'deleted.pdf')})
        status, payload = self.json('GET', '/resume.pdf')
        self.assertEqual((status, payload), (404, {'error': expected}))

    def test_resume_pdf_relative_path_resolves_against_workspace_root(self):
        shutil.copy(os.path.join(FIXTURES, 'resume.fixture.pdf'),
                    os.path.join(self.root, 'resume', 'cv.pdf'))
        self.json('PUT', '/config', {'resume_pdf': 'resume/cv.pdf'})
        status, headers, _ = self.request('GET', '/resume.pdf')
        self.assertEqual((status, headers['X-Resume-Name']), (200, 'cv.pdf'))

    def test_U21_runs_appends_only_documented_keys(self):
        status, payload = self.json('POST', '/runs', {
            'host': 'boards.example.test', 'path': '/jobs/1', 'ats': 'greenhouse', 'green': 8,
            'yellow': 0, 'ai_drafts': 0, 'ai_calls': 0, 'steps': 1, 'outcome': 'filled',
            'email': 'jordan.avery@example.test'})
        self.assertEqual((status, payload), (200, {'ok': True}))
        with open(os.path.join(self.home, 'runs.jsonl'), encoding='utf-8') as f:
            line = f.read()
        rec = json.loads(line)
        self.assertEqual(list(rec), list(store_mod.RUN_KEYS))
        self.assertNotIn('jordan', line)
        self.assertEqual(mode(os.path.join(self.home, 'runs.jsonl')), 0o600)
        status, payload = self.json('POST', '/runs', {'green': 'many'})
        self.assertEqual(status, 400)

    def test_bad_bodies_and_unknown_routes(self):
        self.assertEqual(self.request('PUT', '/config', body='{nope')[0], 400)
        self.assertEqual(self.request('PUT', '/config', body='[1]')[0], 400)
        self.assertEqual(self.request('GET', '/nope')[0], 404)
        self.assertEqual(self.request('DELETE', '/profile')[0], 501)

    def test_oversized_body_is_refused_before_reading(self):
        s = socket.create_connection(('127.0.0.1', self.port), timeout=10)
        try:
            s.sendall(('PUT /config HTTP/1.1\r\nHost: x\r\nOrigin: %s\r\nX-Job-Autofill-Token: %s\r\n'
                       'Content-Length: %d\r\n\r\n' % (EXT_ORIGIN, self.token, 2 * 1024 * 1024))
                      .encode())
            self.assertTrue(s.recv(64).startswith(b'HTTP/1.1 413'))
        finally:
            s.close()

    def _raw(self, request_line, extra=''):
        s = socket.create_connection(('127.0.0.1', self.port), timeout=10)
        try:
            s.sendall(('%s HTTP/1.1\r\nHost: x\r\nOrigin: %s\r\nX-Job-Autofill-Token: %s\r\n%s\r\n'
                       % (request_line, EXT_ORIGIN, self.token, extra)).encode())
            data = b''
            while b'\r\n\r\n' not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            return data.split(b'\r\n\r\n')[0].decode('latin-1')
        finally:
            s.close()

    def test_negative_content_length_is_a_400_and_closes_the_connection(self):
        head = self._raw('PUT /config', 'Content-Length: -5\r\n')
        self.assertTrue(head.startswith('HTTP/1.1 400'), head)
        self.assertIn('Connection: close', head)
        head = self._raw('POST /draft', 'Content-Length: abc\r\n')
        self.assertTrue(head.startswith('HTTP/1.1 400'), head)
        self.assertIn('Connection: close', head)

    def test_unknown_route_closes_the_connection_so_an_unread_body_cannot_leak(self):
        head = self._raw('POST /nope', 'Content-Length: 4\r\n')
        self.assertTrue(head.startswith('HTTP/1.1 404'), head)
        self.assertIn('Connection: close', head)

    def test_a_normal_response_keeps_the_connection_open(self):
        head = self._raw('GET /health')
        self.assertTrue(head.startswith('HTTP/1.1 200'), head)
        self.assertNotIn('Connection: close', head)


class CliTest(unittest.TestCase):
    def setUp(self):
        base = os.environ.get('TMPDIR') or None
        self.tmp = tempfile.mkdtemp(prefix='jaf-cli-', dir=base)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, 'home')
        self.kc = os.path.join(self.tmp, 'kc.json')
        self.env = {'JOB_AUTOFILL_HOME': self.home, 'JOB_AUTOFILL_KEYCHAIN': 'fake:' + self.kc}

    def test_U14_set_key_saves_to_keychain_and_never_echoes_the_key(self):
        out, err = io.StringIO(), io.StringIO()
        secret = 'fixture-secret-key-0001'
        rc = server.cmd_set_key('anthropic', self.env, getpass_fn=lambda prompt: secret + '\n',
                                out=out, err=err)
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), 'Saved key for anthropic in Keychain (job-autofill-anthropic)\n')
        self.assertNotIn(secret, out.getvalue() + err.getvalue())
        self.assertEqual(keychain.get('anthropic', env=self.env), secret)
        out = io.StringIO()
        server.cmd_set_key('openai', self.env, getpass_fn=lambda p: 'k2', out=out, err=err)
        self.assertEqual(out.getvalue(), 'Saved key for openai in Keychain (job-autofill-openai)\n')
        # Nothing about the key lands under JOB_AUTOFILL_HOME.
        self.assertFalse(os.path.exists(self.home))

    def test_set_key_rejects_unknown_provider_and_empty_input(self):
        err = io.StringIO()
        self.assertEqual(server.cmd_set_key('other-vendor', self.env, getpass_fn=lambda p: 'x',
                                            out=io.StringIO(), err=err), 2)
        self.assertEqual(server.cmd_set_key('openai', self.env, getpass_fn=lambda p: '  ',
                                            out=io.StringIO(), err=err), 1)
        self.assertFalse(os.path.exists(self.kc))

    def test_set_key_prompt_is_hidden_getpass_by_default(self):
        with mock.patch('getpass.getpass', return_value='k3') as gp:
            rc = server.cmd_set_key('openai', self.env, out=io.StringIO(), err=io.StringIO())
        self.assertEqual(rc, 0)
        gp.assert_called_once()

    def test_main_usage_error(self):
        with mock.patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(server.main(['bogus'], self.env), 2)
            self.assertEqual(server.main(['set-key'], self.env), 2)

    def run_helper(self, *args, **extra):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **self.env)
        env.update(extra)
        return subprocess.Popen([sys.executable, os.path.join(HELPER_DIR, 'server.py')] + list(args),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                universal_newlines=True)

    def serve_once(self, **extra):
        """Start `serve`, collect output up to the listening line, stop it."""
        proc = self.run_helper('serve', JOB_AUTOFILL_PORT=str(free_port()), **extra)
        lines = []
        try:
            for line in iter(proc.stdout.readline, ''):
                lines.append(line.rstrip('\n'))
                if line.startswith('Helper listening on'):
                    break
        finally:
            proc.terminate()
            proc.wait(10)
            proc.stdout.close()
        return lines

    def test_U1_token_printed_once_on_first_start_and_by_pair_only(self):
        first = self.serve_once()
        self.assertTrue(first[0].startswith('Pairing token: '), first)
        token = first[0][len('Pairing token: '):]
        self.assertGreaterEqual(len(token), 32)
        self.assertTrue(first[-1].startswith('Helper listening on 127.0.0.1:'), first)
        with open(os.path.join(self.home, 'token')) as f:
            self.assertEqual(f.read().strip(), token)
        self.assertEqual(mode(self.home), 0o700)
        for name in ('token', 'config.json'):
            self.assertEqual(mode(os.path.join(self.home, name)), 0o600, name)

        second = self.serve_once()
        self.assertEqual(len(second), 1, second)
        self.assertTrue(second[0].startswith('Helper listening on'))
        self.assertNotIn(token, '\n'.join(second))

        pair = self.run_helper('pair')
        out = pair.communicate(timeout=20)[0]
        self.assertEqual(out.strip(), 'Pairing token: ' + token)

    def test_F8_serve_prints_the_ignored_host_warning(self):
        os.makedirs(self.home, mode=0o700)
        with open(os.path.join(self.home, 'config.json'), 'w') as f:
            json.dump({'host': '0.0.0.0'}, f)
        lines = self.serve_once()
        self.assertIn('Ignoring host 0.0.0.0; helper binds 127.0.0.1 only', lines)
        self.assertTrue(lines[-1].startswith('Helper listening on 127.0.0.1:'))

    def test_serve_honors_port_env_and_resume_env(self):
        port = free_port()
        md = os.path.join(self.tmp, 'm.md')
        with open(md, 'w') as f:
            f.write('# Pat Quinn\n')
        proc = self.run_helper('serve', JOB_AUTOFILL_PORT=str(port), JOB_AUTOFILL_RESUME_MD=md)
        try:
            lines = []
            for line in iter(proc.stdout.readline, ''):
                lines.append(line)
                if line.startswith('Helper listening on'):
                    break
            self.assertIn('127.0.0.1:%d' % port, lines[-1])
            with open(os.path.join(self.home, 'token')) as f:
                token = f.read().strip()
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            conn.request('GET', '/profile', headers={'Origin': EXT_ORIGIN,
                                                     'X-Job-Autofill-Token': token})
            payload = json.loads(conn.getresponse().read())
            conn.close()
            self.assertEqual(payload['imported']['fullName'], 'Pat Quinn')
        finally:
            proc.terminate()
            proc.wait(10)
            proc.stdout.close()


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


if __name__ == '__main__':
    unittest.main()
