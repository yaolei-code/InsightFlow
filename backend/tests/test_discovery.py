from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from app import models as m, search, discovery
from app.search import SearchInput,SearchHit,SearchUnavailable
from app.db import get_db
from app.main import app

def company(db):
    c=m.Company(name='宇树科技',official_url='https://unitree.com/')
    db.add(c);db.flush();db.add(m.CompanyAlias(company_id=c.id,alias='Unitree'));db.commit();return c

def test_tracking_url_dedup(db):
    a,new=discovery.save_candidate(db,SearchHit(title='机器人新闻',url='https://example.org/news/?utm_source=x&b=2&a=1#section'),'fixture','query')
    b,again=discovery.save_candidate(db,SearchHit(title='机器人新闻',url='https://example.org/news/?a=1&b=2'),'fixture2','query2')
    assert new and not again and a.id==b.id and len(b.discovery_history)==2

def test_alias_and_existing_source(db):
    c=company(db)
    source=m.Source(company_id=c.id,url='https://unitree.com/news',source_type='company_news');db.add(source);db.commit()
    row,_=discovery.save_candidate(db,SearchHit(title='Unitree robot release',url=source.url),'fixture','query')
    assert row.company_id==c.id and row.source_id==source.id and row.review_status=='pending'
    assert row.relevance_score>0 and row.source_trust_level=='company_claim'

def test_company_ambiguity_not_guessed(db):
    c=company(db);other=m.Company(name='Other Robotics');db.add(other);db.commit()
    row,_=discovery.save_candidate(db,SearchHit(title='Unitree and Other Robotics',url='https://media.example/article'),'fixture','query')
    assert row.company_id is None

def test_no_event_from_snippet(db):
    company(db)
    discovery.save_candidate(db,SearchHit(title='Unitree factory',url='https://media.example/story',snippet='Delivered 100000 robots'),'fixture','query')
    assert not db.scalars(select(m.ProgressEvent)).all() and not db.scalars(select(m.Snapshot)).all()

@pytest.mark.parametrize('url',['http://localhost/a','http://10.0.0.1/a','file:///etc/passwd'])
def test_candidate_ssrf_rejected(db,url):
    with pytest.raises(ValueError):discovery.save_candidate(db,SearchHit(title='x',url=url),'fixture','q')

async def test_missing_search_key(monkeypatch):
    monkeypatch.setattr(search.settings,'tavily_api_key','')
    with pytest.raises(SearchUnavailable,match='未配置'):await search.TavilyProvider().search('机器人')

async def test_failed_run_persists_safe_error(db,monkeypatch):
    run=m.DiscoveryRun(kind='search',parameters=SearchInput().model_dump(mode='json'));db.add(run);db.commit()
    monkeypatch.setattr(discovery,'Session',lambda:db)
    monkeypatch.setattr(search.settings,'tavily_api_key','')
    await discovery.execute_discovery(run.id)
    saved=db.get(m.DiscoveryRun,run.id)
    assert saved.status=='failed' and '未配置' in saved.error

def test_trailing_slash_preserved():
    assert discovery.canonical_url('https://example.org/research/')!='https://example.org/research'

def test_article_metadata_saved(db):
    from app.collector import extract_html
    from app.research import create_snapshot
    source=db.get(m.Source,1)
    content=extract_html('<html><head><title>Robot release</title><meta property="article:published_time" content="2026-11-01T10:00:00Z"></head><main>A documented public robot release with evidence.</main></html>')
    snap,_,_=create_snapshot(db,source,content,source.url)
    assert snap.title=='Robot release' and snap.published_at=='2026-11-01' and snap.source_type==source.source_type

async def test_search_schema_and_filters(monkeypatch):
    monkeypatch.setattr(search.settings,'tavily_api_key','fixture-key')
    response=SimpleNamespace(status_code=200,content=b'{}',raise_for_status=lambda:None,json=lambda:{'results':[{'title':'Test','url':'https://example.org/','content':'Snippet'}]})
    client=AsyncMock();client.post.return_value=response
    context=AsyncMock();context.__aenter__.return_value=client
    monkeypatch.setattr(search.httpx,'AsyncClient',lambda **kwargs:context)
    result=await search.TavilyProvider().search('机器人',date(2026,10,1),date(2026,11,1),['example.org'])
    payload=client.post.call_args.kwargs['json']
    assert payload['start_date']=='2026-10-01' and payload['include_domains']==['example.org']
    assert result[0].snippet=='Snippet'

async def test_search_persists_candidates_only(db,monkeypatch):
    c=company(db);provider=SimpleNamespace(search=AsyncMock(return_value=[SearchHit(title='Unitree pilot',url='https://example.org/story')]))
    monkeypatch.setitem(search.providers,'tavily',provider)
    result=await discovery.discover_search(db,SearchInput(kind='company',company_id=c.id,keywords=['客户试点']))
    assert result['candidates_added']==1 and 'Unitree' in result['query']
    assert not db.scalars(select(m.ProgressEvent)).all()

async def test_seed_links_and_nested_sitemap(db,monkeypatch):
    seed=m.DiscoverySeed(name='Fixture media',url='https://example.org/',source_type='industry_media');db.add(seed);db.commit()
    pages={seed.url:'<a href="/story?utm_source=x">机器人发布</a><a href="http://127.0.0.1/">robot</a>', 'https://example.org/sitemap.xml':'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.org/news.xml</loc></sitemap></sitemapindex>', 'https://example.org/news.xml':'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.org/news/robot</loc></url></urlset>'}
    async def fetch(url,parser):return parser(pages[url]),url
    monkeypatch.setattr(discovery,'fetch_webpage',fetch)
    result=await discovery.discover_seed(db,seed)
    assert result['candidates_added']==2 and result['pages_read']==3
    assert seed.last_status=='success'

def test_review_boundary_and_idempotence(db):
    c=company(db)
    app.dependency_overrides[get_db]=lambda:db
    try:
        client=TestClient(app)
        response=client.post('/api/source-candidates',json={'title':'Public story','url':'https://example.org/story','company_id':c.id,'source_type':'industry_media'})
        assert response.status_code==201;cid=response.json()['id']
        approved=client.patch(f'/api/source-candidates/{cid}/review',json={'review_status':'approved'})
        assert approved.status_code==200 and approved.json()['source_id']
        assert client.patch(f'/api/source-candidates/{cid}/review',json={'review_status':'approved'}).json()['source_id']==approved.json()['source_id']
        assert client.patch(f'/api/source-candidates/{cid}/review',json={'review_status':'rejected'}).status_code==409
        assert not db.scalars(select(m.ProgressEvent)).all()
        assert client.get('/api/source-candidates?review_status=approved').json()['total']==1
    finally:app.dependency_overrides.clear()

def test_unknown_company_requires_review(db):
    row,_=discovery.save_candidate(db,SearchHit(title='Robot news',url='https://example.org/x'),'fixture','q');db.commit()
    app.dependency_overrides[get_db]=lambda:db
    try:
        response=TestClient(app).patch(f'/api/source-candidates/{row.id}/review',json={'review_status':'approved'})
        assert response.status_code==400
    finally:app.dependency_overrides.clear()
