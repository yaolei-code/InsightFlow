from datetime import datetime,timezone,timedelta
from unittest.mock import AsyncMock
from sqlalchemy import select
from fastapi.testclient import TestClient
from app import models as m,workspace_api as w,ai
from app.db import get_db
from app.main import app
from app.research import create_snapshot
from app.intelligence_service import quality,records,detail,report

def event(db,title='Model Alpha released',date=None,level='company_claim',stage='research',suffix='a'):
    company=db.scalar(select(m.Company).where(m.Company.name=='Fixture Corp'))
    if not company:company=m.Company(name='Fixture Corp');db.add(company);db.flush()
    source=m.Source(company_id=company.id,url='https://example.org/'+suffix,source_type='company_news');db.add(source);db.commit()
    snap,_,_=create_snapshot(db,source,'Model Alpha released. Company claim only.',source.url)
    ev=m.EventEvidence(company_id=company.id,snapshot_id=snap.id,source_url=source.url,evidence_text='Model Alpha released.',evidence_level=level);db.add(ev);db.flush()
    row=m.ProgressEvent(company_id=company.id,snapshot_id=snap.id,event_type='model_release',title=title,description='Fixture release.',capability_tags=['VLA'],progress_stage=stage,published_at=date,occurred_at=None,evidence_ids=[ev.id],evidence_level=level,verification_status='verified',metrics=[]);db.add(row);db.commit();return row

def test_duplicate_sources_group_without_deletion(db):
    today=datetime.now(timezone.utc).date().isoformat()
    a=event(db,date=today);b=event(db,date=today,level='technical_artifact',suffix='b')
    quality(db);quality(db)
    rows=records(db)
    assert len(rows)==1 and set(rows[0]['member_ids'])=={a.id,b.id}
    assert len(rows[0]['evidence_levels'])==2
    assert len(db.scalars(select(m.ProgressEvent)).all())==2

def test_similar_different_models_not_merged(db):
    event(db);event(db,title='Model Beta released',suffix='b')
    quality(db);assert len(records(db))==2

def test_semantic_membership_survives_score_recompute(db):
    a=event(db);b=event(db,title='Model Alpha announced',suffix='b');quality(db)
    left=db.get(m.ClusterMember,a.id);right=db.get(m.ClusterMember,b.id)
    cluster=db.get(m.EventCluster,left.cluster_id);cluster.method='rule_recall+llm'
    right.cluster_id=left.cluster_id;db.commit()
    quality(db)
    assert len(records(db))==1 and len(db.scalars(select(m.ClusterMember)).all())==2

def test_same_title_different_date_not_merged(db):
    event(db,date='2026-01-01');event(db,date='2026-02-01',suffix='b')
    quality(db);assert len(records(db))==2

def test_unknown_and_old_dates_not_recent(db):
    event(db);event(db,date='2020-01-01',suffix='b');quality(db)
    assert records(db,days=7)==[]

def test_recent_date_and_evidence_detail(db):
    row=event(db,date=datetime.now(timezone.utc).date().isoformat());quality(db)
    assert len(records(db,days=7))==1
    data=detail(db,row.id)
    assert data['evidence'][0]['collected_at'] and data['evidence'][0]['source_type']=='company_news'
    assert data['evidence'][0]['verification_status']=='verified' and data['uncertainties']

def test_high_importance_company_claim_stays_pending(db):
    e=event(db,stage='scaled_production');quality(db)
    data=records(db)[0]
    assert data['importance']>=50 and data['review_status']=='pending' and data['evidence_levels']==['company_claim']

def test_follow_unfollow_and_personalized(db):
    e=event(db,date=datetime.now(timezone.utc).date().isoformat());quality(db)
    app.dependency_overrides[get_db]=lambda:db
    try:
        client=TestClient(app)
        assert client.get('/api/workspace/events?followed=true').json()['total']==0
        f=client.post('/api/workspace/follows',json={'target_type':'company','target_key':str(e.company_id)}).json()
        assert client.get('/api/workspace/events?followed=true').json()['total']==1
        assert client.post('/api/workspace/follows',json={'target_type':'company','target_key':str(e.company_id)}).json()['id']==f['id']
        digest=client.post('/api/workspace/digest?days=7&followed=true').json()
        assert '[E' in digest['markdown'] and 'Snapshot' in digest['markdown']
        client.delete('/api/workspace/follows/'+str(f['id']))
        assert client.get('/api/workspace/events?followed=true').json()['total']==0
    finally:app.dependency_overrides.clear()

