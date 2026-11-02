import asyncio
import difflib
import logging
import time
from sqlalchemy import select
from . import models as m, ai
from .db import Session, utcnow
from .collector import fetch_webpage, fetch_github_repo, normalize_content, content_hash
from .extraction import extract_saved_snapshot
from .progress import extract_progress
from . import adapters

log = logging.getLogger(__name__)
execution_lock = asyncio.Lock()

def asdict(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns}

def meaningful_diff(old, new):
    return '\n'.join(difflib.unified_diff(normalize_content(old).splitlines(), normalize_content(new).splitlines(), fromfile='old', tofile='new', lineterm=''))

def create_snapshot(db, source, content, url):
    content = normalize_content(content)
    latest = db.scalar(select(m.Snapshot).where(m.Snapshot.source_id==source.id).order_by(m.Snapshot.sequence.desc()))
    digest = content_hash(content)
    if latest and latest.content_hash == digest:
        return latest, None, False
    row = m.Snapshot(source_id=source.id, sequence=latest.sequence+1 if latest else 1, content=content, content_hash=digest, source_url=url)
    db.add(row)
    db.commit()
    return row, latest, True

async def process_source(db, source, usage):
    try:
        if source.company_id and not source.product_id:
            if source.source_type=='wechat_official_account':
                text,url=await adapters.wechat_provider.fetch(source.url)
            else:
                text,url=await adapters.collect(source)
        elif source.source_type == 'github_repository':
            from urllib.parse import urlsplit
            p = urlsplit(source.url)
            if p.hostname != 'github.com':
                raise ValueError('GitHub 数据源仅支持 github.com/owner/repo')
            text = await fetch_github_repo(p.path.strip('/'))
            url = source.url
        else:
            text, url = await fetch_webpage(source.url)
        snapshot, previous, created = create_snapshot(db,source,text,url)
        source.last_status = 'success'
        source.error = None
        source.last_fetched_at = utcnow()
        db.commit()
    except Exception as exc:
        source.last_status = 'error'
        source.error = '采集失败：' + type(exc).__name__ + (': '+str(exc)[:250] if isinstance(exc, ValueError) else '')
        source.last_fetched_at = utcnow()
        db.commit()
        log.exception('Source %s failed', source.id)
        return source.error
    note = '建立基线完成，等待下一次采集' if created and not previous else ('内容未变化' if not created else '新快照已保存')
    if not ai.settings.openai_api_key:
        return note + '；未配置模型，AI 分析未执行'
    if source.company_id and not source.product_id:
        result=await extract_progress(db,snapshot.id,usage)
        return note+'；企业事件：'+str(result)
    if not previous and snapshot.sequence > 1:
        previous = db.scalar(select(m.Snapshot).where(m.Snapshot.source_id==source.id,m.Snapshot.sequence==snapshot.sequence-1))
    await extract_saved_snapshot(db,snapshot.id,usage)
    if previous and not db.scalar(select(m.ChangeEvent).where(m.ChangeEvent.new_snapshot_id==snapshot.id)):
        diff = meaningful_diff(previous.content,snapshot.content)
        if diff:
            change = await ai.classify_change(previous,snapshot,diff,usage)
            if ((change.old_evidence and change.old_evidence not in previous.content) or (change.new_evidence and change.new_evidence not in snapshot.content) or not (change.old_evidence or change.new_evidence)):
                raise ValueError('变化证据未通过验证')
            event = m.ChangeEvent(product_id=source.product_id,old_snapshot_id=previous.id,new_snapshot_id=snapshot.id,source_url=url,verification_status='verified',**change.model_dump())
            db.add(event)
            db.commit()
            for target in db.scalars(select(m.Product).where(m.Product.is_active==True,m.Product.id!=source.product_id)):
                current_claims = current_verified_claims(db,[target.id,source.product_id])
                result = await ai.analyze_impact(asdict(event),[asdict(c) for c in current_claims],usage)
                allowed = {c.id for c in current_claims}
                if not set(result.evidence_claim_ids)<=allowed:
                    raise ValueError('影响分析引用了无效证据')
                if not any(c.product_id==target.id for c in current_claims):
                    result.impact_level='unknown'
                    result.relationship='insufficient_evidence'
                    result.uncertainties.append('目标产品缺乏当前已验证证据')
                db.add(m.ImpactAnalysis(target_product=target.id,competitor_product=source.product_id,change_event_id=event.id,data=result.model_dump()))
                db.commit()
    return note

def current_verified_claims(db, product_ids=None, include_review=False):
    latest_ids = []
    for source in db.scalars(select(m.Source).where(m.Source.is_active==True)):
        snap = db.scalar(select(m.Snapshot).where(m.Snapshot.source_id==source.id).order_by(m.Snapshot.sequence.desc()))
        if snap:
            latest_ids.append(snap.id)
    query = select(m.Claim).where(m.Claim.snapshot_id.in_(latest_ids))
    if not include_review:
        query=query.where(m.Claim.verification_status=='verified')
    if product_ids:
        query = query.where(m.Claim.product_id.in_(product_ids))
    return db.scalars(query).all()

async def run_task(task_id):
    async with execution_lock:
        start = time.monotonic()
        with Session() as db:
            task = db.get(m.ResearchTask,task_id)
            task.status='running'
            db.commit()
            usage = {'requests':0,'total_tokens':0}
            errors = 0
            items=task.snapshot_ids or task.source_ids
            for i, sid in enumerate(items):
                try:
                    if task.snapshot_ids:
                        extractor=extract_progress if task.task_kind=='company' else extract_saved_snapshot
                        result=await asyncio.wait_for(extractor(db,sid,usage),timeout=180)
                        message='快照提取完成：'+str(result)
                    else:
                        source = db.get(m.Source,sid)
                        message = await asyncio.wait_for(process_source(db,source,usage),timeout=300)
                        errors += int(source.last_status=='error')
                except Exception as exc:
                    db.rollback()
                    message = ai.safe_error(exc)
                    log.warning('Research stage failed: %s',message)
                    errors += 1
                task.logs = [*task.logs, {('snapshot_id' if task.snapshot_ids else 'source_id'):sid,'message':message,'time':utcnow()}]
                task.progress = int((i+1)/len(items)*100)
                db.commit()
            usage['elapsed_seconds'] = round(time.monotonic()-start,3)
            task.usage=usage
            task.status='partial' if errors else 'completed'
            task.progress=100
            task.finished_at=utcnow()
            db.commit()
