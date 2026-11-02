from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,or_
from sqlalchemy.orm import Session
from .db import get_db,utcnow
from . import models as m, adapters
from .company_schemas import CompanyInput,CompanyPatch,CompanySourceInput,CompanySourcePatch,ProjectInput
from .collector import normalize_url
from .research import asdict
from .config import settings

router=APIRouter(prefix='/api',tags=['Company Intelligence'])
DB=Depends(get_db)

def require(db,model,id):
    row=db.get(model,id)
    if not row:raise HTTPException(404,'记录不存在')
    return row

@router.get('/companies')
def companies(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:Session=DB):
    return [asdict(c) for c in db.scalars(select(m.Company).order_by(m.Company.id).offset(offset).limit(limit))]

@router.post('/companies',status_code=201)
def create_company(body:CompanyInput,db:Session=DB):
    if db.scalar(select(m.Company).where(m.Company.name==body.name)):
        raise HTTPException(409,'企业已存在')
    data=body.model_dump()
    if data['official_url']:data['official_url']=normalize_url(data['official_url'])
    row=m.Company(**data);db.add(row);db.commit();return asdict(row)

@router.patch('/companies/{id}')
def patch_company(id:int,body:CompanyPatch,db:Session=DB):
    row=require(db,m.Company,id)
    for key,value in body.model_dump(exclude_none=True,exclude_unset=True).items():
        setattr(row,key,normalize_url(value) if key=='official_url' and value else value)
    if not row.is_active:
        for source in db.scalars(select(m.Source).where(m.Source.company_id==id)):
            source.is_active=False
    db.commit();return asdict(row)

@router.get('/companies/{id}')
def profile(id:int,db:Session=DB):
    row=require(db,m.Company,id)
    return {**asdict(row),'products':[asdict(x) for x in db.scalars(select(m.Product).where(m.Product.company_id==id))], 'projects':[asdict(x) for x in db.scalars(select(m.Project).where(m.Project.company_id==id))], 'sources':[asdict(x) for x in db.scalars(select(m.Source).where(m.Source.company_id==id))]}

@router.post('/projects',status_code=201)
def project(body:ProjectInput,db:Session=DB):
    require(db,m.Company,body.company_id)
    if db.scalar(select(m.Project).where(m.Project.company_id==body.company_id,m.Project.name==body.name)):
        raise HTTPException(409,'项目已存在')
    row=m.Project(**body.model_dump());db.add(row);db.commit();return asdict(row)

@router.post('/company-sources',status_code=201)
def add_source(body:CompanySourceInput,db:Session=DB):
    company=require(db,m.Company,body.company_id)
    if not company.is_active:raise HTTPException(400,'企业已停用')
    if body.project_id and require(db,m.Project,body.project_id).company_id!=body.company_id:
        raise HTTPException(400,'项目不属于该企业')
    data=body.model_dump();data['url']=normalize_url(body.url)
    existing=db.scalar(select(m.Source).where(m.Source.company_id==body.company_id,m.Source.url==data['url']))
    if existing:raise HTTPException(409,'该企业已配置此来源')
    row=m.Source(**data);db.add(row);db.commit();return asdict(row)

@router.get('/wechat/search')
async def search_wechat(q:str=Query(min_length=1,max_length=200)):
    try:return await adapters.wechat_provider.search(q)
    except Exception as exc:
        from .ai import safe_error
        raise HTTPException(400,'公众号搜索不可用：'+(str(exc) if isinstance(exc,ValueError) else safe_error(exc))) from None

@router.patch('/company-sources/{id}')
def patch_source(id:int,body:CompanySourcePatch,db:Session=DB):
    row=require(db,m.Source,id)
    if not row.company_id:raise HTTPException(400,'不是企业数据源')
    if db.scalar(select(m.ResearchTask).where(m.ResearchTask.status.in_(['queued','running']))):raise HTTPException(409,'任务执行期间不能修改来源')
    for key,value in body.model_dump(exclude_unset=True,exclude_none=True).items():
        setattr(row,key,normalize_url(value) if key=='url' else value)
    db.commit();return asdict(row)

@router.post('/snapshots/{id}/progress',status_code=202)
async def run_progress(id:int,db:Session=DB):
    from .main import enqueue
    snapshot=require(db,m.Snapshot,id)
    source=require(db,m.Source,snapshot.source_id)
    if not source.company_id:raise HTTPException(400,'来源未关联企业')
    if not settings.openai_api_key:raise HTTPException(409,'未配置模型')
    return enqueue([source.id],db,[id],task_kind='company')

@router.get('/snapshots/{id}/progress-run')
def progress_run(id:int,db:Session=DB):
    require(db,m.Snapshot,id)
    row=db.scalar(select(m.ProgressRun).where(m.ProgressRun.snapshot_id==id))
    return asdict(row) if row else {'status':'not_started'}

@router.get('/progress-events')
def events(company_id:int|None=None,tag:str|None=None,stage:str|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:Session=DB):
    query=select(m.ProgressEvent)
    if company_id:query=query.where(m.ProgressEvent.company_id==company_id)
    if stage:query=query.where(m.ProgressEvent.progress_stage==stage)
    query=query.order_by(m.ProgressEvent.published_at.desc(),m.ProgressEvent.created_at.desc())
    rows=db.scalars(query).all()
    if tag:rows=[r for r in rows if any(tag.casefold() in t.casefold() for t in r.capability_tags)]
    return [asdict(x) for x in rows[offset:offset+limit]]

@router.get('/event-evidence/{id}')
def evidence(id:int,db:Session=DB):
    return asdict(require(db,m.EventEvidence,id))

@router.post('/industry-reports',status_code=201)
def weekly_report(db:Session=DB):
    now=datetime.now(timezone.utc);start=(now-timedelta(days=6)).date().isoformat();end=now.date().isoformat()
    rows=db.scalars(select(m.ProgressEvent).where(m.ProgressEvent.published_at>=start,m.ProgressEvent.published_at<=end).order_by(m.ProgressEvent.published_at.desc())).all()
    unknown=db.scalars(select(m.ProgressEvent).where(m.ProgressEvent.published_at==None)).all()
    lines=[f'# 最近一周具身智能行业进展\n\n窗口：{start} 至 {end}（UTC，按来源发布时间）',f'已保存并验证原文的事件 {len(rows)} 条。企业自述不等同独立证实；未知日期事件 {len(unknown)} 条不计入本周。']
    for row in rows:
        company=db.get(m.Company,row.company_id)
        lines.append(f'## {company.name} · {row.title}\n\n发布时间：{row.published_at}；事件时间：{row.occurred_at or "unknown"}；阶段：{row.progress_stage}；证据等级：{row.evidence_level}\n\n{row.description}')
        for eid in row.evidence_ids:
            e=db.get(m.EventEvidence,eid)
            lines.append(f'[E{e.id}] {e.source_url} · Snapshot {e.snapshot_id}\n\n> {e.evidence_text}')
    if not rows:lines.append('当前数据库没有本周已知发布日期的事件；这不代表行业没有进展。')
    row=m.ResearchReport(title=f'行业周报 {end}',markdown='\n\n'.join(lines),evidence_claim_ids=[])
    db.add(row);db.commit();return asdict(row)
