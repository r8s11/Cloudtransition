"""Helper state under JOB_AUTOFILL_HOME (dir 0700, files 0600).

Files: config.json, profile.json (manual fields), imported.json (last good resume import),
token, answers.json (draft cache), runs.jsonl (run log), usage.json (AI calls per day).
"""
import datetime
import hashlib
import json
import os
import secrets
import tempfile
import threading
from pathlib import Path

import profile_import

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOME = '~/.config/job-autofill'
DEFAULT_PORT = 8766
PROVIDERS = ('anthropic', 'openai')

CONFIG_DEFAULTS = {
    'port': DEFAULT_PORT,
    'provider': 'anthropic',
    'models': {},
    'daily_cap': 30,
    'resume_pdf': '',
    'resume_markdown': 'resume/master.md',
}
MANUAL_KEYS = (
    'street', 'zip', 'country', 'workAuthorization', 'needsSponsorship',
    'gender', 'race', 'veteran', 'disability',
)
RUN_KEYS = ('time', 'host', 'path', 'ats', 'green', 'yellow', 'ai_drafts', 'ai_calls',
            'steps', 'outcome')
BLANK = 'Leave blank'

_KNOWN_FILES = ('config.json', 'profile.json', 'imported.json', 'token',
                'answers.json', 'runs.jsonl', 'usage.json')


def _now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


