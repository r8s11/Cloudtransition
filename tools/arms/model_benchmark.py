#!/usr/bin/env python3
"""Compare fresh Claude retrieval with supplied deterministic evidence on technical-only sources.

Each invocation uses the user's existing Claude authentication and consumes plan/API usage.
No account settings change. Results are actual CLI usage, not interactive /context output.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    {
        'question': 'After an abrupt supervisor exit, what status do unfinished agent runtime runs become, and are surviving processes signalled using old PIDs?',
        'expected': ['lost', 'not'],
    },
    {
        'question': 'What address does the Agentic OS local control plane bind to, and does its policy sandbox agent tool execution?',
        'expected': ['127.0.0.1', 'not'],
    },
]


def claude_routing() -> dict:
    """Where the CLI will send requests, from the environment or the user's Claude settings.

    Reports only hosts and which aliases are remapped; never tokens or model names' secrets.
    """
    env = {}
    settings = Path.home() / '.claude' / 'settings.json'
    try:
        env = json.loads(settings.read_text(encoding='utf-8')).get('env', {}) or {}
    except (OSError, ValueError, AttributeError):
        env = {}
    base = os.environ.get('ANTHROPIC_BASE_URL') or env.get('ANTHROPIC_BASE_URL')
    remapped = sorted(k for k in ('ANTHROPIC_DEFAULT_HAIKU_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL',
                                  'ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_MODEL')
                      if os.environ.get(k) or env.get(k))
    info = {'base_url_host': None, 'reachable': None, 'aliases_remapped_by': remapped}
    if base:
        parts = urlsplit(base)
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        info['base_url_host'] = f'{parts.scheme}://{parts.hostname}:{port}'
        try:
            with socket.create_connection((parts.hostname, port), timeout=2):
                info['reachable'] = True
        except OSError:
            info['reachable'] = False
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Explicitly permit four bounded fresh model calls')
    parser.add_argument('--model', default='haiku')
    parser.add_argument('--budget-per-call', type=float, default=0.5)
    parser.add_argument('--output', type=Path, default=ROOT / 'tools/arms/data/model-benchmark.json')
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'status': 'not_run', 'cases': CASES, 'calls': 4,
                          'maximum_configured_budget_usd': 4 * args.budget_per_call}, indent=2))
        return 0
    if not 0 < args.budget_per_call <= 1:
        parser.error('--budget-per-call must be greater than zero and at most 1 USD')
    if not shutil.which('claude'):
        parser.error('claude is not installed')
    routing = claude_routing()
    if routing['reachable'] is False:
        # Fail fast instead of letting each call retry for minutes against a closed port.
        print(json.dumps({'status': 'blocked', 'routing': routing,
                          'message': 'Claude CLI is configured to use an API endpoint that is not '
                                     'accepting connections. Start that endpoint, or change the '
                                     'CLI configuration yourself, then rerun with --run.'}, indent=2))
        return 2
    result = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'method': 'Fresh safe-mode Claude sessions; same model and technical corpus. Baseline uses read-only file tools; brain receives retrieved evidence and the same tools. Not interactive /context. API-equivalent CLI cost is not a subscription charge.',
        'model_requested': args.model,
        'budget_per_call_usd': args.budget_per_call,
        # If aliases are remapped, `model_requested` is not necessarily the model that answered;
        # each row's `model_usage` names the model actually billed.
        'routing': routing,
        'rows': [],
    }
    with tempfile.TemporaryDirectory(prefix='cloudtransition-model-benchmark-') as directory:
        corpus = Path(directory)
        target = corpus / 'agentic-os/README.md'
        target.parent.mkdir()
        shutil.copyfile(ROOT / 'agentic-os/README.md', target)
        for case in CASES:
            retrieval = subprocess.run(
                ['python3', str(ROOT / 'second-brain/brain.py'), 'query', case['question']],
                capture_output=True, text=True, timeout=30, check=True,
            )
            evidence = json.loads(retrieval.stdout)
            # Only the technical README may leave this fixture. Never forward personal memory.
            allowed = [entry for entry in evidence.get('evidence', [])
                       if entry.get('path') == 'agentic-os/README.md']
            if not allowed:
                result['rows'].append({'question': case['question'], 'status': 'retrieval_miss',
                                       'retrieval_status': evidence.get('status')})
                continue
            for mode in ('baseline', 'brain'):
                prompt = ('Answer the technical question below accurately in at most 100 words, with source path and line citations. '
                          'You may read only the agentic-os/README.md provided in this directory. '
                          'Do not write files or use network tools. If evidence is insufficient, say so.\nQuestion: ' + case['question'])
                if mode == 'brain':
                    prompt += '\nDeterministically retrieved source evidence:\n' + json.dumps(allowed)
                command = ['claude', '--safe-mode', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                           '--model', args.model, '--effort', 'low', '--tools', 'Read,Glob,Grep',
                           '--allowed-tools', 'Read,Glob,Grep', '--permission-mode', 'plan',
                           '--max-budget-usd', str(args.budget_per_call), '--no-session-persistence',
                           '--output-format', 'json', '--print', prompt]
                start = time.perf_counter()
                try:
                    process = subprocess.run(command, cwd=corpus, capture_output=True, text=True, timeout=180)
                    elapsed = round((time.perf_counter() - start) * 1000, 3)
                    try:
                        response = json.loads(process.stdout)
                    except json.JSONDecodeError:
                        response = {'error': process.stderr.strip()[:1500] or process.stdout[:1500]}
                    row = {'question': case['question'], 'mode': mode, 'wall_ms': elapsed,
                           'exit_code': process.returncode, 'status': 'ok' if process.returncode == 0 and not response.get('is_error') else 'error',
                           'usage': response.get('usage'), 'model_usage': response.get('modelUsage'),
                           'api_equivalent_cost_usd': response.get('total_cost_usd'),
                           'answer': response.get('result'), 'error': response.get('error'),
                           'subtype': response.get('subtype'),
                           'retrieval_ms': evidence.get('elapsed_ms') if mode == 'brain' else None}
                    if row['answer']:
                        row['keyword_sanity_only'] = all(word in row['answer'].lower() for word in case['expected'])
                    result['rows'].append(row)
                    print(json.dumps(row), flush=True)
                except subprocess.TimeoutExpired:
                    result['rows'].append({'question': case['question'], 'mode': mode, 'status': 'timeout', 'wall_ms': 180000})
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
                # Provider/auth failure is not a reason to repeat requests automatically.
                if result['rows'][-1]['status'] != 'ok':
                    return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0 if len(result['rows']) == 4 and all(row['status'] == 'ok' for row in result['rows']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
