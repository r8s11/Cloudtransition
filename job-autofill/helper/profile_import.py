"""Import the profile and the AI grounding text from a resume markdown file.

`parse(md_text) -> (fields, grounding, missing)` never raises. Missing fields are empty
strings; nothing is inferred.
"""
import re

FIELD_KEYS = (
    'fullName', 'firstName', 'lastName', 'city', 'state',
    'phone', 'email', 'website', 'github', 'linkedin',
)

_COMMENT = re.compile(r'<!--.*?-->', re.S)
_H1 = re.compile(r'^#\s+(\S.*?)\s*#*\s*$')
_HEADING = re.compile(r'^(#{1,6})\s+(.*\S)\s*$')
_MASTER_ONLY = re.compile(r'master[\s\-_\u2010-\u2015]*only', re.I)
_LINK = re.compile(r'\[([^\]]*)\]\(\s*<?([^)>\s]*)>?[^)]*\)')
_BARE_BRACKET = re.compile(r'^\[[^\]]*\]$')
_EMAIL = re.compile(r'[^\s@<>()\[\]|]+@[^\s@<>()\[\]|]+\.[^\s@<>()\[\]|]+')
_PHONE = re.compile(r'^\+?[\d\s().\-]{7,}(?:\s*(?:x|ext\.?)\s*\d{1,6})?$', re.I)
_BARE_URL = re.compile(r'^(?:https?://)?[A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,}(?:/\S*)?$')
_PLACE = re.compile(r"^([A-Za-z][A-Za-z .'\-]*?),\s*([A-Za-z]{2}|[A-Za-z][A-Za-z .]{2,24})$")
_SEPARATORS = re.compile(r'\s*[|\u2022\u00b7]\s*')


def _assign_link(fields, label, url):
    url = url.strip()
    low = url.lower()
    if not url:
        return
    if low.startswith('mailto:'):
        fields['email'] = fields['email'] or url[7:]
        return
    if low.startswith('tel:'):
        fields['phone'] = fields['phone'] or url[4:]
        return
    if ' ' in url or '.' not in url:
        return
    if 'linkedin.com' in low:
        slot = 'linkedin'
    elif 'github.com' in low:
        slot = 'github'
    elif label.strip().lower() in ('linkedin', 'github'):
        slot = label.strip().lower()
    else:
        slot = 'website'
    if not fields[slot]:
        fields[slot] = url


def _parse_contact(line, fields):
    for seg in _SEPARATORS.split(line):
        seg = seg.strip()
        if not seg:
            continue
        link = _LINK.search(seg)
        if link:
            _assign_link(fields, link.group(1), link.group(2))
        elif _BARE_BRACKET.match(seg):
            continue  # a link label without a URL
        elif '@' in seg:
            m = _EMAIL.search(seg)
            if m and not fields['email']:
                fields['email'] = m.group(0)
        elif _PHONE.match(seg) and 7 <= sum(c.isdigit() for c in seg) <= 20:
            if not fields['phone']:
                fields['phone'] = seg
        elif _BARE_URL.match(seg):
            _assign_link(fields, '', seg)
        else:
            m = _PLACE.match(seg)
            if m and not fields['city']:
                fields['city'] = m.group(1).strip()
                fields['state'] = m.group(2).strip()


def _find_name(lines):
    for i, line in enumerate(lines):
        m = _H1.match(line)
        if m:
            return i, re.sub(r'[*`]', '', m.group(1)).strip()
    return None, ''


def _find_contact(lines, name_idx):
    """The contact line is the first content line under the name heading."""
    if name_idx is None:
        return None
    for i in range(name_idx + 1, min(len(lines), name_idx + 8)):
        line = lines[i].strip()
        if not line or line == '---':
            continue
        if line.startswith('#'):
            return None
        if '|' in line or _EMAIL.search(line):
            return i
        return None
    return None


def _is_master_only(lines, idx, heading_text):
    if _MASTER_ONLY.search(heading_text):
        return True
    for line in lines[idx + 1:]:
        s = line.strip()
        if not s:
            continue
        return (not s.startswith('#') and len(s) <= 200 and s[0] in '_*(>'
                and bool(_MASTER_ONLY.search(s)))
    return False


def _build_grounding(lines, contact_idx):
    out = []
    skip_level = None
    for i, line in enumerate(lines):
        if i == contact_idx:
            continue  # phone/email never belong in AI grounding
        m = _HEADING.match(line)
        if m:
            level = len(m.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and _is_master_only(lines, i, m.group(2)):
                skip_level = level
        if skip_level is not None:
            continue
        out.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()


def parse(md_text):
    text = _COMMENT.sub('', md_text or '')
    lines = text.splitlines()
    fields = {k: '' for k in FIELD_KEYS}

    name_idx, name = _find_name(lines)
    if name:
        parts = name.split()
        fields['fullName'] = name
        fields['firstName'] = parts[0]
        fields['lastName'] = parts[-1] if len(parts) > 1 else ''

    contact_idx = _find_contact(lines, name_idx)
    if contact_idx is not None:
        _parse_contact(lines[contact_idx], fields)

    grounding = _build_grounding(lines, contact_idx)
    missing = [k for k in FIELD_KEYS if not fields[k]]
    return fields, grounding, missing
