#!/usr/bin/env python3
"""Job-autofill helper: a 127.0.0.1-only HTTP API for the Chrome extension.

    server.py [serve]          run the helper
    server.py pair             print the pairing token
    server.py set-key <name>   store an API key (anthropic | openai) in the macOS Keychain

Environment: JOB_AUTOFILL_HOME, JOB_AUTOFILL_PORT, JOB_AUTOFILL_KEYCHAIN (fake:<file>),
JOB_AUTOFILL_RESUME_MD, JOB_AUTOFILL_ANTHROPIC_URL, JOB_AUTOFILL_OPENAI_URL.
"""
import getpass
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ai  # noqa: E402
import keychain  # noqa: E402
import store as store_mod  # noqa: E402

VERSION = '0.1.0'
BIND_HOST = '127.0.0.1'
EXTENSION_ORIGIN = 'chrome-extension://'
MAX_BODY = 1024 * 1024
RESUME_MISSING = 'AutoFill: Resume file not found \u2014 pick it in Profile'


class ApiError(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status = status
        self.message = message


def _extension_origin(origin):
    return origin.startswith(EXTENSION_ORIGIN) and len(origin) > len(EXTENSION_ORIGIN)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'job-autofill-helper'

    def log_message(self, fmt, *args):  # no request logging: paths and origins stay out of logs
        pass

    # ---- plumbing --------------------------------------------------------------------
    def _origin(self):
        return self.headers.get('Origin', '')

    def _cors(self):
        origin = self._origin()
        if _extension_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Expose-Headers', 'X-Resume-Name')
            self.send_header('Vary', 'Origin')

    def _send(self, status, body=b'', content_type=None, headers=None):
        self.send_response(status)
        if content_type:
            self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        if self.close_connection:
            self.send_header('Connection', 'close')
        self.send_header('Cache-Control', 'no-store')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self._cors()
        self.end_headers()
        if body and self.command != 'HEAD':
            self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload).encode('utf-8'), 'application/json')

    def _refuse(self):
        self.close_connection = True  # an unread request body must not leak into the next request
        self.send_response(403)
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'close')
        self.end_headers()

    def _authorized(self):
        if not _extension_origin(self._origin()):
            return False
        sent = self.headers.get('X-Job-Autofill-Token', '')
        return hmac.compare_digest(sent.encode('utf-8'), self.server.token.encode('utf-8'))

    def _body(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True  # the body, if any, was not read
            raise ApiError(400, 'bad Content-Length')
        if length > MAX_BODY:
            self.close_connection = True
            raise ApiError(413, 'request body too large')
        raw = self.rfile.read(length) if length else b''
        try:
            data = json.loads(raw.decode('utf-8')) if raw else None
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, 'body is not valid JSON')
        if not isinstance(data, dict):
            raise ApiError(400, 'body must be a JSON object')
        return data

    def _dispatch(self, method):
        # Authorization comes first: a refused request never reaches the store.
        if not self._authorized():
            return self._refuse()
        path = urlsplit(self.path).path
        route = self.ROUTES.get((method, path))
        if route is None:
            self.close_connection = True  # a body of an unknown route is never read
            return self._json(404, {'error': 'not found'})
        try:
            getattr(self, route)()
        except ApiError as e:
            self._json(e.status, {'error': e.message})
        except Exception as e:  # keep details out of the response and the log
            sys.stderr.write('helper error on %s %s: %s\n' % (method, path, type(e).__name__))
            self._json(500, {'error': 'internal error'})

    def do_GET(self):
        self._dispatch('GET')

    def do_PUT(self):
        self._dispatch('PUT')

    def do_POST(self):
        # Chrome sends no Origin header on GETs an extension makes to a host it has permission
        # for (PUT/POST carry it), so the extension reads through POST + this header. A plain
        # GET without an extension Origin is still refused.
        if self.headers.get('X-HTTP-Method-Override') == 'GET':
            if self.headers.get('Content-Length', '0').strip() not in ('', '0'):
                self.close_connection = True  # a GET's body is never read
            return self._dispatch('GET')
        self._dispatch('POST')

    def do_OPTIONS(self):
        origin = self._origin()
        if not _extension_origin(origin):
            return self._refuse()
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Job-Autofill-Token, X-HTTP-Method-Override, Content-Type')
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', '0')
        self.end_headers()

    # ---- routes ----------------------------------------------------------------------
    ROUTES = {
        ('GET', '/health'): 'r_health',
        ('GET', '/profile'): 'r_profile_get',
        ('PUT', '/profile'): 'r_profile_put',
        ('GET', '/resume.pdf'): 'r_resume',
        ('GET', '/config'): 'r_config_get',
        ('PUT', '/config'): 'r_config_put',
        ('POST', '/runs'): 'r_runs',
        ('GET', '/models'): 'r_models',
        ('POST', '/draft'): 'r_draft',
    }

    @property
    def store(self):
        return self.server.store

    def r_health(self):
        self._json(200, {'ok': True, 'version': VERSION})

    def r_profile_get(self):
        self._json(200, self.store.profile())

    def r_profile_put(self):
        body = self._body()
        values = body['manual'] if isinstance(body.get('manual'), dict) else body
        try:
            self.store.save_manual(values)
        except ValueError as e:
            raise ApiError(400, str(e))
        self._json(200, self.store.profile())

    def r_resume(self):
        path = self.store.resume_pdf()
        try:
            data = path.read_bytes() if path is not None and path.is_file() else None
        except OSError:
            data = None
        if data is None:
            return self._json(404, {'error': RESUME_MISSING})
        self._send(200, data, 'application/pdf', {
            'X-Resume-Name': quote(path.name),
            'Content-Disposition': 'inline; filename="resume.pdf"',
        })

    def r_config_get(self):
        self._json(200, self.store.config())

    def r_config_put(self):
        try:
            cfg = self.store.save_config(self._body())
        except ValueError as e:
            raise ApiError(400, str(e))
        self._json(200, cfg)

    def r_runs(self):
        try:
            self.store.append_run(self._body())
        except ValueError as e:
            raise ApiError(400, str(e))
        self._json(200, {'ok': True})

    def r_models(self):
        provider = parse_qs(urlsplit(self.path).query).get('provider', [''])[0]
        try:
            models = ai.list_models(provider, env=self.store.env)
        except ValueError:
            raise ApiError(400, 'provider must be one of: %s' % ', '.join(store_mod.PROVIDERS))
        except ai.AiError as e:
            return self._json(200, {'error': e.message})
        self._json(200, {'models': models})

    def r_draft(self):
        self._json(200, ai.draft(self._body(), self.store))


class HelperServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler, store, token):
        ThreadingHTTPServer.__init__(self, addr, handler)
        self.store = store
        self.token = token


# ---- startup ---------------------------------------------------------------------------
def bind_host(store):
    """Always loopback. A non-loopback `host` in config.json is ignored with a warning."""
    requested = store.raw_config().get('host')
    warnings = []
    if requested is not None and requested != BIND_HOST:
        warnings.append('Ignoring host %s; helper binds 127.0.0.1 only' % requested)
    return BIND_HOST, warnings


def resolve_port(store, env):
    raw = env.get('JOB_AUTOFILL_PORT')
    if raw:
        try:
            port = int(raw)
        except ValueError:
            port = 0
        if not 0 < port < 65536:
            raise SystemExit('JOB_AUTOFILL_PORT must be a port number, got %r' % raw)
        return port
    return store.config()['port']


def create_server(store, port=None, env=None):
    """Returns (httpd, warnings). `port` defaults to env/config; 0 picks a free port."""
    env = env if env is not None else os.environ
    host, warnings = bind_host(store)
    if port is None:
        port = resolve_port(store, env)
    httpd = HelperServer((host, port), Handler, store, store.token())
    return httpd, warnings


def make_store(env):
    return store_mod.Store(env.get('JOB_AUTOFILL_HOME') or store_mod.DEFAULT_HOME, env=env)


def cmd_serve(env=None, out=None, err=None):
    env = env if env is not None else os.environ
    out = out or sys.stdout
    err = err or sys.stderr
    store = make_store(env)
    token, created = store.ensure()  # the token file exists before the port opens
    if created:
        out.write('Pairing token: %s\n' % token)
        out.flush()
    try:
        httpd, warnings = create_server(store, env=env)
    except OSError as e:
        err.write('Cannot listen on %s: %s\n' % (BIND_HOST, e))
        return 1
    for w in warnings:
        err.write(w + '\n')
    err.flush()
    out.write('Helper listening on %s:%d\n' % httpd.server_address[:2])
    out.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def cmd_pair(env=None, out=None):
    env = env if env is not None else os.environ
    (out or sys.stdout).write('Pairing token: %s\n' % make_store(env).ensure()[0])
    return 0


def cmd_set_key(provider, env=None, getpass_fn=None, out=None, err=None):
    env = env if env is not None else os.environ
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        service = keychain.service_for(provider)
    except ValueError as e:
        err.write('%s\n' % e)
        return 2
    key = (getpass_fn or getpass.getpass)('API key for %s (hidden): ' % provider).strip()
    if not key:
        err.write('No key entered; nothing saved.\n')
        return 1
    try:
        keychain.set(provider, key, env=env)
    except (keychain.KeychainError, ValueError) as e:
        err.write('Could not save the key: %s\n' % e)
        return 1
    out.write('Saved key for %s in Keychain (%s)\n' % (provider, service))
    return 0


def main(argv=None, env=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    env = env if env is not None else os.environ
    cmd = argv[0] if argv else 'serve'
    if cmd == 'serve' and len(argv) <= 1:
        return cmd_serve(env)
    if cmd == 'pair' and len(argv) == 1:
        return cmd_pair(env)
    if cmd == 'set-key' and len(argv) == 2:
        return cmd_set_key(argv[1], env)
    sys.stderr.write('usage: server.py [serve] | pair | set-key anthropic|openai\n')
    return 2


if __name__ == '__main__':
    sys.exit(main())
