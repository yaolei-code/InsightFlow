"""Public discovery providers. Search snippets are never evidence."""
import asyncio,json
from datetime import date
from typing import Protocol
from urllib.parse import urlencode
import httpx
from pydantic import Field,model_validator
from .schemas import Strict
from .config import settings
from .collector import safe_fetch

KEYWORDS=['机器人发布','具身智能','VLA','世界模型','机器人基础模型','真机部署','工厂落地','客户试点','商业交付','批量生产','开源模型','训练框架','数据采集','仿真平台','灵巧手','遥操作','机器人训练','融资','战略合作']

class SearchInput(Strict):
    kind: str=Field(default='industry',pattern='^(industry|company|technology|website|github|papers)$')
    query:str=Field(default='具身智能 机器人',max_length=500)
    company_id:int|None=None
    keywords:list[str]=Field(default_factory=list,max_length=20)
    start_date:date|None=None
    end_date:date|None=None
    domains:list[str]=Field(default_factory=list,max_length=10)
    provider:str=Field(default_factory=lambda:settings.search_provider,pattern='^(tavily|github)$')
    @model_validator(mode='after')
    def dates(self):
        if self.start_date and self.end_date and self.start_date>self.end_date:raise ValueError('开始日期不得晚于结束日期')
        return self

class SearchHit(Strict):
    title:str
    url:str
    snippet:str=''
    published_at:str|None=None

class SearchUnavailable(Exception):pass

class SearchProvider(Protocol):
    async def search(self,query:str,start_date=None,end_date=None,domains=None)->list[SearchHit]:...

class TavilyProvider:
    async def search(self,query,start_date=None,end_date=None,domains=None):
        if not settings.tavily_api_key:raise SearchUnavailable('未配置 TAVILY_API_KEY，无法执行通用搜索')
        payload={'query':query,'max_results':10,'search_depth':'basic','include_answer':False,'include_raw_content':False,'include_domains':domains or []}
        if start_date:payload['start_date']=str(start_date)
        if end_date:payload['end_date']=str(end_date)
        # A fixed official endpoint, not a user-provided credential destination.
        try:
            async with httpx.AsyncClient(timeout=25,follow_redirects=False,trust_env=False) as client:
                for attempt in range(2):
                    response=await client.post('https://api.tavily.com/search',json=payload,headers={'Authorization':'Bearer '+settings.tavily_api_key})
                    if response.status_code in (429,502,503) and attempt==0:
                        await asyncio.sleep(1);continue
                    response.raise_for_status()
                    if len(response.content)>2_000_000:raise SearchUnavailable('搜索响应超过大小上限')
                    data=response.json();break
        except httpx.HTTPStatusError as exc:raise SearchUnavailable(f'Tavily API 失败（HTTP {exc.response.status_code}）') from None
        except (httpx.HTTPError,ValueError):raise SearchUnavailable('Tavily 连接或响应解析失败') from None
        return [SearchHit(title=str(r.get('title',''))[:500],url=r['url'],snippet=str(r.get('content',''))[:4000],published_at=r.get('published_date')) for r in data.get('results',[])[:10]]

class GithubSearchProvider:
    async def search(self,query,start_date=None,end_date=None,domains=None):
        if domains and any(d not in ('github.com','www.github.com') for d in domains):raise SearchUnavailable('GitHub 搜索仅支持 github.com 域名')
        if start_date:query+=' pushed:>='+str(start_date)
        if end_date:query+=' pushed:<='+str(end_date)
        headers={'Accept':'application/vnd.github+json'}
        if settings.github_token:headers['Authorization']='Bearer '+settings.github_token
        try:
            raw,_=await safe_fetch('https://api.github.com/search/repositories?'+urlencode({'q':query,'per_page':10,'sort':'updated'}),headers)
            data=json.loads(raw)
        except Exception:raise SearchUnavailable('GitHub 公开搜索失败或达到限频；可配置 GITHUB_TOKEN') from None
        # Repository pushed_at is not a news publication date.
        return [SearchHit(title=r['full_name'],url=r['html_url'],snippet=r.get('description') or '') for r in data.get('items',[])[:10]]

providers={'tavily':TavilyProvider(),'github':GithubSearchProvider()}

async def search_industry_news(query,date_range=None,domains=None,provider='tavily'):
    start,end=date_range or (None,None)
    return await providers[provider].search(query,start,end,domains)

async def search_company_updates(company,keywords,date_range=None,**kwargs):
    return await search_industry_news(company+' '+ ' '.join(keywords),date_range,**kwargs)

async def search_technology_updates(technology,date_range=None,**kwargs):
    return await search_industry_news(technology+' 机器人 embodied AI',date_range,**kwargs)

async def search_company_website(company,**kwargs):
    return await search_industry_news(company+' 官方网站 official website',**kwargs)

async def search_company_github(company,**kwargs):
    return await search_industry_news(company,provider='github',**kwargs)

async def search_company_papers(company,**kwargs):
    return await search_industry_news(company,domains=['arxiv.org'],**kwargs)
