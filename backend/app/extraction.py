import time
from sqlalchemy import select
from . import models as m, ai
from .db import utcnow
from .schemas import Extraction, ClaimOutput, DIMENSIONS
from .evidence import validate_evidence, mark_conflicts

async def extract_saved_snapshot(db, snapshot_id, usage, refresh=False):
    snapshot = db.get(m.Snapshot,snapshot_id)
    if not snapshot:
        raise ValueError('Snapshot 不存在')
    source = db.get(m.Source,snapshot.source_id)
    run = db.scalar(select(m.ExtractionRun).where(m.ExtractionRun.snapshot_id==snapshot_id))
    if run and run.status=='completed' and not refresh:
        return {**run.counts,'reused':True}
    if not run:
        run=m.ExtractionRun(snapshot_id=snapshot_id,status='running')
        db.add(run)
    run.status='running'; run.error=None; run.finished_at=None
    db.commit()
    started=time.monotonic()
    try:
        # Validate even an injected/mock provider at this trust boundary.
        extracted=Extraction.model_validate(await ai.extract_claims(snapshot,usage))
        candidates=list(extracted.claims)
        seen_dimensions={c.dimension for c in candidates}
        for dimension in DIMENSIONS:
            if dimension not in seen_dimensions:
                candidates.append(ClaimOutput(dimension=dimension,claim_text='当前快照未提取到该维度的可验证证据，能力未知。',claim_status='unknown',availability='unknown',evidence_text=''))
        existing_rows={(c.dimension,c.claim_text):c for c in db.scalars(select(m.Claim).where(m.Claim.snapshot_id==snapshot_id))}
        existing=set(existing_rows)
        for candidate in candidates:
            if (candidate.dimension,candidate.claim_text) in existing and not refresh:
                continue
            state=validate_evidence(db,source.product_id,snapshot_id,snapshot.source_url,candidate)
            if not candidate.evidence_text.strip():
                candidate=candidate.model_copy(update={'claim_status':'unknown','availability':'unknown'})
            elif state!='verified':
                # Retain the failed candidate for review, never as an asserted fact.
                candidate=candidate.model_copy(update={'claim_status':'unknown','availability':'unknown'})
            prior=existing_rows.get((candidate.dimension,candidate.claim_text))
            if refresh and prior:
                for key,value in candidate.model_dump().items():setattr(prior,key,value)
                prior.verification_status=state
            else:
                db.add(m.Claim(product_id=source.product_id,snapshot_id=snapshot.id,source_url=snapshot.source_url,observed_at=snapshot.created_at,**candidate.model_dump(),verification_status=state))
            existing.add((candidate.dimension,candidate.claim_text))
        db.flush()
        mark_conflicts(db,source.product_id)
        rows=db.scalars(select(m.Claim).where(m.Claim.snapshot_id==snapshot_id)).all()
        counts={'total':len(rows),'verified':sum(c.verification_status=='verified' for c in rows),'unknown':sum(c.claim_status=='unknown' for c in rows),'conflicting':sum(c.verification_status=='conflicting' for c in rows),'unverified':sum(c.verification_status=='unverified' for c in rows)}
        run.status='completed';run.counts=counts;run.finished_at=utcnow()
        run.usage={**usage,'elapsed_seconds':round(time.monotonic()-started,3)}
        db.commit()
        return counts
    except Exception as exc:
        db.rollback()
        run=db.scalar(select(m.ExtractionRun).where(m.ExtractionRun.snapshot_id==snapshot_id))
        run.status='failed';run.error=ai.safe_error(exc);run.finished_at=utcnow();run.usage=dict(usage)
        db.commit()
        raise ai.ProviderFailure(run.error) from None
