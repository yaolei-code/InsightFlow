"""Bounded public HTTP collector. DNS is pinned per hop to prevent rebinding."""
import asyncio
import hashlib
import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.robotparser import RobotFileParser
import httpx
from bs4 import BeautifulSoup
from .config import settings

MAX_BYTES = 2_000_000
gate = asyncio.Semaphore(2)

def normalize_url(url):
    p = urlsplit(url.strip())
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError('仅支持无凭据的公开 HTTP(S) URL 和标准端口')
    host = p.hostname.encode('idna').decode().lower()
    if host in ('localhost', 'metadata.google.internal') or host.endswith(('.local', '.internal', '.localhost')):
        raise ValueError('禁止访问内部地址')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError('禁止访问非公网 IP')
    except ValueError as exc:
        if '禁止' in str(exc):
            raise
    return urlunsplit((p.scheme, host + ((':' + str(p.port)) if p.port else ''), p.path or '/', p.query, ''))

async def public_ip(host):
    addresses = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    ips = {a[4][0] for a in addresses}
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError('DNS 指向非公网地址')
    return sorted(ips)[0]

async def request(url, headers=None):
    for _ in range(6):
        url = normalize_url(url)
        p = urlsplit(url)
        ip = await public_ip(p.hostname)
        target = urlunsplit((p.scheme, ('['+ip+']' if ':' in ip else ip) + ((':'+str(p.port)) if p.port else ''), p.path, p.query, ''))
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            async with client.stream('GET', target, headers={'User-Agent':'InsightFlow/0.1', 'Host':p.netloc, **(headers or {})}, extensions={'sni_hostname':p.hostname}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers['location'])
                    # Never forward credentials to a redirect target.
                    headers = None
                    continue
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError('响应超过 2MB 限制')
                return bytes(data).decode('utf-8', errors='replace'), url
    raise ValueError('重定向次数过多')

async def safe_fetch(url, headers=None):
    async with gate:
        for attempt in range(2):
            try:
                await asyncio.sleep(0.5)
                return await request(url, headers)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt:
                    raise

def normalize_content(content):
    lines = []
    for line in content.splitlines():
        line = re.sub(r'\s+', ' ', line).strip()
        if not line or re.fullmatch(r'(Last updated|Updated|更新时间)\s*[:：]?.*\d{4}[-/].*', line, re.I):
            continue
        lines.append(line)
    return '\n'.join(lines)

def extract_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    metadata=[]
    title=soup.find('meta',attrs={'property':'og:title'})
    if title and title.get('content'):metadata.append('Article title: '+title['content'].strip())
    elif soup.title:metadata.append('Article title: '+soup.title.get_text(' ',strip=True))
    for attrs in ({'property':'article:published_time'},{'name':'pubdate'},{'name':'publishdate'},{'name':'date'}):
        node=soup.find('meta',attrs=attrs)
        if node and node.get('content'):
            metadata.append('Published: '+node['content'].strip());break
    for node in soup.select('head,title,meta,link,script,style,nav,footer,header,aside,noscript,[role=navigation]'):
        node.decompose()
    root = soup.find(id='js_content') or soup.find('main') or soup.find('article') or soup.body or soup
    for h in root.find_all(re.compile('^h[1-6]$')):
        h.replace_with('\n' + '#' * int(h.name[1]) + ' ' + h.get_text(' ',strip=True) + '\n')
    return normalize_content('\n'.join(metadata)+'\n'+root.get_text('\n', strip=True))

async def fetch_webpage(url, parser=extract_html):
    url = normalize_url(url)
    p = urlsplit(url)
    try:
        robots, _ = await safe_fetch(urlunsplit((p.scheme,p.netloc,'/robots.txt','','')))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            robots = ''
        else:
            raise ValueError('无法确认 robots.txt 许可，暂不采集') from exc
    robots_parser = RobotFileParser()
    robots_parser.parse(robots.splitlines())
    if not robots_parser.can_fetch('InsightFlow', url):
        raise ValueError('robots.txt 禁止采集')
    delay = robots_parser.crawl_delay('InsightFlow') or robots_parser.crawl_delay('*') or 0
    if delay > 30:
        raise ValueError('站点 crawl-delay 超出 MVP 上限')
    await asyncio.sleep(delay)
    html, final = await safe_fetch(url)
    if urlsplit(final).netloc != p.netloc:
        # Fetch again after checking the redirected origin's robots policy.
        return await fetch_webpage(final,parser)
    text = parser(html)
    if parser is extract_html:
        body='\n'.join(line for line in text.splitlines() if not line.startswith(('Article title:','Published:')))
        if len(body.strip())<40:raise ValueError('仅取得标题/元数据，正文可能需要 JavaScript；未取得可分析正文')
    if len(text) < 40:
        raise ValueError('正文不足，可能需要 JavaScript；请更换公开文档源')
    return text, final

async def github_json(path, accept='application/vnd.github+json'):
    import json
    headers = {'Accept': accept}
    if settings.github_token:
        headers['Authorization'] = 'Bearer ' + settings.github_token
    body, _ = await safe_fetch('https://api.github.com/repos/' + path, headers)
    return body if accept.endswith('raw+json') else json.loads(body)

async def fetch_github_releases(repo):
    releases = await github_json(repo + '/releases?per_page=10')
    return '\n'.join(f"## {r['tag_name']}\n{r.get('body') or ''}" for r in releases)

async def fetch_github_repo(repo):
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise ValueError('GitHub 仓库应为 owner/repo')
    meta = await github_json(repo)
    readme = await github_json(repo + '/readme', 'application/vnd.github.raw+json')
    releases = await fetch_github_releases(repo)
    return normalize_content(f"# {meta['full_name']}\n{meta.get('description') or ''}\n{readme}\n{releases}")

def content_hash(text):
    return hashlib.sha256(normalize_content(text).encode()).hexdigest()
