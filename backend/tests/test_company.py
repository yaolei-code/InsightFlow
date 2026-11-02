from datetime import date,datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from app import models as m, ai, adapters
from app.company_schemas import ProgressOutput,EventOutput
from app.progress import extract_progress
from app.research import create_snapshot
from app.main import app
from app.db import get_db

def event(title='Released a model',**changes):
    data=dict(event_type='model_release',title=title,description='A public model release.',project_name='Model A',capability_tags=['VLA'],progress_stage='research',published_at=date(2026,11,1),occurred_at=None,published_evidence='2026-11-01',occurred_evidence='',evidence_text='Model A released on 2026-11-01.',evidence_level='independent_verification',metrics=[])
    return EventOutput(**{**data,**changes})

def setup_snapshot(db,text='Model A released on 2026-11-01. A robot demo is available.'):
    company=m.Company(name='Fixture Company');db.add(company);db.flush()
    source=m.Source(company_id=company.id,url='https://example.org/article',source_type='company_news');db.add(source);db.commit()
    snap,_,_=create_snapshot(db,source,text,source.url)
    return company,source,snap

async def test_multiple_events_and_provenance(db,monkeypatch):
    company,source,snap=setup_snapshot(db)
    provider=AsyncMock(return_value=ProgressOutput(events=[event(),event('Robot demonstration',event_type='robot_demo',progress_stage='demonstration',evidence_text='A robot demo is available.')]))
    monkeypatch.setattr(ai,'structured',provider)
    assert (await extract_progress(db,snap.id,{}))['events']==2
    assert (await extract_progress(db,snap.id,{}))['reused']
    assert provider.await_count==1
    rows=db.scalars(select(m.ProgressEvent)).all()
    assert len(rows)==2 and all(e.company_id==company.id for e in rows)
    assert all(e.evidence_level=='company_claim' for e in rows)
    for row in rows:
        evidence=db.get(m.EventEvidence,row.evidence_ids[0])
        assert evidence.evidence_text in snap.content and evidence.source_url==snap.source_url
    assert db.scalar(select(m.Project)).company_id==company.id

async def test_missing_evidence_rejected(db,monkeypatch):
    _,_,snap=setup_snapshot(db)
    monkeypatch.setattr(ai,'structured',AsyncMock(return_value=ProgressOutput(events=[event(evidence_text='Invented achievement')])) )
    assert (await extract_progress(db,snap.id,{}))['rejected_evidence']==1
    assert not db.scalars(select(m.ProgressEvent)).all()

async def test_unknown_dates_and_metrics(db,monkeypatch):
    _,_,snap=setup_snapshot(db)
    monkeypatch.setattr(ai,'structured',AsyncMock(return_value=ProgressOutput(events=[event(published_evidence='Unknown date',metrics=[{'name':'robots','value':'1000','unit':'units','evidence_text':'Invented 1000 units'}])])) )
    await extract_progress(db,snap.id,{})
    row=db.scalar(select(m.ProgressEvent))
    assert row.published_at is None and row.occurred_at is None and row.metrics==[]

async def test_progress_schema_failure_atomic(db,monkeypatch):
    _,_,snap=setup_snapshot(db)
    monkeypatch.setattr(ai,'structured',AsyncMock(return_value={'events':[{'title':'invalid'}]}))
    with pytest.raises(ai.ProviderFailure):await extract_progress(db,snap.id,{})
    assert db.scalar(select(m.ProgressRun)).status=='failed'
    assert not db.scalars(select(m.ProgressEvent)).all()

async def test_progress_provider_failure(db,monkeypatch):
    _,_,snap=setup_snapshot(db)
    monkeypatch.setattr(ai,'structured',AsyncMock(side_effect=ai.ProviderFailure('模型 API 连接失败')))
    with pytest.raises(ai.ProviderFailure):await extract_progress(db,snap.id,{})
    assert db.scalar(select(m.ProgressRun)).error=='模型 API 连接失败'

async def test_arxiv_adapter(monkeypatch):
    xml='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Robot model</title><id>https://arxiv.org/abs/2401.12345</id><published>2026-01-01</published><summary>Public abstract</summary><author><name>Author A</name></author></entry></feed>'
    assert 'Public abstract' in adapters.arxiv_metadata(xml)
    with pytest.raises(ValueError):adapters.arxiv_metadata('<feed/>')

async def test_github_and_web_dispatch(monkeypatch):
    github=AsyncMock(return_value='Repo and releases')
    web=AsyncMock(return_value=('Public article','https://example.org/'))
    monkeypatch.setattr(adapters,'fetch_github_repo',github)
    monkeypatch.setattr(adapters,'fetch_webpage',web)
    assert (await adapters.collect(SimpleNamespace(url='https://github.com/owner/repo',source_type='github')))[0]=='Repo and releases'
    await adapters.collect(SimpleNamespace(url='https://example.org/',source_type='company_news'))
    github.assert_awaited_once_with('owner/repo');web.assert_awaited_once()

