import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'helper'))

import profile_import  # noqa: E402

FIXTURE = os.path.join(HERE, '..', 'fixtures', 'master.fixture.md')

EXPECTED = {
    'fullName': 'Jordan Avery',
    'firstName': 'Jordan',
    'lastName': 'Avery',
    'city': 'Springfield',
    'state': 'IL',
    'phone': '555-010-0199',
    'email': 'jordan.avery@example.test',
    'website': 'https://javery.example.test',
    'github': 'https://github.com/javery-fixture',
    'linkedin': 'https://www.linkedin.com/in/jordan-avery-fixture',
}


def fixture_text():
    with open(FIXTURE, encoding='utf-8') as f:
        return f.read()


class ProfileImportTest(unittest.TestCase):
    def test_U2_fields_equal_fixture_values_exactly(self):
        fields, _, missing = profile_import.parse(fixture_text())
        self.assertEqual(fields, EXPECTED)
        self.assertEqual(missing, [])

    def test_U2_grounding_keeps_normal_sections_and_drops_master_only(self):
        _, grounding, _ = profile_import.parse(fixture_text())
        for kept in ('Fabrikam Industries', 'Adventure Works', 'Lakeside University',
                     'Active Directory', 'Systems analyst'):
            self.assertIn(kept, grounding)
        for dropped in ('Northwind', 'Contoso', 'deployment tooling', 'data pipeline audits',
                        'master only'):
            self.assertNotIn(dropped, grounding)

    def test_U2_grounding_never_carries_contact_details(self):
        _, grounding, _ = profile_import.parse(fixture_text())
        for value in ('555-010-0199', 'jordan.avery@example.test', 'javery.example.test'):
            self.assertNotIn(value, grounding)

    def test_U2_master_only_marker_on_first_body_line(self):
        md = ('# Jordan Avery\n\nSpringfield, IL | 555-010-0199\n\n## Public\n\nkeep me\n\n'
              '## Private\n_(master only)_\n\nhide me\n\n### Nested\n\nhide nested\n\n'
              '## After\n\nkeep after\n')
        _, grounding, _ = profile_import.parse(md)
        self.assertIn('keep me', grounding)
        self.assertIn('keep after', grounding)
        self.assertNotIn('hide me', grounding)
        self.assertNotIn('hide nested', grounding)

    def test_U2_every_other_field_is_empty(self):
        fields, _, _ = profile_import.parse(fixture_text())
        self.assertEqual(sorted(fields), sorted(profile_import.FIELD_KEYS))
        # Street, ZIP, EEO and authorization fields are manual and never inferred here.
        for manual in ('street', 'zip', 'country', 'veteran', 'workAuthorization'):
            self.assertNotIn(manual, fields)


class MalformedImportTest(unittest.TestCase):
    def assertEmptyExcept(self, fields, *keep):
        for k in profile_import.FIELD_KEYS:
            if k not in keep:
                self.assertEqual(fields[k], '', k)

    def test_F18_no_contact_line(self):
        md = '# Jordan Avery\n\nSystems analyst with a decade of experience, in IT.\n\n## Experience\n'
        fields, grounding, missing = profile_import.parse(md)
        self.assertEqual(fields['fullName'], 'Jordan Avery')
        self.assertEmptyExcept(fields, 'fullName', 'firstName', 'lastName')
        self.assertEqual(missing, ['city', 'state', 'phone', 'email', 'website', 'github', 'linkedin'])
        self.assertIn('Systems analyst', grounding)

    def test_F18_contact_line_missing_phone(self):
        md = ('# Jordan Avery\n\nSpringfield, IL | jordan.avery@example.test | '
              '[site](https://javery.example.test) | [GitHub](https://github.com/javery-fixture) | '
              '[LinkedIn](https://www.linkedin.com/in/jordan-avery-fixture)\n')
        fields, _, missing = profile_import.parse(md)
        self.assertEqual(missing, ['phone'])
        self.assertEqual(fields['phone'], '')
        self.assertEqual(fields['email'], 'jordan.avery@example.test')

    def test_F18_linkedin_link_without_url(self):
        for link in ('[LinkedIn]()', '[LinkedIn]', '[LinkedIn](  )'):
            md = ('# Jordan Avery\n\nSpringfield, IL | 555-010-0199 | jordan.avery@example.test | '
                  '[GitHub](https://github.com/javery-fixture) | %s\n' % link)
            fields, _, missing = profile_import.parse(md)
            self.assertEqual(fields['linkedin'], '', link)
            self.assertEqual(missing, ['website', 'linkedin'], link)

    def test_F18_empty_file(self):
        for text in ('', '   \n\n', None):
            fields, grounding, missing = profile_import.parse(text)
            self.assertEmptyExcept(fields)
            self.assertEqual(grounding, '')
            self.assertEqual(missing, list(profile_import.FIELD_KEYS))

    def test_F18_garbage_never_raises(self):
        for text in ('|||', '# \n|', '[[[](', '<!-- unterminated', '# A\n| | |\n\x00\x01'):
            profile_import.parse(text)


if __name__ == '__main__':
    unittest.main()
