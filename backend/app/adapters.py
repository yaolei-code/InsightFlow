"""Adapters preserve the shared public HTTP security boundary."""
import asyncio
import json
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urlsplit, urlencode
from .collector import fetch_webpage, fetch_github_repo, safe_fetch, normalize_url
from .config import settings

limits={name:asyncio.Semaphore(1) for name in ('arxiv','wechat','github','web')}

def arxiv_metadata(xml):
    root=ET.fromstring(xml)
    ns={'a':'http://www.w3.org/2005/Atom'}
    entries=root.findall('a:entry',ns)
    if not entries:
        raise ValueError('arXiv 未返回论文条目')
    output=[]
    for entry in entries:
        value=lambda name:' '.join((entry.findtext('a:'+name,'',ns)).split())
        authors=', '.join(n.text or '' for n in entry.findall('a:author/a:name',ns))
        output.append(f"# {value('title')}\nURL: {value('id')}\nPublished: {value('published')}\nUpdated: {value('updated')}\nAuthors: {authors}\nAbstract: {value('summary')}")
    return '\n\n'.join(output)

def arxiv_html_metadata(html):
    soup=BeautifulSoup(html,'html.parser')
    title=soup.find('meta',attrs={'name':'citation_title'})
    if not title:raise ValueError('arXiv 摘要页缺少论文元数据')
    values=[]
    for name in ('citation_title','citation_author','citation_date','citation_arxiv_id'):
        for node in soup.find_all('meta',attrs={'name':name}):
            values.append(name+': '+node.get('content',''))
    abstract=soup.find('blockquote',class_='abstract')
    if abstract:values.append('Abstract: '+abstract.get_text(' ',strip=True))
    return '\n'.join(values)

async def collect(source):
    p=urlsplit(normalize_url(source.url))
    if source.source_type in ('github','github_repository'):
        if p.hostname!='github.com':
            raise ValueError('GitHub 来源必须为 github.com/owner/repo')
        async with limits['github']:
            return await fetch_github_repo(p.path.strip('/')),source.url
    if source.source_type=='arxiv':
        if p.hostname not in ('arxiv.org','export.arxiv.org'):
            raise ValueError('论文来源仅支持官方 arXiv URL')
        match=re.fullmatch(r'/(?:abs|pdf)/([\w.-]+(?:/\d+)?)(?:\.pdf)?',p.path)
        if not match:
            raise ValueError('请提交 arxiv.org/abs/论文编号')
        paper=match.group(1).removesuffix('.pdf')
        api='https://export.arxiv.org/api/query?'+urlencode({'id_list':paper,'max_results':1})
        async with limits['arxiv']:
            await asyncio.sleep(3)
            try:
                text,_=await fetch_webpage(api,parser=arxiv_metadata)
            except ValueError as exc:
                if 'robots.txt' not in str(exc):raise
                # API policy may disallow crawlers; only use an allowed public abstract page.
                text,_=await fetch_webpage('https://arxiv.org/abs/'+paper,parser=arxiv_html_metadata)
            return text,source.url
    if source.source_type=='wechat_official_account':
        if p.hostname!='mp.weixin.qq.com' or not p.path.startswith('/s'):
            raise ValueError('请导入 mp.weixin.qq.com 的公开文章 URL')
        async with limits['wechat']:
            text,url=await fetch_webpage(source.url)
            if any(word in text for word in ('环境异常','访问过于频繁','完成验证','该内容已被发布者删除')):
                raise ValueError('公众号文章受限或已删除；不绕过验证')
            return text,url
    if source.source_type=='video':
        raise ValueError('MVP 不下载视频，请导入公开文字稿或报道来源')
    async with limits['web']:
        return await fetch_webpage(source.url)

class PublicWechatProvider:
    async def fetch(self,url):
        from types import SimpleNamespace
        return await collect(SimpleNamespace(url=url,source_type='wechat_official_account'))

    async def search(self,query):
        if not settings.wechat_search_api_url:
            raise ValueError('未配置合规公众号搜索 Provider；可手动导入文章 URL')
        endpoint=normalize_url(settings.wechat_search_api_url)
        headers={}
        if settings.wechat_search_api_key:
            headers['Authorization']='Bearer '+settings.wechat_search_api_key
        body,_=await safe_fetch(endpoint+('&' if '?' in endpoint else '?')+urlencode({'q':query}),headers)
        payload=json.loads(body)
        results=[]
        for item in payload.get('results',[])[:20]:
            url=normalize_url(item['url'])
            if urlsplit(url).hostname=='mp.weixin.qq.com':
                results.append({'title':str(item.get('title',''))[:200],'url':url})
        return results

wechat_provider=PublicWechatProvider()

def register_wechat_provider(provider):
    """Provider implements async search(query) and fetch(url). No private cookies."""
    global wechat_provider
    wechat_provider=provider