async def test_wechat_restriction(monkeypatch):
    monkeypatch.setattr(adapters,'fetch_webpage',AsyncMock(return_value=('环境异常，需要完成验证','https://mp.weixin.qq.com/s/a')))
    with pytest.raises(ValueError,match='受限'):await adapters.collect(SimpleNamespace(url='https://mp.weixin.qq.com/s/a',source_type='wechat_official_account'))
    with pytest.raises(ValueError):await adapters.collect(SimpleNamespace(url='https://evil.example/s/a',source_type='wechat_official_account'))

async def test_wechat_search_provider(monkeypatch):
    monkeypatch.setattr(adapters.settings,'wechat_search_api_url','')
    with pytest.raises(ValueError,match='未配置'):await adapters.wechat_provider.search('robot')

async def test_web_parser_and_robots(monkeypatch):
    from app import collector
    fetch=AsyncMock(side_effect=[('User-agent: *\nAllow: /','https://example.org/robots.txt'),('<main>Public company article with sufficient body content for extraction.</main>','https://example.org/article')])
    monkeypatch.setattr(collector,'safe_fetch',fetch)
    text,_=await collector.fetch_webpage('https://example.org/article')
    assert 'Public company article' in text

async def test_metadata_only_is_not_full_body(monkeypatch):
    from app import collector
    monkeypatch.setattr(collector,'safe_fetch',AsyncMock(side_effect=[('User-agent: *\nAllow: /','https://example.org/robots.txt'),('<title>A very long article title with many words but absolutely no public body</title>','https://example.org/article')]))
    with pytest.raises(ValueError,match='元数据'):await collector.fetch_webpage('https://example.org/article')

async def test_future_plan_not_deployment(db,monkeypatch):
    _,_,snap=setup_snapshot(db,'Model A plans commercial deployment in 2027.')
    monkeypatch.setattr(ai,'structured',AsyncMock(return_value=ProgressOutput(events=[event(event_type='commercial_deployment',progress_stage='commercial_deployment',evidence_text=snap.content,published_at=None,published_evidence='')])) )
    await extract_progress(db,snap.id,{})
    row=db.scalar(select(m.ProgressEvent))
    assert row.progress_stage=='unknown' and row.event_type=='other'

async def test_arxiv_permitted_abstract_fallback(monkeypatch):
    monkeypatch.setattr(adapters.asyncio,'sleep',AsyncMock())
    fetch=AsyncMock(side_effect=[ValueError('robots.txt 禁止采集'),('Official abstract metadata','https://arxiv.org/abs/2410.24164')])
    monkeypatch.setattr(adapters,'fetch_webpage',fetch)
    text,url=await adapters.collect(SimpleNamespace(url='https://arxiv.org/abs/2410.24164',source_type='arxiv'))
    assert text=='Official abstract metadata' and url.endswith('2410.24164')
    assert fetch.call_args_list[1].kwargs['parser']==adapters.arxiv_html_metadata

async def test_search_api_filters_public_articles(monkeypatch):
    monkeypatch.setattr(adapters.settings,'wechat_search_api_url','https://example.org/search')
    monkeypatch.setattr(adapters,'safe_fetch',AsyncMock(return_value=('{"results":[{"title":"public","url":"https://mp.weixin.qq.com/s/abc"},{"title":"unrelated","url":"https://example.org/"}]}','https://example.org/search')))
    result=await adapters.wechat_provider.search('robot')
    assert len(result)==1 and result[0]['title']=='public'

def test_company_api_and_weekly_report(db):
    app.dependency_overrides[get_db]=lambda:db
    try:
        client=TestClient(app)
        created=client.post('/api/companies',json={'name':'API Company'})
        assert created.status_code==201
        cid=created.json()['id']
        source=client.post('/api/company-sources',json={'company_id':cid,'source_type':'arxiv','url':'https://arxiv.org/abs/2401.12345'})
        assert source.status_code==201
        assert client.patch('/api/company-sources/'+str(source.json()['id']),json={'url':'https://arxiv.org/abs/2410.24164'}).status_code==200
        assert client.get('/api/companies/'+str(cid)).json()['sources']
        assert client.get('/api/progress-events?tag=VLA').json()==[]
        report=client.post('/api/industry-reports').json()
        assert '不代表行业没有进展' in report['markdown']
        assert client.patch('/api/companies/'+str(cid),json={'is_active':False}).status_code==200
    finally:app.dependency_overrides.clear()

def test_weekly_excludes_unknown_old_and_future(db):
    from datetime import timedelta
    from app.company_api import weekly_report
    company,source,snap=setup_snapshot(db)
    today=datetime.now(timezone.utc).date()
    for title,published in [('RECENT',today.isoformat()),('OLDER',(today-timedelta(days=7)).isoformat()),('FUTURE',(today+timedelta(days=1)).isoformat()),('UNKNOWN',None)]:
        db.add(m.ProgressEvent(company_id=company.id,snapshot_id=snap.id,event_type='other',title=title,description='fixture event',capability_tags=[],progress_stage='unknown',published_at=published,occurred_at=None,evidence_ids=[],evidence_level='company_claim',verification_status='verified',metrics=[]))
    db.commit()
    text=weekly_report(db)['markdown']
    assert 'RECENT' in text
    assert 'OLDER' not in text and 'FUTURE' not in text and 'UNKNOWN' not in text
