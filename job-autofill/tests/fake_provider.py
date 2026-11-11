#!/usr/bin/env python3
"""Fake AI provider for tests: Anthropic-shaped and OpenAI-shaped endpoints on 127.0.0.1.

    python3 tests/fake_provider.py <port>

Provider endpoints (every request below is recorded):
    GET  /v1/models              Anthropic shape when the request has `x-api-key`, else OpenAI shape
    POST /v1/messages            Anthropic Messages
    POST /v1/chat/completions    OpenAI Chat Completions
Control endpoints (not recorded):
    GET  /__requests             JSON array of {method, path, headers, body}
    POST /__mode                 {"mode": <mode>, "reply": <optional text>}

Modes: ok, 401, 429, 500, slow (25 s), malformed, echo (replies with the user message).
`reply` replaces the ok text.
The model ids are opaque test strings.
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELS = {
    'anthropic': ['fake-anthropic-a', 'fake-anthropic-b'],
    'openai': ['fake-openai-a', 'fake-openai-b'],
}
OK_REPLY = 'I enjoy building reliable systems and would bring that experience to this team.'
SLOW_SECONDS = 25
MODES = ('ok', '401', '429', '500', 'slow', 'malformed', 'echo')


class FakeState(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = 'ok'
        self.reply = None
        self.requests = []
        self.stopping = threading.Event()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass

    @property
    def state(self):
        return self.server.state

    def _send(self, status, payload=None, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b''
        try:
            return json.loads(raw.decode('utf-8')) if raw else None
        except ValueError:
            return raw.decode('utf-8', 'replace')

    # ---- control ---------------------------------------------------------------------
    def _control(self, method):
        if self.path == '/__requests' and method == 'GET':
            with self.state.lock:
                self._send(200, list(self.state.requests))
            return True
        if self.path == '/__mode' and method == 'POST':
            body = self._read_body()
            mode = body.get('mode') if isinstance(body, dict) else None
            if mode not in MODES:
                self._send(400, {'error': 'unknown mode %r' % (mode,)})
                return True
            with self.state.lock:
                self.state.mode = mode
                reply = body.get('reply')
                self.state.reply = reply if isinstance(reply, str) else None
            self._send(200, {'mode': mode})
            return True
        return False

    # ---- provider --------------------------------------------------------------------
    def _handle(self, method):
        if self._control(method):
            return
        body = self._read_body() if method == 'POST' else None
        with self.state.lock:
            self.state.requests.append({
                'method': method,
                'path': self.path,
                'headers': {k.lower(): v for k, v in self.headers.items()},
                'body': body,
            })
            mode, reply = self.state.mode, self.state.reply
        route = (method, self.path.split('?', 1)[0])
        if route not in (('GET', '/v1/models'), ('POST', '/v1/messages'),
                         ('POST', '/v1/chat/completions')):
            return self._send(404, {'error': 'not found'})
        if mode == 'slow':
            self.state.stopping.wait(SLOW_SECONDS)
        if mode in ('401', '429', '500'):
            return self._send(int(mode), {'error': {'message': 'fake %s' % mode}})
        if mode == 'malformed':
            return self._send(200, raw=b'{"not json')
        anthropic = 'x-api-key' in self.headers
        if route == ('GET', '/v1/models'):
            return self._models(anthropic)
        text = self._text(mode, reply, body, anthropic=route[1] == '/v1/messages')
        if route[1] == '/v1/messages':
            return self._send(200, {
                'id': 'msg_fake', 'type': 'message', 'role': 'assistant',
                'content': [{'type': 'text', 'text': text}],
                'stop_reason': 'end_turn',
            })
        return self._send(200, {
            'id': 'chatcmpl-fake', 'object': 'chat.completion',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': text}}],
        })

    def _models(self, anthropic):
        ids = MODELS['anthropic' if anthropic else 'openai']
        if anthropic:
            data = [{'type': 'model', 'id': i, 'display_name': i} for i in ids]
            return self._send(200, {'data': data, 'has_more': False,
                                    'first_id': ids[0], 'last_id': ids[-1]})
        return self._send(200, {'object': 'list',
                                'data': [{'id': i, 'object': 'model'} for i in ids]})

    @staticmethod
    def _text(mode, reply, body, anthropic):
        if mode == 'echo':
            messages = (body or {}).get('messages') or []
            users = [m for m in messages if isinstance(m, dict) and m.get('role') == 'user']
            content = users[-1].get('content') if users else ''
            return content if isinstance(content, str) else json.dumps(content)
        if reply is not None:
            return reply
        return OK_REPLY

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')


class FakeProvider(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=0):
        ThreadingHTTPServer.__init__(self, ('127.0.0.1', port), Handler)
        self.state = FakeState()

    def shutdown(self):
        self.state.stopping.set()  # wake any `slow` handler
        ThreadingHTTPServer.shutdown(self)


def main(argv):
    if len(argv) != 2:
        sys.stderr.write('usage: fake_provider.py <port>\n')
        return 2
    httpd = FakeProvider(int(argv[1]))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
