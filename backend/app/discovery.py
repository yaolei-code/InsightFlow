import asyncio,json,re
import xml.etree.ElementTree as ET
import httpx
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode,urljoin
from bs4 import BeautifulSoup
from sqlalchemy import select
from . import models as m
from .collector import normalize_url,fetch_webpage
from .db import Session,utcnow
from .search import SearchInput,SearchHit,KEYWORDS,providers,SearchUnavailable

def public_error(exc):
    if isinstance(exc,httpx.HTTPStatusError):return f'HTTP {exc.response.status_code}'
    if isinstance(exc,ValueError):return str(exc)[:180]
    return type(exc).__name__

def canonical_url(url):
    p=urlsplit(normalize_url(url))
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid','spm','from','isappinstalled')]
    # A trailing slash can identify a different resource; never rewrite it away.
    return urlunsplit((p.scheme,p.netloc,p.path or '/',urlencode(sorted(query)),''))

def matches(text,term):
    if term.isascii():return bool(re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])',text,re.I))
    return term.casefold() in text.casefold()

def company_matches(db,text):
    found=set()
    for company in db.scalars(select(m.Company)):
        if matches(text,company.name):found.add(company.id)
    for alias in db.scalars(select(m.CompanyAlias)):
        if matches(text,alias.alias):found.add(alias.company_id)
    return found

def candidate_type(domain,default='other'):
    if domain=='github.com':return 'github'
    if domain=='arxiv.org':return 'arxiv'
    if domain=='mp.weixin.qq.com':return 'wechat_official_account'
    if domain.endswith(('.gov.cn','.gov')):return 'government'
    return default

def save_candidate(db,hit,by,query,company_id=None,source_type='other'):
    url=canonical_url(hit.url);domain=urlsplit(url).hostname
    known=db.scalar(select(m.SourceCandidate).where(m.SourceCandidate.url==url))
    history={'provider':by,'query':query,'at':utcnow()}
    if known:
        known.discovery_history=[*known.discovery_history[-19:],history]
        return known,False
    matched=company_matches(db,hit.title+' '+hit.snippet)
    if company_id is None and len(matched)==1:company_id=next(iter(matched))
    if company_id is None:
        owners=[c.id for c in db.scalars(select(m.Company)) if c.official_url and urlsplit(c.official_url).hostname==domain]
        if len(owners)==1:company_id=owners[0]
    existing=next((s for s in db.scalars(select(m.Source)) if canonical_url(s.url)==url and (company_id is None or s.company_id==company_id)),None)
    text=hit.title+' '+hit.snippet
    relevance=min(100,sum(matches(text,k) for k in KEYWORDS+['robot','robotics','embodied','humanoid','foundation model']) * 15 + (40 if company_id else 0))
    kind=candidate_type(domain,source_type)
    company=db.get(m.Company,company_id) if company_id else None
    if kind=='other' and company and urlsplit(company.official_url).hostname==domain:kind='official_website'
    trust='technical_artifact' if kind in ('github','arxiv') else ('company_claim' if company and urlsplit(company.official_url).hostname==domain else 'unverified_secondary')
    row=m.SourceCandidate(title=hit.title[:500],url=url,domain=domain,source_type=kind,company_id=company_id,discovered_by=by,discovery_query=query,published_at=hit.published_at,discovered_at=utcnow(),snippet=hit.snippet[:4000],relevance_score=relevance,source_trust_level=trust,source_id=existing.id if existing else None,review_status='pending',discovery_history=[history])
    db.add(row);db.flush();return row,True

def parse_links(html,base):
    if '<!DOCTYPE' in html.upper() and '<html' not in html.lower():raise ValueError('不支持带实体声明的 sitemap')
    if html.lstrip().startswith('<?xml') or '<urlset' in html or '<sitemapindex' in html:
        root=ET.fromstring(html)
        links=[{'title':'','url':node.text.strip()} for node in root.iter() if node.tag.endswith('}loc') and node.text][:200]
        return {'links':links,'sitemap_index':root.tag.endswith('sitemapindex'),'base':base}
    soup=BeautifulSoup(html,'html.parser')
    links=[]
    for a in soup.select('a[href]')[:2000]:
        href=a.get('href','')
        if href.startswith(('javascript:','mailto:','tel:','#')):continue
        links.append({'title':a.get_text(' ',strip=True)[:500],'url':urljoin(base,href)})
        if len(links)>=200:break
    return {'links':links,'sitemap_index':False,'base':base}

