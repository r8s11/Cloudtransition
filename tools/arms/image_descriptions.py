#!/usr/bin/env python3
"""Inventory, caption and register workspace-owned images with Markdown sidecars.

Commands (all stdlib; no service, no index, nothing moves):
  inventory  metadata-only scan; rewrites resources/image-coverage.md (the one generated file).
  describe   caption in-scope images that have no sidecar, using the Claude CLI. Needs --run.
  register   save an image's exact generation prompt + generator model in a new sidecar.

A sidecar is `<image-filename>.md` beside the image (e.g. `cover.png.md`). A pre-existing
`<stem>.md` that links to the image is honoured. Existing sidecars are never overwritten.
Image contents leave the machine only in `describe`/`register`, only for in-scope files, and
only to the model named in the sidecar. Excluded media are counted, never decoded or uploaded.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_benchmark import claude_routing  # noqa: E402  (reports host only; never tokens)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'resources/image-coverage.md'
IMAGE_EXT = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
             '.webp': 'image/webp', '.avif': 'image/avif', '.svg': 'image/svg+xml', '.heic': 'image/heic',
             '.bmp': 'image/bmp', '.tif': 'image/tiff', '.tiff': 'image/tiff', '.ico': 'image/x-icon'}
DIRECT_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}  # sent as-is; others converted
MAX_DIRECT_BYTES = 3_500_000
NOT_ENUMERATED = {'.git', 'node_modules'}
VENDOR_DIRS = {'node_modules', 'venv', 'env', '__pycache__', 'dist', 'build', 'site-packages', 'vendor',
               'coverage', 'target', 'out'}
PRIVATE_RE = re.compile(r'private|employer|secret|credential', re.I)
TEMPLATE_DIR = 'projects/reactnative/mytvapp/assets/images'
# SHA-256 of the 10 original assets in expo-template-default@54.0.63 (npm), compared 2026-11-02.
# Only files that still match are excluded; any new or edited asset in that folder stays in scope.
TEMPLATE_HASHES = {
    'android-icon-background.png': 'fb139c2dee362ebf2070e23b96da6fc0d43f8492de38b8af1fd7223e19b5861d',
    'android-icon-foreground.png': '9e3d0315a33c6799de601dd34cd8bf8cc3a8d16f3bf75592baec2ceb7240b391',
    'android-icon-monochrome.png': '6371fc2c12e33ad2215a86c281db3d682a81bebe7c957a842c13b8bf00cceb83',
    'favicon.png': 'a4e030697a7571b3e95d31860e4da55d2f98e5e861e2b55e414f45a8556828ba',
    'icon.png': '119462bb78eb240a65c869fc067ee599639b3cb5a41953f25c07b17d2a8c7e0f',
    'partial-react-logo.png': '015a72aeb24c1166243ebc185355c9488cc892fbf3aa82f9ae66819a10f3451c',
    'react-logo.png': '224b7636b15e672801579b5b418077cbc2ca42f0146389062364356b0ecb5c5c',
    'react-logo@2x.png': 'fa600be9ad2f869c7a8dbaffc78bb15af741123e1319c948f0be51753a153cde',
    'react-logo@3x.png': 'cd84e02a5d542a3e71b7fa10a685c1b9fb51db4aff92aca6c0da6461ce17be16',
    'splash-icon.png': '5f4c0a732b6325bf4071d9124d2ae67e037cb24fcc9c482ef82bea742109a3b8',
}
TEMPLATE_REASON = ('unmodified Expo create-app template asset: SHA-256 equals the original in '
                   'expo-template-default@54.0.63 (third-party/generated; local hash comparison only)')
PRIVATE_REASON = 'name matches private/employer policy; contents are never decoded or uploaded'
EXPLICIT = {
    'projects/rendercv': 'third-party project, not workspace-authored',
    'andrej-karpathy-skills': 'third-party project, not workspace-authored',
    'r8s11': 'standalone nested git repository (own .git); workspace ownership not established',
    'college planning': 'personal academic records; contents are never decoded or uploaded',
}
CAPTION_PROMPT = (
    'Describe this image for a plain-text search index. Return only JSON with keys: '
    '"title" (at most 10 words), "description" (2 to 5 factual sentences: subject, layout, colors, '
    'style, notable objects), "visible_text" (array of exact legible strings; empty array if none), '
    '"uncertainty" (what is unclear or unreadable; empty string if nothing). '
    'Do not guess the creator, the identity of any person, who owns a brand, or how the image was made.'
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def dir_exclusion(path: Path) -> str | None:
    name, relative = path.name, rel(path).lower()
    if relative in EXPLICIT:
        return EXPLICIT[relative]
    if name.startswith('.'):
        return 'hidden directory (tool-owned or generated)'
    if name.lower() in VENDOR_DIRS:
        return 'dependency, build or generated output'
    if name.lower().endswith('_files'):
        return 'saved web-page assets (third-party)'
    if PRIVATE_RE.search(name):
        return PRIVATE_REASON
    return None


def file_exclusion(path: Path) -> str | None:
    """Per-file policy: private-looking names, and unmodified Expo template originals (hash-verified)."""
    if PRIVATE_RE.search(path.name):
        return PRIVATE_REASON
    expected = TEMPLATE_HASHES.get(path.name)
    if expected and rel(path.parent).lower() == TEMPLATE_DIR and sha256(path) == expected:
        return TEMPLATE_REASON
    return None


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXT


def count_images(directory: Path) -> int:
    total = 0
    for current, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in NOT_ENUMERATED and not (Path(current) / d).is_symlink()]
        total += sum(1 for f in files if is_image(Path(f)) and not (Path(current) / f).is_symlink())
    return total


def scan() -> tuple[list[Path], list[tuple[str, str, int | None]], int]:
    """Return (in-scope images, [(reason, label, image count)], symlinked image count).

    Reads no image content except a local SHA-256 of the template-named files."""
    images: list[Path] = []
    excluded: list[tuple[str, str, int | None]] = []
    links = 0
    for current, dirs, files in os.walk(ROOT):
        here = Path(current)
        keep = []
        for d in sorted(dirs):
            child = here / d
            if child.is_symlink():
                continue
            reason = dir_exclusion(child)
            if reason:
                counted = None if d in NOT_ENUMERATED else count_images(child)
                excluded.append((reason, rel(child) + '/', counted))
            else:
                keep.append(d)
        dirs[:] = keep
        template = 0
        for f in sorted(files):
            path = here / f
            if not is_image(path):
                continue
            if path.is_symlink():
                links += 1
                continue
            reason = file_exclusion(path)
            if reason == TEMPLATE_REASON:
                template += 1
            elif reason:
                excluded.append((reason, rel(path), 1))
            else:
                images.append(path)
        if template:
            excluded.append((TEMPLATE_REASON, rel(here) + '/ (only the matching files)', template))
    images.sort(key=lambda p: rel(p).lower())
    excluded.sort(key=lambda row: (row[0], row[1].lower()))
    return images, excluded, links


def in_scope(path: Path) -> bool:
    """True only for a regular, non-symlinked image whose whole path stays inside the workspace policy."""
    path = Path(os.path.abspath(path))
    if ROOT not in path.parents or not is_image(path) or not path.is_file():
        return False
    probe = path
    while probe != ROOT:  # a symlink anywhere between the workspace root and the file is rejected
        if probe.is_symlink():
            return False
        probe = probe.parent
    if ROOT not in path.resolve().parents:
        return False
    return file_exclusion(path) is None and all(
        dir_exclusion(parent) is None for parent in path.parents if parent != ROOT and ROOT in parent.parents)


def sidecar_for(image: Path) -> Path:
    new = image.with_name(image.name + '.md')
    legacy = image.with_suffix('.md')
    if not new.exists() and legacy.exists():
        text = legacy.read_text(encoding='utf-8', errors='replace')
        if f']({image.name})' in text or f']({quote(image.name)})' in text:
            return legacy
    return new


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def field(text: str, label: str) -> str | None:
    match = re.search(rf'^- {re.escape(label)}: (.+)$', text, re.M)
    return match.group(1).strip() if match else None


def inventory() -> int:
    images, excluded, links = scan()
    rows, described = [], 0
    for image in images:
        sidecar = sidecar_for(image)
        if sidecar.exists():
            described += 1
            text = sidecar.read_text(encoding='utf-8', errors='replace')
            model = field(text, 'Caption model')
            recorded = field(text, 'Image SHA-256')
            if model is None:
                status = 'described (pre-existing sidecar, viewed by agent; see file)'
            elif recorded and recorded != sha256(image):
                status = f'STALE (image changed after caption by {model})'
            else:
                status = f'described by {model}'
            prompt = (field(text, 'Original prompt') or ('unknown' if re.search(r'prompt are unknown', text) else 'see sidecar')).split(' (')[0]
            note = f'{status}; prompt: {prompt}'
        else:
            note = 'MISSING sidecar'
        rows.append(f'- `{rel(image)}` ({image.stat().st_size} bytes, sha256 {sha256(image)[:12]})\n'
                    f'  - sidecar: `{rel(sidecar)}`{"" if sidecar.exists() else " (not yet created)"}\n'
                    f'  - {note}')
    lines = [
        '# Image description coverage', '',
        f'Generated {datetime.now().astimezone().date()} by `python3 tools/arms/image_descriptions.py inventory`. '
        'Built from file metadata and local SHA-256 only: no image was decoded or sent to a model. Regenerate after adding images or sidecars.', '',
        'Scope: workspace-owned images. Sidecar rule, schema and prompt capture: '
        '[tools/arms/image-descriptions-README.md](../tools/arms/image-descriptions-README.md). '
        'No image or folder is moved. Captions are searchable machine descriptions in the sidecars, not repeated here.', '',
        f'## In scope: {described} of {len(images)} images have a sidecar', '', *rows, '',
        '## Excluded (counted, never decoded, never uploaded, never captioned)', '',
        'Only the unmodified Expo template originals were byte-hashed, locally, to prove provenance.', '',
    ]
    empty: dict[str, list[str]] = {}
    for reason, label, counted in excluded:
        if counted == 0:
            empty.setdefault(reason, []).append(f'`{label}`')
            continue
        size = 'not enumerated' if counted is None else f'{counted} image file(s)'
        lines.append(f'- `{label}`: {size}. Reason: {reason}.')
    for reason, labels in empty.items():
        lines.append(f'- 0 image files in {len(labels)} director{"y" if len(labels) == 1 else "ies"} '
                     f'({", ".join(labels)}). Reason: {reason}.')
    lines += [f'- Symlinked image files: {links}. Reason: link targets may sit outside the workspace.',
              '- Any other directory not listed above containing no images has nothing to describe.', '']
    MANIFEST.write_text('\n'.join(lines), encoding='utf-8')
    print(f'{described}/{len(images)} in-scope images have sidecars; {len(excluded)} exclusion rows -> {rel(MANIFEST)}')
    return 0


def prepare(image: Path, temp: Path) -> tuple[bytes, str]:
    media = IMAGE_EXT[image.suffix.lower()]
    if media in DIRECT_TYPES and image.stat().st_size <= MAX_DIRECT_BYTES:
        return image.read_bytes(), media
    if not shutil.which('sips'):
        raise SystemExit(f'cannot convert {rel(image)} ({media}): sips (macOS) not available')
    out = temp / 'converted.png'
    subprocess.run(['sips', '-s', 'format', 'png', str(image), '--out', str(out)],
                   check=True, capture_output=True, timeout=60)
    return out.read_bytes(), 'image/png'


def ask_model(image: Path, model: str, budget: float) -> dict:
    """One bounded vision call. Fails unless the model that actually answered matches `model`."""
    if not shutil.which('claude'):
        raise SystemExit('claude CLI is not installed')
    with tempfile.TemporaryDirectory(prefix='image-caption-') as directory:
        data, media = prepare(image, Path(directory))
        message = {'type': 'user', 'message': {'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': media,
                                         'data': base64.b64encode(data).decode()}},
            {'type': 'text', 'text': CAPTION_PROMPT}]}}
        command = ['claude', '--safe-mode', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                   '--model', model, '--effort', 'low', '--tools', '', '--max-budget-usd', str(budget),
                   '--no-session-persistence', '--input-format', 'stream-json',
                   '--output-format', 'stream-json', '--verbose', '--print']
        process = subprocess.run(command, input=json.dumps(message) + '\n', capture_output=True,
                                 text=True, timeout=180, cwd=directory)
    result = None
    for line in process.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'result':
            result = event
    if process.returncode != 0 or not result or result.get('is_error'):
        raise SystemExit(f'caption call failed for {rel(image)} (exit {process.returncode}): '
                         f'{(result or {}).get("result") or process.stderr.strip()[:500]}')
    used = sorted(result.get('modelUsage') or {})
    if not used or not all(name == model or (model in name) for name in used):
        raise SystemExit(f'refusing to record: requested "{model}" but billed model(s) were {used or "unknown"}')
    body = re.sub(r'^```(?:json)?\s*|\s*```$', '', result['result'].strip())
    try:
        caption = json.loads(body)
        caption['description']
    except (ValueError, KeyError, TypeError):
        raise SystemExit(f'model reply for {rel(image)} was not the requested JSON; nothing written')
    return {'caption': caption, 'models': used, 'requested': model, 'cost': result.get('total_cost_usd')}


def fence(text: str) -> str:
    ticks = '`' * max(3, max((len(run) for run in re.findall(r'`+', text)), default=0) + 1)
    return f'{ticks}text\n{text}\n{ticks}'


def render(image: Path, result: dict, prompt: dict | None) -> str:
    today = datetime.now().astimezone().date()
    caption = result['caption']
    title = str(caption.get('title') or image.stem).strip()
    lines = [f'# {title}', '', f'Image: [{image.name}]({quote(image.name)})', '']
    if prompt:
        lines += ['- Original prompt: recorded verbatim below (saved at generation time)',
                  f'- Generator model: {prompt["model"]}']
        if prompt.get('tool'):
            lines.append(f'- Generator tool: {prompt["tool"]}')
        lines += [f'- Prompt recorded: {today}',
                  f'- Prompt SHA-256: {hashlib.sha256(prompt["text"].encode("utf-8")).hexdigest()}']
    else:
        lines.append('- Original prompt: unknown (not recorded; the caption below is a description, not a prompt)')
    lines += [f'- Caption model: {", ".join(result["models"])} (requested alias: {result["requested"]}; '
              'actual model read from Claude CLI modelUsage)',
              f'- Caption date: {today}',
              f'- Caption route: Claude CLI via {claude_routing().get("base_url_host") or "default Anthropic endpoint"}',
              '- Caption status: machine description, not manually verified; no creator, ownership or identity inferred',
              f'- Image SHA-256: {sha256(image)}', '',
              str(caption['description']).strip(), '']
    texts = [str(t) for t in caption.get('visible_text') or []]
    lines += ['Visible text: ' + ('; '.join(f'"{t}"' for t in texts) if texts else 'none legible'), '']
    if str(caption.get('uncertainty') or '').strip():
        lines += [f'Uncertainty: {str(caption["uncertainty"]).strip()}', '']
    if prompt:
        lines += ['## Original prompt', '', fence(prompt['text']), '']
    return '\n'.join(lines)


def write_new(sidecar: Path, content: str) -> None:
    # 'x': fail rather than overwrite; newline='' keeps recorded prompt bytes (CR/LF) untranslated.
    with sidecar.open('x', encoding='utf-8', newline='') as handle:
        handle.write(content)


def describe(args: argparse.Namespace) -> int:
    chosen = [Path(os.path.abspath(p)) for p in args.paths] if args.paths else scan()[0]
    todo = []
    for image in chosen:
        if not in_scope(image):
            raise SystemExit(f'not an in-scope workspace image: {image}')
        if not sidecar_for(image).exists():
            todo.append(image)
    print(f'{len(todo)} image(s) without sidecar; budget cap {args.budget_per_call} USD each, model "{args.model}"')
    for image in todo:
        print(f'  {rel(image)} -> {rel(sidecar_for(image))}')
    if not args.run:
        print('dry run; add --run to call the model')
        return 0
    routing = claude_routing()
    if routing['reachable'] is False:
        raise SystemExit(f'Claude CLI endpoint {routing["base_url_host"]} is not accepting connections')
    for image in todo:
        result = ask_model(image, args.model, args.budget_per_call)
        write_new(sidecar_for(image), render(image, result, None))
        print(f'wrote {rel(sidecar_for(image))} (model {", ".join(result["models"])}, cost {result["cost"]} USD)')
    return inventory()


def register(args: argparse.Namespace) -> int:
    image = Path(os.path.abspath(args.image))
    if not in_scope(image):
        raise SystemExit(f'not an in-scope workspace image: {image}')
    sidecar = sidecar_for(image)
    if sidecar.exists():
        raise SystemExit(f'{rel(sidecar)} already exists; it is never overwritten')
    raw = sys.stdin.buffer.read() if args.prompt_file == '-' else Path(args.prompt_file).read_bytes()
    text = raw.decode('utf-8')  # exact text: no newline translation, no stripping
    if not text.strip():
        raise SystemExit('prompt is empty')
    result = ask_model(image, args.caption_model, args.budget_per_call)
    write_new(sidecar, render(image, result, {'text': text, 'model': args.model, 'tool': args.tool}))
    print(f'wrote {rel(sidecar)}')
    return inventory()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('inventory', help='rewrite resources/image-coverage.md from file metadata')
    d = sub.add_parser('describe', help='caption in-scope images with no sidecar')
    d.add_argument('paths', nargs='*')
    d.add_argument('--run', action='store_true', help='actually call the model')
    d.add_argument('--model', default='haiku')
    d.add_argument('--budget-per-call', type=float, default=0.1)
    r = sub.add_parser('register', help='new sidecar with exact prompt and generator model')
    r.add_argument('image')
    r.add_argument('--prompt-file', required=True, help='file holding the exact prompt, or - for stdin')
    r.add_argument('--model', required=True, help='generator model that produced the image')
    r.add_argument('--tool', help='generator tool or provider, if known')
    r.add_argument('--caption-model', default='haiku')
    r.add_argument('--budget-per-call', type=float, default=0.1)
    args = parser.parse_args()
    if getattr(args, 'budget_per_call', 0.1) <= 0 or getattr(args, 'budget_per_call', 0.1) > 1:
        parser.error('--budget-per-call must be greater than 0 and at most 1 USD')
    return {'inventory': lambda a: inventory(), 'describe': describe, 'register': register}[args.command](args)


if __name__ == '__main__':
    raise SystemExit(main())
