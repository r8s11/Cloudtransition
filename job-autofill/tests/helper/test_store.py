import datetime
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'helper'))

import keychain  # noqa: E402
import store as store_mod  # noqa: E402

FIXTURE = os.path.join(HERE, '..', 'fixtures', 'master.fixture.md')


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class StoreCase(unittest.TestCase):
    def setUp(self):
        base = os.environ.get('TMPDIR') or None
        self.tmp = tempfile.mkdtemp(prefix='jaf-store-', dir=base)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, 'workspace')
        os.makedirs(os.path.join(self.root, 'resume'))
        self.md = os.path.join(self.root, 'resume', 'master.md')
        shutil.copy(FIXTURE, self.md)
        self.home = os.path.join(self.tmp, 'home')
        self.store = store_mod.Store(self.home, root=self.root, env={})


class ProfileStoreTest(StoreCase):
    def test_U2_profile_reports_imported_manual_and_no_inferred_fields(self):
        p = self.store.profile()
        self.assertEqual(p['imported']['fullName'], 'Jordan Avery')
        self.assertEqual(p['imported']['linkedin'], 'https://www.linkedin.com/in/jordan-avery-fixture')
        self.assertEqual(p['missing'], [])
        self.assertTrue(p['synced_at'])
        self.assertEqual(len(p['grounding_hash']), 64)
        self.assertEqual(set(p['manual']), set(store_mod.MANUAL_KEYS))
        self.assertTrue(all(v == '' for v in p['manual'].values()))
        self.assertNotIn('grounding', p)
        self.assertIsNone(p['error'])

    def test_U2_resync_keeps_manual(self):
        self.store.save_manual({'country': 'United States', 'workAuthorization': 'Yes',
                                'needsSponsorship': 'No', 'veteran': 'Leave blank'})
        with open(self.md, encoding='utf-8') as f:
            text = f.read()
        old_hash = self.store.profile()['grounding_hash']
        with open(self.md, 'w', encoding='utf-8') as f:
            f.write(text.replace('Springfield, IL', 'Shelbyville, KY').replace('Fabrikam', 'Acme'))
        p = self.store.profile()
        self.assertEqual((p['imported']['city'], p['imported']['state']), ('Shelbyville', 'KY'))
        self.assertEqual(p['manual']['country'], 'United States')
        self.assertEqual(p['manual']['workAuthorization'], 'Yes')
        self.assertEqual(p['manual']['needsSponsorship'], 'No')
        self.assertEqual(p['manual']['veteran'], '')
        self.assertNotEqual(p['grounding_hash'], old_hash)

    def test_U3_manual_profile_json_holds_exactly_the_saved_values(self):
        self.store.save_manual({'country': 'United States', 'workAuthorization': 'Yes',
                                'needsSponsorship': 'No', 'veteran': 'Leave blank'})
        with open(os.path.join(self.home, 'profile.json'), encoding='utf-8') as f:
            saved = json.load(f)
        expected = {k: '' for k in store_mod.MANUAL_KEYS}
        expected.update(country='United States', workAuthorization='Yes', needsSponsorship='No')
        self.assertEqual(saved, expected)
        self.assertEqual(mode(os.path.join(self.home, 'profile.json')), 0o600)

    def test_U3_manual_rejects_unknown_keys_and_non_strings(self):
        with self.assertRaises(ValueError):
            self.store.save_manual({'fullName': 'Someone Else'})
        with self.assertRaises(ValueError):
            self.store.save_manual({'country': 5})
        with self.assertRaises(ValueError):
            self.store.save_manual(['country'])

    def test_F18_missing_resume_reports_not_found_and_keeps_last_good_import(self):
        good = self.store.profile()
        os.unlink(self.md)
        p = self.store.profile()
        self.assertEqual(p['error'], 'resume/master.md not found')
        self.assertEqual(p['imported'], good['imported'])
        self.assertEqual(p['grounding_hash'], good['grounding_hash'])
        self.assertEqual(p['synced_at'], good['synced_at'])
        self.assertIsNone(self.store.grounding())

    def test_F18_missing_resume_without_any_prior_import(self):
        os.unlink(self.md)
        p = self.store.profile()
        self.assertEqual(p['error'], 'resume/master.md not found')
        self.assertTrue(all(v == '' for v in p['imported'].values()))
        self.assertIsNone(p['synced_at'])

    def test_F18_missing_field_is_listed_for_the_popup(self):
        with open(self.md, 'w', encoding='utf-8') as f:
            f.write('# Jordan Avery\n\nSpringfield, IL | jordan.avery@example.test\n')
        self.assertEqual(self.store.profile()['missing'],
                         ['phone', 'website', 'github', 'linkedin'])

    def test_resume_markdown_env_and_config_override_default_path(self):
        other = os.path.join(self.tmp, 'other.md')
        with open(other, 'w', encoding='utf-8') as f:
            f.write('# Pat Quinn\n')
        s = store_mod.Store(self.home, root=self.root, env={'JOB_AUTOFILL_RESUME_MD': other})
        self.assertEqual(s.profile()['imported']['fullName'], 'Pat Quinn')
        s2 = store_mod.Store(self.home, root=self.root, env={})
        s2.save_config({'resume_markdown': other})
        self.assertEqual(s2.profile()['imported']['fullName'], 'Pat Quinn')
        self.assertIsNone(s2.profile()['error'])

    def test_grounding_hash_matches_grounding_text(self):
        text, digest = self.store.grounding()
        self.assertNotIn('Northwind', text)
        self.assertEqual(digest, self.store.profile()['grounding_hash'])


