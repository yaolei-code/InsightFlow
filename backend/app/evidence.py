"""Provenance validation. Conflicts are conservative review flags, not adjudication."""
from sqlalchemy import select
from . import models as m
from .ai import verify_claim
from .schemas import ClaimOutput

def validate_evidence(db, product_id, snapshot_id, source_url, claim):
    snapshot = db.get(m.Snapshot, snapshot_id)
    if not snapshot:
        raise ValueError('Snapshot 不存在')
    source = db.get(m.Source, snapshot.source_id)
    if not source or source.product_id != product_id:
        raise ValueError('Claim 产品与 Snapshot 来源不匹配')
    if source_url != snapshot.source_url:
        raise ValueError('Claim URL 与 Snapshot 保存的真实 URL 不匹配')
    return 'verified' if verify_claim(claim, snapshot) else 'unverified'

def mark_conflicts(db, product_id):
    # Compare only current versions. Historical changes must not conflict with themselves.
    rows = []
    for source in db.scalars(select(m.Source).where(m.Source.product_id==product_id,m.Source.is_active==True)):
        snap = db.scalar(select(m.Snapshot).where(m.Snapshot.source_id==source.id).order_by(m.Snapshot.sequence.desc()))
        if snap:
            rows.extend(db.scalars(select(m.Claim).where(m.Claim.snapshot_id==snap.id)).all())
    groups = {}
    for row in rows:
        if row.verification_status=='unverified':
            continue
        claim = ClaimOutput(**{k:getattr(row,k) for k in ClaimOutput.model_fields})
        row.verification_status = validate_evidence(db,row.product_id,row.snapshot_id,row.source_url,claim)
        if row.verification_status=='verified' and row.claim_status in ('supported','not_supported'):
            groups.setdefault((row.dimension,row.availability),[]).append(row)
    for group in groups.values():
        if {c.claim_status for c in group} == {'supported','not_supported'}:
            for row in group:
                row.verification_status='conflicting'
    db.flush()
