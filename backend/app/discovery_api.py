import asyncio
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from typing import Literal
from .db import get_db
from . import models as m
from .schemas import Strict
from .search import SearchInput,SearchHit,KEYWORDS
from .discovery import canonical_url,save_candidate,execute_discovery
from .research import asdict
from .config import settings

router=APIRouter(prefix='/api',tags=['Industry Coverage'])
DB=Depends(get_db)
CandidateType=Literal['official_website','wechat_official_account','industry_media','github','arxiv','technical_blog','customer_announcement','government','video','other']

class SeedInput(Strict):
    name:str=Field(min_length=1,max_length=200)
    url:str
    company_id:int|None=None
    source_type:CandidateType='industry_media'

class ImportInput(Strict):
    title:str=Field(min_length=1,max_length=500)
    url:str
    company_id:int|None=None
    source_type:CandidateType='other'

class ReviewInput(Strict):
    review_status:Literal['approved','rejected']
    company_id:int|None=None
    source_type:CandidateType|None=None

class AliasInput(Strict):
    company_id:int
    alias:str=Field(min_length=2,max_length=100)

def require(db,model,id):
    row=db.get(model,id)
    if not row:raise HTTPException(404,'记录不存在')
    return row

def submit(db,kind,parameters):
    from .main import workers
    if db.scalar(select(m.DiscoveryRun).where(m.DiscoveryRun.status.in_(['queued','running']))):raise HTTPException(409,'已有发现任务执行中')
    row=m.DiscoveryRun(kind=kind,parameters=parameters);db.add(row);db.commit()
    task=asyncio.create_task(execute_discovery(row.id));workers.add(task);task.add_done_callback(workers.discard)
    return asdict(row)

@router.get('/coverage')
def coverage(db:Session=DB):
    counts={name:db.scalar(select(func.count()).select_from(model)) for name,model in [('seeds',m.DiscoverySeed),('candidates',m.SourceCandidate),('sources',m.Source),('snapshots',m.Snapshot),('events',m.ProgressEvent)]}
    return {**counts,'pending':db.scalar(select(func.count()).select_from(m.SourceCandidate).where(m.SourceCandidate.review_status=='pending')),'tavily_configured':bool(settings.tavily_api_key),'keywords':KEYWORDS,'warning':'此处统计仅代表已发现及已采集资料，不代表行业全貌。'}

@router.get('/discovery-seeds')
def seeds(db:Session=DB):return [asdict(x) for x in db.scalars(select(m.DiscoverySeed).order_by(m.DiscoverySeed.id))]

@router.post('/discovery-seeds',status_code=201)
def add_seed(body:SeedInput,db:Session=DB):
    if body.company_id:require(db,m.Company,body.company_id)
    url=canonical_url(body.url)
    if db.scalar(select(m.DiscoverySeed).where(m.DiscoverySeed.url==url)):raise HTTPException(409,'来源库已登记此 URL')
    row=m.DiscoverySeed(**{**body.model_dump(),'url':url});db.add(row);db.commit();return asdict(row)

@router.post('/discovery-seeds/{id}/discover',status_code=202)
async def discover(id:int,db:Session=DB):
    require(db,m.DiscoverySeed,id)
    return submit(db,'seed',{'seed_id':id})

@router.post('/discovery/search',status_code=202)
async def search(body:SearchInput,db:Session=DB):
    if body.company_id:require(db,m.Company,body.company_id)
    return submit(db,'search',body.model_dump(mode='json'))

@router.get('/discovery-runs')
def runs(limit:int=Query(30,ge=1,le=100),db:Session=DB):return [asdict(x) for x in db.scalars(select(m.DiscoveryRun).order_by(m.DiscoveryRun.id.desc()).limit(limit))]

@router.get('/discovery-runs/{id}')
def run(id:int,db:Session=DB):return asdict(require(db,m.DiscoveryRun,id))

@router.get('/source-candidates')
def candidates(review_status:Literal['pending','approved','rejected']|None=None,company_id:int|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:Session=DB):
    query=select(m.SourceCandidate)
    if review_status:query=query.where(m.SourceCandidate.review_status==review_status)
    if company_id:query=query.where(m.SourceCandidate.company_id==company_id)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    return {'total':total,'items':[asdict(x) for x in db.scalars(query.order_by(m.SourceCandidate.id.desc()).offset(offset).limit(limit))]}

@router.post('/source-candidates',status_code=201)
def import_candidate(body:ImportInput,db:Session=DB):
    if body.company_id:require(db,m.Company,body.company_id)
    row,created=save_candidate(db,SearchHit(title=body.title,url=body.url),'manual_import','用户提交公开 URL',body.company_id,body.source_type)
    db.commit();return {**asdict(row),'new':created}

@router.patch('/source-candidates/{id}/review')
def review(id:int,body:ReviewInput,db:Session=DB):
    row=require(db,m.SourceCandidate,id)
    if row.review_status!='pending':
        if row.review_status==body.review_status:return asdict(row)
        raise HTTPException(409,'已审核候选不可直接反转；请在正式来源管理中启停')
    cid=body.company_id or row.company_id
    if body.review_status=='approved':
        if not cid:raise HTTPException(400,'请人工确认所属企业，不能从摘要直接认定归属')
        company=require(db,m.Company,cid)
        if not company.is_active:raise HTTPException(400,'企业已停用')
        source=next((s for s in db.scalars(select(m.Source).where(m.Source.company_id==cid)) if canonical_url(s.url)==row.url),None)
        if not source:
            source=m.Source(company_id=cid,url=row.url,source_type=body.source_type or row.source_type,evidence_authority='company_claim')
            db.add(source);db.flush()
        row.company_id=cid;row.source_id=source.id
        if body.source_type:row.source_type=body.source_type
    row.review_status=body.review_status
    db.commit();return asdict(row)

@router.get('/company-aliases')
def aliases(db:Session=DB):return [asdict(x) for x in db.scalars(select(m.CompanyAlias))]

@router.post('/company-aliases',status_code=201)
def alias(body:AliasInput,db:Session=DB):
    require(db,m.Company,body.company_id)
    if db.scalar(select(m.CompanyAlias).where(m.CompanyAlias.alias==body.alias)):raise HTTPException(409,'别名已存在')
    row=m.CompanyAlias(**body.model_dump());db.add(row);db.commit();return asdict(row)