def test_technology_follow_and_filter(db):
    event(db);db.add(m.UserFollow(target_type='technology',target_key='VLA'));db.commit();quality(db)
    assert len(records(db,followed=True,technology='VLA'))==1
    assert records(db,technology='World Model')==[]

def test_empty_report_honest(db):
    saved=report(db,'Empty',[],'7 days')
    assert '没有符合条件' in saved.markdown

async def test_real_task_flow_mock_model_offline(db,monkeypatch):
    event(db,date=datetime.now(timezone.utc).date().isoformat());quality(db)
    row=m.ResearchSession(user_query='VLA research',parameters={'days':30,'company_id':None,'technology':None,'allow_search':False});db.add(row);db.commit()
    monkeypatch.setattr(w,'DBSession',lambda:db)
    monkeypatch.setattr(ai,'structured',AsyncMock(side_effect=[w.Scope(company_ids=[],technology='VLA'),w.Decision(sufficient=True,plan_summary='Use saved evidence',search_query='',gaps=['Customer evidence absent'])]))
    await w.run_research(row.id)
    saved=db.get(m.ResearchSession,row.id)
    assert saved.status=='completed' and saved.report_id and len(saved.trace)>=3

async def test_insufficient_evidence_calls_real_tool_adapter_mocked(db,monkeypatch):
    from app import discovery
    row=m.ResearchSession(user_query='Latest VLA updates',parameters={'days':30,'company_id':None,'technology':'VLA','allow_search':True});db.add(row);db.commit()
    monkeypatch.setattr(w,'DBSession',lambda:db)
    monkeypatch.setattr(ai,'structured',AsyncMock(side_effect=[w.Scope(company_ids=[],technology='VLA'),w.Decision(sufficient=False,plan_summary='Need fresh sources',search_query='VLA robot news',gaps=['No current evidence'])]))
    search=AsyncMock(return_value={'candidate_ids':[],'results':0})
    monkeypatch.setattr(discovery,'discover_search',search)
    await w.run_research(row.id)
    search.assert_awaited_once()
    assert db.get(m.ResearchSession,row.id).status=='completed'
    assert search.call_args.args[1].start_date is not None

async def test_semantic_confirmation_and_numeric_conflict(db,monkeypatch):
    from app.semantic_clusters import semantic_recompute,Results,Pair
    a=event(db);b=event(db,title='Model Alpha announced',suffix='b')
    response=Results(pairs=[Pair(first=a.id,second=b.id,same_progress=True,shared_anchor='Model Alpha',reason='Same specific model release')])
    monkeypatch.setattr(ai,'structured',AsyncMock(return_value=response))
    assert (await semantic_recompute(db))['merged']==1
    assert len(records(db))==1
    quality(db);assert len(records(db))==1

async def test_semantic_conflicting_numbers_not_merged(db,monkeypatch):
    from app.semantic_clusters import semantic_recompute,Results,Pair
    a=event(db);b=event(db,title='Model Alpha announced',suffix='b')
    a.metrics=[{'name':'accuracy','value':'90','unit':'%'}];b.metrics=[{'name':'accuracy','value':'95','unit':'%'}];db.commit()
    monkeypatch.setattr(ai,'structured',AsyncMock(return_value=Results(pairs=[Pair(first=a.id,second=b.id,same_progress=True,shared_anchor='Model Alpha',reason='model thinks same')])) )
    assert (await semantic_recompute(db))['merged']==0
    assert len(records(db))==2 and all(e['review_status']=='questionable' for e in records(db))

def test_review_does_not_change_evidence_level(db):
    e=event(db);quality(db);app.dependency_overrides[get_db]=lambda:db
    try:
        client=TestClient(app);client.patch(f'/api/workspace/events/{e.id}/review',json={'status':'reviewed'})
        value=client.get(f'/api/workspace/events/{e.id}').json()
        assert value['review_status']=='reviewed' and value['evidence_levels']==['company_claim']
    finally:app.dependency_overrides.clear()
