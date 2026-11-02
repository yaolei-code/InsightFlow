from unittest.mock import AsyncMock
from sqlalchemy import select
from app import ingestion,models as m
from app.discovery import save_candidate
from app.search import SearchHit

def candidate(db,title='Acme robot release',snippet=''):
    company=m.Company(name='Acme',official_url='https://acme.example/');db.add(company);db.commit()
    row,_=save_candidate(db,SearchHit(title=title,url='https://media.example/news/release-123',snippet=snippet),'fixture','q');db.commit()
    return row

async def test_no_manual_gate_and_idempotence(db,monkeypatch):
    row=candidate(db)
    fetch=AsyncMock(return_value=('Acme released a robot. This public article describes the release.','https://media.example/news/release-123'))
    extract=AsyncMock(return_value={'events':2})
    monkeypatch.setattr(ingestion.adapters,'collect',fetch);monkeypatch.setattr(ingestion,'extract_progress',extract)
    monkeypatch.setattr(ingestion.ai,'structured',AsyncMock(return_value=ingestion.CompanyAttribution(company_name='Acme',evidence_text='Acme released a robot.')))
    result=await ingestion.ingest_candidate(db,row,{})
    assert result['status']=='completed' and row.decision_method=='automatic' and row.review_status=='approved'
    assert db.scalar(select(m.Snapshot)).content.startswith('Acme released')
    assert (await ingestion.ingest_candidate(db,row,{}))['reused']
    assert fetch.await_count==1 and extract.await_count==1

async def test_snippet_not_company_evidence(db,monkeypatch):
    row=candidate(db,title='Robot story',snippet='Acme delivered robots')
    monkeypatch.setattr(ingestion.adapters,'collect',AsyncMock(return_value=('Unrelated company article with no identified enterprise.','https://media.example/news/release-123')))
    monkeypatch.setattr(ingestion.ai,'structured',AsyncMock(return_value=ingestion.CompanyAttribution(company_name=None,evidence_text='')))
    result=await ingestion.ingest_candidate(db,row,{})
    assert result['status']=='skipped' and not db.scalars(select(m.ProgressEvent)).all()

async def test_background_mention_not_owner(db,monkeypatch):
    row=candidate(db,title='NewCo announced a robot')
    monkeypatch.setattr(ingestion.ai,'structured',AsyncMock(return_value=ingestion.CompanyAttribution(company_name='NewCo',evidence_text='NewCo announced its robot.')))
    cid=await ingestion.resolve_company(db,row,'NewCo announced its robot. Acme is a competitor.',{})
    assert db.get(m.Company,cid).name=='NewCo'

async def test_fetch_failure_persisted(db,monkeypatch):
    row=candidate(db)
    monkeypatch.setattr(ingestion.adapters,'collect',AsyncMock(side_effect=ValueError('robots.txt 禁止采集')))
    result=await ingestion.ingest_candidate(db,row,{})
    assert result['status']=='failed' and 'robots' in row.processing_error

async def test_index_skipped(db):
    row=candidate(db);row.url='https://media.example/news';db.commit()
    assert (await ingestion.ingest_candidate(db,row,{}))['status']=='skipped'

async def test_rejected_not_ingested(db):
    row=candidate(db);row.review_status='rejected';db.commit()
    result=await ingestion.ingest_candidate(db,row,{})
    assert result['status']=='skipped' and row.source_id is None
