"""API keys in the macOS Keychain (generic passwords), or a JSON file for tests.

`JOB_AUTOFILL_KEYCHAIN=fake:<file>` swaps the Keychain for a 0600 JSON file. Keys are never
logged and never appear in error text.
"""
import json
import os
import subprocess
import tempfile

SERVICES = {
    'anthropic': 'job-autofill-anthropic',
    'openai': 'job-autofill-openai',
}
ACCOUNT = 'job-autofill'
_NOT_FOUND = 44  # `security` exit status for "item not found"


class KeychainError(Exception):
    pass


def service_for(provider):
    try:
        return SERVICES[provider]
    except KeyError:
        raise ValueError('unknown provider %r; use one of: %s' % (provider, ', '.join(SERVICES)))


def _fake_path(env):
    spec = (env if env is not None else os.environ).get('JOB_AUTOFILL_KEYCHAIN', '')
    return spec[len('fake:'):] if spec.startswith('fake:') else None


def _read_fake(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get(provider, env=None):
    """The stored key, or None when no key is set."""
    service = service_for(provider)
    fake = _fake_path(env)
    if fake:
        value = _read_fake(fake).get(service)
        return value if isinstance(value, str) and value else None
    try:
        r = subprocess.run(
            ['security', 'find-generic-password', '-s', service, '-a', ACCOUNT, '-w'],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        raise KeychainError('could not run the security tool: %s' % type(e).__name__)
    if r.returncode == _NOT_FOUND:
        return None
    if r.returncode != 0:
        raise KeychainError('Keychain read failed (security exit %d)' % r.returncode)
    return r.stdout.rstrip('\n') or None


def set(provider, key, env=None):  # noqa: A001 - public API name from the plan
    service = service_for(provider)
    if not key or any(ord(c) < 32 for c in key):
        raise ValueError('key is empty or contains control characters')
    fake = _fake_path(env)
    if fake:
        data = _read_fake(fake)
        data[service] = key
        directory = os.path.dirname(os.path.abspath(fake))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix='.keychain.')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            os.replace(tmp, fake)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return
    try:
        r = subprocess.run(
            ['security', 'add-generic-password', '-U', '-s', service, '-a', ACCOUNT, '-w', key],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        raise KeychainError('could not run the security tool: %s' % type(e).__name__)
    if r.returncode != 0:
        detail = (r.stderr or '').replace(key, '***').strip()
        raise KeychainError('Keychain write failed (security exit %d) %s' % (r.returncode, detail))