class FilesAndPermissionsTest(StoreCase):
    def test_home_is_0700_and_files_are_0600(self):
        token, created = self.store.ensure()
        self.assertTrue(created)
        self.store.save_manual({'country': 'United States'})
        self.store.save_config({'daily_cap': 5})
        self.store.profile()
        self.store.append_run({'host': 'h', 'outcome': 'filled'})
        self.store.answers_put('k', {'text': 'v'})
        self.store.count_ai_call()
        self.assertEqual(mode(self.home), 0o700)
        names = sorted(os.listdir(self.home))
        self.assertEqual(names, ['answers.json', 'config.json', 'imported.json', 'profile.json',
                                 'runs.jsonl', 'token', 'usage.json'])
        for n in names:
            self.assertEqual(mode(os.path.join(self.home, n)), 0o600, n)

    def test_existing_loose_modes_are_tightened_on_ensure(self):
        os.makedirs(self.home, exist_ok=True)
        path = os.path.join(self.home, 'config.json')
        with open(path, 'w') as f:
            f.write('{}')
        os.chmod(path, 0o644)
        os.chmod(self.home, 0o755)
        store_mod.Store(self.home, root=self.root, env={}).ensure()
        self.assertEqual(mode(self.home), 0o700)
        self.assertEqual(mode(path), 0o600)

    def test_token_is_created_once(self):
        t1, c1 = self.store.ensure_token()
        t2, c2 = self.store.ensure_token()
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(t1, t2)
        self.assertEqual(self.store.token(), t1)
        self.assertGreaterEqual(len(t1), 32)
        self.assertEqual(store_mod.Store(self.home, root=self.root, env={}).token(), t1)

    def test_config_defaults_merge_and_validation(self):
        cfg = self.store.config()
        self.assertEqual(cfg, {'port': 8766, 'provider': 'anthropic', 'models': {}, 'daily_cap': 30,
                               'resume_pdf': '', 'resume_markdown': 'resume/master.md'})
        self.store.save_config({'models': {'anthropic': 'pick-a'}})
        self.store.save_config({'provider': 'openai', 'models': {'openai': 'pick-b'}})
        cfg = self.store.config()
        self.assertEqual(cfg['models'], {'anthropic': 'pick-a', 'openai': 'pick-b'})
        self.assertEqual(cfg['provider'], 'openai')
        for bad in ({'host': '0.0.0.0'}, {'provider': 'other-vendor'}, {'daily_cap': -1},
                    {'daily_cap': True}, {'port': 0}, {'resume_markdown': ' '},
                    {'models': {'other': 'x'}}, {'resume_pdf': 7}):
            with self.assertRaises(ValueError, msg=str(bad)):
                self.store.save_config(bad)
        self.assertEqual(self.store.config(), cfg)

    def test_corrupt_json_falls_back_to_defaults(self):
        with open(os.path.join(self.home, 'config.json'), 'w') as f:
            f.write('{not json')
        with open(os.path.join(self.home, 'profile.json'), 'w') as f:
            f.write('[1]')
        self.assertEqual(self.store.config()['port'], 8766)
        self.assertEqual(set(self.store.profile()['manual']), set(store_mod.MANUAL_KEYS))