class Store(object):
    def __init__(self, home, root=None, env=None):
        self.home = Path(os.path.expanduser(str(home)))
        self.root = Path(root) if root is not None else WORKSPACE_ROOT
        self.env = env if env is not None else os.environ
        self._lock = threading.RLock()
        os.makedirs(str(self.home), mode=0o700, exist_ok=True)
        os.chmod(str(self.home), 0o700)

    # ---- low-level files -------------------------------------------------------------
    def _read_json(self, name, default):
        try:
            with open(str(self.home / name), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def _write_text(self, name, text):
        # mkstemp creates 0600; os.replace keeps that mode.
        fd, tmp = tempfile.mkstemp(dir=str(self.home), prefix='.' + name + '.')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(text)
            os.replace(tmp, str(self.home / name))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _write_json(self, name, obj):
        self._write_text(name, json.dumps(obj, indent=2, sort_keys=True) + '\n')

    def ensure(self):
        """Create config.json and the token, and tighten modes. Returns (token, token_created)."""
        with self._lock:
            os.chmod(str(self.home), 0o700)
            if not (self.home / 'config.json').exists():
                self._write_json('config.json', self.config())
            token, created = self.ensure_token()
            for name in _KNOWN_FILES:
                p = self.home / name
                if p.exists():
                    os.chmod(str(p), 0o600)
            return token, created

    # ---- config ----------------------------------------------------------------------
    def raw_config(self):
        data = self._read_json('config.json', {})
        return data if isinstance(data, dict) else {}

    def config(self):
        raw = self.raw_config()
        cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in CONFIG_DEFAULTS.items()}
        for k in CONFIG_DEFAULTS:
            if k in raw and self._config_value_ok(k, raw[k]):
                cfg[k] = raw[k]
        return cfg

    @staticmethod
    def _config_value_ok(key, v):
        if key == 'port':
            return _is_int(v) and 1 <= v <= 65535
        if key == 'provider':
            return v in PROVIDERS
        if key == 'models':
            return (isinstance(v, dict) and all(k in PROVIDERS and isinstance(m, str)
                                                for k, m in v.items()))
        if key == 'daily_cap':
            return _is_int(v) and v >= 0
        if key == 'resume_pdf':
            return isinstance(v, str)
        if key == 'resume_markdown':
            return isinstance(v, str) and bool(v.strip())
        return False

    def save_config(self, patch):
        """Merge `patch` into config.json. Unknown or invalid keys raise ValueError."""
        if not isinstance(patch, dict):
            raise ValueError('config must be a JSON object')
        for k, v in patch.items():
            if k not in CONFIG_DEFAULTS:
                raise ValueError('unknown config key: %s' % k)
            if not self._config_value_ok(k, v):
                raise ValueError('invalid value for config key: %s' % k)
        with self._lock:
            cfg = self.config()
            for k, v in patch.items():
                if k == 'models':
                    cfg['models'] = dict(cfg['models'], **v)
                else:
                    cfg[k] = v
            self._write_json('config.json', cfg)
            return cfg

    # ---- token -----------------------------------------------------------------------
    def ensure_token(self):
        with self._lock:
            path = self.home / 'token'
            try:
                existing = path.read_text(encoding='utf-8').strip()
            except OSError:
                existing = ''
            if existing:
                return existing, False
            token = secrets.token_urlsafe(32)
            self._write_text('token', token + '\n')
            return token, True

    def token(self):
        return self.ensure_token()[0]

    # ---- resume locations ------------------------------------------------------------
    def _resolve(self, raw):
        p = Path(os.path.expanduser(raw))
        return p if p.is_absolute() else self.root / p

    def resume_markdown(self):
        """(path, display name). The env override wins over config."""
        raw = self.env.get('JOB_AUTOFILL_RESUME_MD') or self.config()['resume_markdown']
        return self._resolve(raw), raw

    def resume_pdf(self):
        raw = self.config()['resume_pdf']
        return self._resolve(raw) if raw.strip() else None

    def _read_resume(self):
        """(text, error). `error` is a display string when the file cannot be read."""
        path, display = self.resume_markdown()
        if not path.is_file():
            return None, '%s not found' % display
        try:
            return path.read_text(encoding='utf-8', errors='replace'), None
        except OSError:
            return None, '%s could not be read' % display

    def grounding(self):
        """(grounding_text, grounding_hash) from the resume right now, or None if unreadable."""
        text, error = self._read_resume()
        if error:
            return None
        _, grounding, _ = profile_import.parse(text)
        return grounding, hashlib.sha256(grounding.encode('utf-8')).hexdigest()

    # ---- profile ---------------------------------------------------------------------
    def _manual(self):
        data = self._read_json('profile.json', {})
        if not isinstance(data, dict):
            data = {}
        return {k: (data[k] if isinstance(data.get(k), str) else '') for k in MANUAL_KEYS}

    def profile(self):
        """Re-reads the resume every call. A missing file keeps the last good import."""
        with self._lock:
            text, error = self._read_resume()
            cached = self._read_json('imported.json', None)
            if error is None:
                fields, grounding, missing = profile_import.parse(text)
                cached = {
                    'fields': fields,
                    'missing': missing,
                    'grounding_hash': hashlib.sha256(grounding.encode('utf-8')).hexdigest(),
                    'synced_at': _now_iso(),
                }
                self._write_json('imported.json', cached)
            if not isinstance(cached, dict) or not isinstance(cached.get('fields'), dict):
                cached = {'fields': {k: '' for k in profile_import.FIELD_KEYS}, 'missing': [],
                          'grounding_hash': '', 'synced_at': None}
            return {
                'imported': cached['fields'],
                'manual': self._manual(),
                'missing': cached.get('missing', []),
                'synced_at': cached.get('synced_at'),
                'grounding_hash': cached.get('grounding_hash', ''),
                'source': self.resume_markdown()[1],
                'error': error,
            }

    def save_manual(self, values):
        if not isinstance(values, dict):
            raise ValueError('manual profile must be a JSON object')
        for k, v in values.items():
            if k not in MANUAL_KEYS:
                raise ValueError('unknown profile field: %s' % k)
            if not isinstance(v, str):
                raise ValueError('profile field %s must be a string' % k)
        with self._lock:
            merged = self._manual()
            for k, v in values.items():
                merged[k] = '' if v.strip() == BLANK else v
            self._write_json('profile.json', merged)
            return merged

    # ---- run log ---------------------------------------------------------------------
    def append_run(self, rec):
        """Append one run record. Only the documented keys are kept; values are type-checked."""
        if not isinstance(rec, dict):
            raise ValueError('run record must be a JSON object')
        out = {'time': rec.get('time', '') or _now_iso()}
        if not isinstance(out['time'], str):
            raise ValueError('run field time must be a string')
        for k in ('host', 'path', 'ats'):
            v = rec.get(k, '')
            if not isinstance(v, str):
                raise ValueError('run field %s must be a string' % k)
            out[k] = v
        for k in ('green', 'yellow', 'ai_drafts', 'ai_calls', 'steps'):
            v = rec.get(k, 0)
            if not _is_int(v) or v < 0:
                raise ValueError('run field %s must be a non-negative integer' % k)
            out[k] = v
        outcome = rec.get('outcome', '')
        if not isinstance(outcome, str):
            raise ValueError('run field outcome must be a string')
        out['outcome'] = outcome
        line = json.dumps(out, sort_keys=False) + '\n'
        with self._lock:
            fd = os.open(str(self.home / 'runs.jsonl'), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, line.encode('utf-8'))
            finally:
                os.close(fd)
        return out

    # ---- answer cache ----------------------------------------------------------------
    def answers_get(self, key):
        data = self._read_json('answers.json', {})
        return data.get(key) if isinstance(data, dict) else None

    def answers_put(self, key, value):
        with self._lock:
            data = self._read_json('answers.json', {})
            if not isinstance(data, dict):
                data = {}
            data[key] = value
            self._write_json('answers.json', data)

    # ---- daily AI-call counter -------------------------------------------------------
    @staticmethod
    def _day(now):
        if now is None:
            now = datetime.datetime.now()
        elif isinstance(now, (int, float)):
            now = datetime.datetime.fromtimestamp(now)
        return now.date().isoformat()

    def ai_calls_today(self, now=None):
        usage = self._read_json('usage.json', {})
        if isinstance(usage, dict) and usage.get('date') == self._day(now) and _is_int(usage.get('count')):
            return usage['count']
        return 0

    def count_ai_call(self, now=None):
        with self._lock:
            n = self.ai_calls_today(now) + 1
            self._write_json('usage.json', {'date': self._day(now), 'count': n})
            return n
