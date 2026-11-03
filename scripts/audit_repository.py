"""Offline, redacted Git audit. Never prints matched values or file contents."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    configured = []
    env = ROOT / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            key, sep, value = line.partition('=')
            value = value.strip().strip('\"\'')
            if sep and re.search(r'KEY|TOKEN|SECRET|PASSWORD', key, re.I) and len(value) >= 12:
                configured.append(value)
    patterns = {
        'credential_pattern': re.compile(r'(?<![\w-])(?:sk-[A-Za-z0-9_-]{16,}|tvly-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})(?![\w-])'),
        'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        'credential_url': re.compile(r'https?://[^\s/:]+:[^\s/@]+@'),
        'assigned_credential': re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|secret|password)\s*[=:]\s*["']([A-Za-z0-9_./+\-=]{16,})["']'''),
        'private_address': re.compile(r'\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b'),
        'local_absolute_path': re.compile(r'(?i)\b[A-Z]:[\\/](?:Users|Myfolders)[\\/][^\s"<>]+'),
    }
    findings = []

    def scan(data, path, scope, oid=None):
        content = data.decode('utf-8', errors='replace')
        for kind, pattern in patterns.items():
            lines = sorted({content.count('\n', 0, m.start()) + 1 for m in pattern.finditer(content)})
            if lines:
                findings.append(dict(scope=scope, path=path, kind=kind, lines=lines, **({'blob': oid} if oid else {})))
        if any(secret in content for secret in configured):
            findings.append(dict(scope=scope, path=path, kind='configured_secret_exact_match', **({'blob': oid} if oid else {})))

    paths = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')
    for path in filter(None, paths):
        file = ROOT / path
        if file.is_file():
            scan(file.read_bytes(), path, 'working_tree')
    reachable = {line.split(' ', 1)[0] for line in git('rev-list', '--objects', '--all').decode().splitlines()}
    objects = git('rev-list', '--objects', '--all', '--reflog').decode().splitlines()
    blobs = 0
    historical_data = []
    for row in objects:
        oid, _, path = row.partition(' ')
        if git('cat-file', '-t', oid).strip() != b'blob':
            continue
        blobs += 1
        scan(git('cat-file', 'blob', oid), path, 'branch_history' if oid in reachable else 'reflog_only', oid)
        if re.search(r'(?:\.db(?:-wal|-shm)?|\.sqlite3?|\.log)$|(?:acceptance|backlog-processing)\.json$|(?:^|/)\.env$', path):
            historical_data.append(dict(path=path, blob=oid, reachable_from_branch=oid in reachable))
    result = dict(commits=int(git('rev-list', '--all', '--count')), historical_blobs_scanned=blobs,
                  configured_secret_values_checked=len(configured), findings=findings,
                  historical_data_artifacts=historical_data,
                  limitations='Pattern and locally configured credential scan; cannot prove absence of all secrets. Ignored local runtime files are intentionally not upload candidates. Historical public-data artifacts need human scope review.')
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