class RunLogAndCountersTest(StoreCase):
    def test_run_record_keeps_exactly_the_documented_keys(self):
        out = self.store.append_run({
            'time': '2026-01-01T00:00:00+00:00', 'host': 'boards.example.test', 'path': '/jobs/1',
            'ats': 'greenhouse', 'green': 9, 'yellow': 1, 'ai_drafts': 1, 'ai_calls': 1, 'steps': 1,
            'outcome': 'filled', 'fullName': 'Jordan Avery', 'draft': 'secret text'})
        with open(os.path.join(self.home, 'runs.jsonl'), encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1)
        rec = json.loads(lines[0])
        self.assertEqual(list(rec), list(store_mod.RUN_KEYS))
        self.assertEqual(rec, out)
        self.assertNotIn('Jordan', lines[0])
        self.assertNotIn('secret', lines[0])

    def test_run_record_defaults_and_validation(self):
        out = self.store.append_run({'host': 'h', 'outcome': 'filled'})
        self.assertEqual(sorted(out), sorted(store_mod.RUN_KEYS))
        self.assertTrue(out['time'])
        self.assertEqual((out['green'], out['steps']), (0, 0))
        for bad in ('x', {'green': '3'}, {'green': -1}, {'green': True}, {'host': 5},
                    {'outcome': None}):
            with self.assertRaises(ValueError, msg=str(bad)):
                self.store.append_run(bad)
        self.store.append_run({'host': 'h2', 'outcome': 'stopped:captcha'})
        with open(os.path.join(self.home, 'runs.jsonl'), encoding='utf-8') as f:
            self.assertEqual(len(f.read().splitlines()), 2)

    def test_answers_get_put(self):
        self.assertIsNone(self.store.answers_get('k'))
        self.store.answers_put('k', {'text': 'draft'})
        self.assertEqual(self.store.answers_get('k'), {'text': 'draft'})
        self.assertEqual(store_mod.Store(self.home, root=self.root, env={}).answers_get('k'),
                         {'text': 'draft'})

    def test_ai_calls_count_per_day_with_injected_clock(self):
        d1 = datetime.datetime(2026, 3, 1, 23, 59)
        d2 = datetime.datetime(2026, 3, 2, 0, 1)
        self.assertEqual(self.store.ai_calls_today(d1), 0)
        self.assertEqual(self.store.count_ai_call(d1), 1)
        self.assertEqual(self.store.count_ai_call(d1), 2)
        self.assertEqual(self.store.ai_calls_today(d1), 2)
        self.assertEqual(self.store.ai_calls_today(d2), 0)
        self.assertEqual(self.store.count_ai_call(d2), 1)
        self.assertEqual(self.store.ai_calls_today(d1), 0)


class FakeKeychainTest(StoreCase):
    def test_fake_keychain_round_trip_and_unknown_provider(self):
        env = {'JOB_AUTOFILL_KEYCHAIN': 'fake:' + os.path.join(self.tmp, 'kc.json')}
        self.assertIsNone(keychain.get('anthropic', env=env))
        keychain.set('anthropic', 'fixture-key-123', env=env)
        keychain.set('openai', 'fixture-key-456', env=env)
        self.assertEqual(keychain.get('anthropic', env=env), 'fixture-key-123')
        self.assertEqual(keychain.get('openai', env=env), 'fixture-key-456')
        self.assertEqual(mode(os.path.join(self.tmp, 'kc.json')), 0o600)
        with self.assertRaises(ValueError):
            keychain.get('other-vendor', env=env)
        with self.assertRaises(ValueError):
            keychain.set('anthropic', '', env=env)
        with self.assertRaises(ValueError):
            keychain.set('anthropic', 'a\nb', env=env)


if __name__ == '__main__':
    unittest.main()