async def discover_seed(db,seed):
    urls=[seed.url]
    if not urlsplit(seed.url).path.endswith('.xml'):
        p=urlsplit(seed.url);urls.append(urlunsplit((p.scheme,p.netloc,'/sitemap.xml','','')))
    errors=[];pages=0;added=0;seen=0
    for index in range(4):
        if index>=len(urls):break
        url=urls[index]
        try:
            def parser(html):return json.dumps(parse_links(html,url),ensure_ascii=False)
            text,final=await fetch_webpage(url,parser=parser)
            data=json.loads(text);pages+=1
            if data['sitemap_index']:
                # At most two nested maps; never crawl an unbounded sitemap tree.
                for link in data['links'][:2]:
                    if urlsplit(link['url']).hostname==urlsplit(seed.url).hostname and link['url'] not in urls:urls.append(link['url'])
                continue
            for link in data['links']:
                if seen>=60:break
                try:
                    normalized=canonical_url(urljoin(final,link['url']));host=urlsplit(normalized).hostname
                    if host not in (urlsplit(seed.url).hostname,'mp.weixin.qq.com','github.com','arxiv.org'):continue
                    title=link['title'];interesting=any(matches(title+' '+normalized,k) for k in KEYWORDS+['robot','news','blog','research','release','humanoid','model']) or bool(company_matches(db,title))
                    if not interesting:continue
                    hit=SearchHit(title=title or normalized,url=normalized)
                    _,created=save_candidate(db,hit,'sitemap' if url.endswith('.xml') else 'seed_links',url,seed.company_id,seed.source_type)
                    added+=int(created);seen+=1
                except ValueError:continue
            db.commit()
        except Exception as exc:
            errors.append({'url':url,'error':public_error(exc)})
        if len(urls)>4:urls=urls[:4]
    seed.last_checked_at=utcnow();seed.last_status='success' if pages and not errors else ('partial' if pages else 'error')
    seed.error=json.dumps(errors,ensure_ascii=False) if errors else None
    db.commit()
    return {'pages_read':pages,'candidates_seen':seen,'candidates_added':added,'errors':errors}

async def discover_search(db,body):
    company=db.get(m.Company,body.company_id) if body.company_id else None
    if body.company_id and not company:raise ValueError('企业不存在')
    aliases=[a.alias for a in db.scalars(select(m.CompanyAlias).where(m.CompanyAlias.company_id==body.company_id))] if company else []
    terms=body.keywords or KEYWORDS[:3]
    subject=(company.name+' '+ ' '.join(aliases[:2])) if company else body.query
    if body.kind=='website':query=subject+' 官方网站 official website'
    elif body.kind=='github':query=company.name if company else body.query
    elif body.kind=='papers':query=subject+' robotics'
    else:query=subject+' '+ ' '.join(terms)
    domains=body.domains or (['arxiv.org'] if body.kind=='papers' else None)
    if body.provider=='github' and body.kind!='github':raise ValueError('GitHub Provider 仅用于仓库搜索，不可替代新闻搜索')
    hits=await providers[body.provider].search(query,body.start_date,body.end_date,domains)
    added=0
    for hit in hits:
        try:
            _,created=save_candidate(db,hit,body.provider,query,body.company_id,source_type='industry_media' if body.kind in ('industry','company','technology') else 'other')
            added+=int(created)
        except ValueError:continue
    db.commit()
    return {'query':query,'results':len(hits),'candidates_added':added,'provider':body.provider,'date_filter':{'start':str(body.start_date) if body.start_date else None,'end':str(body.end_date) if body.end_date else None},'note':'日期来自搜索元数据，须以采集正文核验；GitHub 日期过滤是 pushed 时间。'}

lock=asyncio.Lock()

async def execute_discovery(id):
    async with lock:
        with Session() as db:
            run=db.get(m.DiscoveryRun,id);run.status='running';db.commit()
            try:
                if run.kind=='seed':
                    seed=db.get(m.DiscoverySeed,run.parameters['seed_id'])
                    if not seed or not seed.is_active:raise ValueError('来源库条目不存在或已停用')
                    result=await asyncio.wait_for(discover_seed(db,seed),timeout=120)
                else:result=await asyncio.wait_for(discover_search(db,SearchInput.model_validate(run.parameters)),timeout=60)
                run.status='completed';run.result=result
            except Exception as exc:
                db.rollback();run=db.get(m.DiscoveryRun,id);run.status='failed'
                run.error=str(exc)[:300] if isinstance(exc,(SearchUnavailable,ValueError)) else '发现失败：'+type(exc).__name__
            run.finished_at=utcnow();db.commit()
