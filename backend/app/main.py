from contextlib import asynccontextmanager
import asyncio
import logging
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession
from . import models as m, schemas as s
from .db import Session, get_db, utcnow
from .collector import normalize_url
from .research import run_task, asdict, current_verified_claims
from .reports import generate_report
from .config import settings

workers = set()

@asynccontextmanager
async def lifespan(app):
    with Session() as db:
        for run in db.scalars(select(m.DiscoveryRun).where(m.DiscoveryRun.status.in_(['queued','running']))):
            run.status='interrupted';run.error='进程重启中断发现任务';run.finished_at=utcnow()
        for task in db.scalars(select(m.ResearchTask).where(m.ResearchTask.status.in_(['queued','running']))):
            task.status='interrupted'
            task.finished_at=utcnow()
            task.logs=[*task.logs,{'message':'进程重启中断；请重新提交任务'}]
        for run in db.scalars(select(m.ExtractionRun).where(m.ExtractionRun.status=='running')):
            run.status='failed'
            run.error='进程重启中断提取；请重新提交'
            run.finished_at=utcnow()
        for run in db.scalars(select(m.ProgressRun).where(m.ProgressRun.status=='running')):
            run.status='failed';run.error='进程重启中断；请重新提交';run.finished_at=utcnow()
        db.commit()
    yield
    for worker in workers:
        worker.cancel()
    await asyncio.gather(*workers,return_exceptions=True)

app = FastAPI(title='InsightFlow',version='0.1.0',lifespan=lifespan)
DB = Depends(get_db)

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(status_code=exc.status_code,content={'error':{'message':str(exc.detail)}})

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422,content={'error':{'message':'输入校验失败','fields':[{'field':'.'.join(map(str,e['loc'])),'message':e['msg']} for e in exc.errors()]}})

@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse(status_code=400,content={'error':{'message':str(exc)}})

@app.exception_handler(Exception)
async def server_error(request, exc):
    logging.exception('Unhandled request error')
    return JSONResponse(status_code=500,content={'error':{'message':'服务器处理失败，请查看本地日志'}})

def require(db, model, id):
    row=db.get(model,id)
    if not row:
        raise HTTPException(404,'记录不存在')
    return row

def page(db, model, offset=0, limit=50, product_id=None):
    query=select(model)
    if product_id is not None and hasattr(model,'product_id'):
        query=query.where(model.product_id==product_id)
    return [asdict(r) for r in db.scalars(query.order_by(model.id.desc()).offset(offset).limit(limit))]

@app.get('/api/health')
def health():
    return {'status':'ok','model_configured':bool(settings.openai_api_key),'model':settings.openai_model,'protocol':settings.llm_protocol}

@app.get('/api/dashboard')
def dashboard(db: DBSession=DB):
    sources=db.scalars(select(m.Source)).all()
    attempted=[x for x in sources if x.last_fetched_at]
    return {'products':db.scalar(select(func.count()).select_from(m.Product).where(m.Product.is_active==True)), 'sources':len(sources),'changes':db.scalar(select(func.count()).select_from(m.ChangeEvent)), 'claims':db.scalar(select(func.count()).select_from(m.Claim)), 'success_rate':round(sum(x.last_status=='success' for x in attempted)/len(attempted)*100,1) if attempted else None,'errors':[asdict(x) for x in sources if x.last_status=='error'],'tasks':page(db,m.ResearchTask,limit=5)}

@app.get('/api/products')
def products(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:DBSession=DB):
    return page(db,m.Product,offset,limit)

@app.post('/api/products',status_code=201)
def add_product(body:s.ProductInput,db:DBSession=DB):
    data=body.model_dump()
    if data['official_url']:
        data['official_url']=normalize_url(data['official_url'])
    row=m.Product(**data)
    db.add(row); db.commit()
    return asdict(row)

@app.get('/api/products/{id}')
def product(id:int,db:DBSession=DB):
    return asdict(require(db,m.Product,id))

@app.patch('/api/products/{id}')
def patch_product(id:int,body:s.ProductPatch,db:DBSession=DB):
    row=require(db,m.Product,id)
    for key,value in body.model_dump(exclude_unset=True,exclude_none=True).items():
        setattr(row,key,normalize_url(value) if key=='official_url' and value else value)
    db.commit()
    return asdict(row)

@app.delete('/api/products/{id}')
def delete_product(id:int,db:DBSession=DB):
    row=require(db,m.Product,id); row.is_active=False
    for source in db.scalars(select(m.Source).where(m.Source.product_id==id)):
        source.is_active=False
    db.commit()
    return {'status':'disabled'}

@app.get('/api/sources')
def sources(product_id:int|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:DBSession=DB):
    return page(db,m.Source,offset,limit,product_id)

@app.post('/api/sources',status_code=201)
def add_source(body:s.SourceInput,db:DBSession=DB):
    require(db,m.Product,body.product_id)
    row=m.Source(**{**body.model_dump(),'url':normalize_url(body.url)})
    db.add(row); db.commit()
    return asdict(row)

