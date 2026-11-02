from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from app import models as m, ai
from app.schemas import ClaimOutput, Extraction
from app.research import create_snapshot
from app.extraction import extract_saved_snapshot
from app.evidence import validate_evidence

def output(text='Simulation supported.',status='supported'):
    return ClaimOutput(dimension='Simulation',claim_text=text,claim_status=status,availability='unknown',evidence_text=text)

def snapshot(db,text='Simulation supported.'):
    source=db.get(m.Source,1)
    return create_snapshot(db,source,text,source.url)[0]

async def test_normal_and_repeated(db,monkeypatch):
    snap=snapshot(db)
    provider=AsyncMock(return_value=Extraction(claims=[output()]))
    monkeypatch.setattr(ai,'extract_claims',provider)
    result=await extract_saved_snapshot(db,snap.id,{})
    assert result['total']==8 and result['verified']==1 and result['unknown']==7
    assert (await extract_saved_snapshot(db,snap.id,{}))['reused']
    assert provider.await_count==1
    assert len(db.scalars(select(m.Claim)).all())==8
    assert db.scalar(select(m.Claim).where(m.Claim.claim_status=='supported')).observed_at==snap.created_at

async def test_unknown_without_evidence(db,monkeypatch):
    snap=snapshot(db)
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[])))
    result=await extract_saved_snapshot(db,snap.id,{})
    assert result['unknown']==8 and result['verified']==0

async def test_missing_quote_not_asserted(db,monkeypatch):
    snap=snapshot(db,'Training only')
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[output()])))
    result=await extract_saved_snapshot(db,snap.id,{})
    row=db.scalar(select(m.Claim).where(m.Claim.dimension=='Simulation'))
    assert row.claim_status=='unknown' and row.verification_status=='unverified'
    assert result['verified']==0

async def test_missing_snapshot(db):
    with pytest.raises(ValueError,match='Snapshot'):
        await extract_saved_snapshot(db,999,{})
    assert not db.scalars(select(m.Claim)).all()

def test_provenance_mismatch(db):
    snap=snapshot(db)
    with pytest.raises(ValueError,match='产品'):
        validate_evidence(db,999,snap.id,snap.source_url,output())
    with pytest.raises(ValueError,match='URL'):
        validate_evidence(db,1,snap.id,'https://evil.example/',output())

async def test_conflicting_current_sources(db,monkeypatch):
    snap=snapshot(db)
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[output()])))
    await extract_saved_snapshot(db,snap.id,{})
    source=m.Source(product_id=1,url='https://example.org/',source_type='documentation')
    db.add(source);db.commit()
    other,_,_=create_snapshot(db,source,'Simulation not supported.',source.url)
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[output('Simulation not supported.','not_supported')])))
    result=await extract_saved_snapshot(db,other.id,{})
    assert result['conflicting']==1
    rows=db.scalars(select(m.Claim).where(m.Claim.dimension=='Simulation')).all()
    assert len(rows)==2 and all(c.verification_status=='conflicting' for c in rows)

@pytest.mark.parametrize('failure',[ai.ProviderFailure('模型 API 请求失败（HTTP 401）'),ValueError('bad schema')])
async def test_failure_persisted_without_claims(db,monkeypatch,failure):
    snap=snapshot(db)
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(side_effect=failure))
    with pytest.raises(ai.ProviderFailure): await extract_saved_snapshot(db,snap.id,{})
    assert not db.scalars(select(m.Claim)).all()
    assert db.scalar(select(m.ExtractionRun)).status=='failed'

async def test_invalid_provider_schema(db,monkeypatch):
    snap=snapshot(db)
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value={'claims':[{'dimension':'invented'}]}))
    with pytest.raises(ai.ProviderFailure,match='Schema'): await extract_saved_snapshot(db,snap.id,{})
    assert not db.scalars(select(m.Claim)).all()

@pytest.mark.parametrize('content,finish', [('{"claims":[]}', 'stop'),('{broken','stop'),('  ','stop'),('{"claims":[]}','length')])
async def test_json_provider_validation(monkeypatch,content,finish):
    monkeypatch.setattr(ai.settings,'openai_api_key','fixture-key')
    monkeypatch.setattr(ai.settings,'llm_protocol','json')
    response=SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,message=SimpleNamespace(content=content))],usage=SimpleNamespace(total_tokens=10))
    create=AsyncMock(return_value=response)
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)),close=AsyncMock())
    monkeypatch.setattr(ai,'AsyncOpenAI',lambda **kwargs:client)
    if content=='{"claims":[]}' and finish=='stop':
        assert (await ai.structured(Extraction,'fixture JSON',{})).claims==[]
    else:
        with pytest.raises(ai.ProviderFailure): await ai.structured(Extraction,'fixture JSON',{})
    client.close.assert_awaited_once()

async def test_vendor_error_redacted(monkeypatch):
    import httpx2
    from openai import AuthenticationError
    secret='fixture-secret-do-not-log'
    exc=AuthenticationError(secret,response=httpx2.Response(401,request=httpx2.Request('POST','https://api.deepseek.com/chat/completions')),body={'error':secret})
    monkeypatch.setattr(ai.settings,'openai_api_key','fixture-key')
    monkeypatch.setattr(ai.settings,'llm_protocol','json')
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=exc))),close=AsyncMock())
    monkeypatch.setattr(ai,'AsyncOpenAI',lambda **kwargs:client)
    with pytest.raises(ai.ProviderFailure) as failure:
        await ai.structured(Extraction,'fixture',{})
    assert '401' in str(failure.value) and secret not in str(failure.value)

async def test_retry_failed_run(db,monkeypatch):
    snap=snapshot(db)
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(side_effect=ai.ProviderFailure('模型 API 请求超时')))
    with pytest.raises(ai.ProviderFailure): await extract_saved_snapshot(db,snap.id,{})
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[output()])))
    assert (await extract_saved_snapshot(db,snap.id,{}))['verified']==1
    assert len(db.scalars(select(m.ExtractionRun)).all())==1

async def test_duplicate_candidates(db,monkeypatch):
    snap=snapshot(db)
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[output(),output()])))
    assert (await extract_saved_snapshot(db,snap.id,{}))['total']==8

async def test_explicit_refresh_rechecks_existing_claim(db,monkeypatch):
    snap=snapshot(db)
    initial=output().model_copy(update={'claim_status':'unknown'})
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[initial])))
    await extract_saved_snapshot(db,snap.id,{})
    before=db.scalar(select(m.Claim).where(m.Claim.dimension=='Simulation')).id
    monkeypatch.setattr(ai,'extract_claims',AsyncMock(return_value=Extraction(claims=[output()])))
    await extract_saved_snapshot(db,snap.id,{},refresh=True)
    row=db.get(m.Claim,before)
    assert row.claim_status=='supported' and row.verification_status=='verified'