@app.patch('/api/sources/{id}')
def patch_source(id:int,body:s.SourcePatch,db:DBSession=DB):
    row=require(db,m.Source,id)
    if db.scalar(select(m.ResearchTask).where(m.ResearchTask.status.in_(['queued','running']))):
        raise HTTPException(409,'研究执行期间暂不能修改来源')
    for key,value in body.model_dump(exclude_unset=True,exclude_none=True).items():
        setattr(row,key,normalize_url(value) if key=='url' else value)
    db.commit()
    return asdict(row)

def enqueue(ids,db,snapshot_ids=None,task_kind='product'):
    if db.scalar(select(m.ResearchTask).where(m.ResearchTask.status.in_(['queued','running']))):
        raise HTTPException(409,'已有研究任务执行中')
    sources=db.scalars(select(m.Source).where(m.Source.is_active==True)).all()
    active={x.id for x in sources}
    ids=list(dict.fromkeys(ids or sorted(active)))
    if not ids or not set(ids)<=active:
        raise HTTPException(400,'请选择有效且启用的数据源')
    task=m.ResearchTask(source_ids=ids,snapshot_ids=snapshot_ids or [],task_kind=task_kind)
    db.add(task); db.commit()
    worker=asyncio.create_task(run_task(task.id)); workers.add(worker)
    worker.add_done_callback(workers.discard)
    return asdict(task)

@app.post('/api/research',status_code=202)
async def research(body:s.ResearchInput,db:DBSession=DB):
    return enqueue(body.source_ids,db)

@app.post('/api/sources/{id}/fetch',status_code=202)
async def fetch(id:int,db:DBSession=DB):
    require(db,m.Source,id)
    return enqueue([id],db)

@app.get('/api/sources/{id}/snapshots')
def snapshots(id:int,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db:DBSession=DB):
    require(db,m.Source,id)
    return [asdict(x) for x in db.scalars(select(m.Snapshot).where(m.Snapshot.source_id==id).order_by(m.Snapshot.sequence.desc()).offset(offset).limit(limit))]

@app.get('/api/snapshots/{id}')
def snapshot(id:int,db:DBSession=DB):
    return asdict(require(db,m.Snapshot,id))

@app.post('/api/snapshots/{id}/extract',status_code=202)
async def extract_snapshot(id:int,db:DBSession=DB):
    snapshot=require(db,m.Snapshot,id)
    if not settings.openai_api_key:
        raise HTTPException(409,'未配置模型，请在本地 .env 配置 API Key')
    source=require(db,m.Source,snapshot.source_id)
    return enqueue([snapshot.source_id],db,[id],task_kind='company' if not source.product_id else 'product')

@app.get('/api/snapshots/{id}/extraction')
def extraction_status(id:int,db:DBSession=DB):
    require(db,m.Snapshot,id)
    run=db.scalar(select(m.ExtractionRun).where(m.ExtractionRun.snapshot_id==id))
    return asdict(run) if run else {'snapshot_id':id,'status':'not_started'}

@app.get('/api/claims')
def claims(product_id:int|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:DBSession=DB):
    return page(db,m.Claim,offset,limit,product_id)

@app.get('/api/changes')
def changes(product_id:int|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:DBSession=DB):
    return page(db,m.ChangeEvent,offset,limit,product_id)

@app.get('/api/impacts')
def impacts(db:DBSession=DB):
    return page(db,m.ImpactAnalysis)

@app.get('/api/tasks')
def tasks(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:DBSession=DB):
    return page(db,m.ResearchTask,offset,limit)

@app.get('/api/tasks/{id}')
def task(id:int,db:DBSession=DB):
    return asdict(require(db,m.ResearchTask,id))

@app.post('/api/comparisons',status_code=201)
def comparison(body:s.ComparisonInput,db:DBSession=DB):
    for pid in body.product_ids:
        require(db,m.Product,pid)
    row=m.Comparison(**body.model_dump()); db.add(row); db.commit()
    return asdict(row)

@app.get('/api/comparisons')
def comparisons(db:DBSession=DB):
    claims=current_verified_claims(db,include_review=True)
    return {'saved':page(db,m.Comparison),'dimensions':s.DIMENSIONS,'claims':[asdict(c) for c in claims]}

@app.post('/api/reports',status_code=201)
def report(body:s.ReportInput,db:DBSession=DB):
    row=generate_report(db,body.title); db.add(row); db.commit()
    return asdict(row)

@app.get('/api/reports')
def reports(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db:DBSession=DB):
    return page(db,m.ResearchReport,offset,limit)

@app.get('/api/reports/{id}')
def report_detail(id:int,db:DBSession=DB):
    return asdict(require(db,m.ResearchReport,id))

from .company_api import router as company_router
app.include_router(company_router)
from .discovery_api import router as discovery_router
app.include_router(discovery_router)
