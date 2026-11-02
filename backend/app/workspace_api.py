import asyncio,json
from datetime import datetime,timezone,timedelta
from typing import Literal
from pydantic import Field
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from . import models as m,ai
from .db import get_db,Session as DBSession,utcnow
from .schemas import Strict
from .research import asdict,execution_lock
from .intelligence_service import records,quality,detail,report,TECHNOLOGIES

router=APIRouter(prefix='/api/workspace',tags=['Intelligence Workspace'])
DB=Depends(get_db)
class FollowInput(Strict):
    target_type:Literal['company','technology']
    target_key:str=Field(min_length=1,max_length=200)
class ResearchInput(Strict):
    query:str=Field(min_length=2,max_length=1000)
    days:int=Field(default=30,ge=0,le=365)
    company_id:int|None=None
    technology:str|None=None
    allow_search:bool=True
class Decision(Strict):
    sufficient:bool
    plan_summary:str
    search_query:str
    gaps:list[str]
class Scope(Strict):
    company_ids:list[int]
    technology:str|None
    event_types:list[Literal['technology_breakthrough','model_release','product_release','robot_demo','benchmark_result','open_source_release','pilot_deployment','commercial_deployment','customer_cooperation','funding','mass_production','other']]=Field(default_factory=list)
    progress_stages:list[Literal['research','prototype','demonstration','pilot','commercial_deployment','scaled_production','unknown']]=Field(default_factory=list)
class ReviewInput(Strict):
    status:Literal['pending','reviewed','questionable']

@router.get('/events')
def events(days:int=Query(7,ge=0,le=365),company_id:int|None=None,technology:str|None=None,level:str|None=None,followed:bool=False,sort:Literal['importance','date']='importance',offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=500),db:Session=DB):
    rows=records(db,days,company_id,technology,level,followed,sort)
    return {'total':len(rows),'items':rows[offset:offset+limit]}

@router.get('/events/{id}')
def event(id:int,db:Session=DB):return detail(db,id)

@router.patch('/events/{id}/review')
def review(id:int,body:ReviewInput,db:Session=DB):
    row=db.get(m.EventAssessment,id)
    if not row:raise HTTPException(404,'事件评估不存在，请先计算质量')
    row.review_status=body.status;row.reviewed_at=utcnow();db.commit();return {'event_id':id,'status':row.review_status,'reviewed_at':row.reviewed_at}

@router.get('/quality')
def stats(db:Session=DB):
    rows=records(db, deduplicate=False);groups=records(db)
    return {'extracted_events':len(rows),'evidence_matched_events':sum(e['verification_status']=='verified' for e in rows),'awaiting_review':sum(e['review_status']=='pending' for e in rows),'event_groups':len(groups),'duplicate_or_related_records':len(rows)-len(groups),'third_party_supported_groups':sum(any(l in ('customer_confirmation','independent_verification') for l in e['evidence_levels']) for e in groups),'important_groups':sum(e['importance']>=50 for e in groups)}

@router.post('/quality/recompute')
def recompute(db:Session=DB):quality(db);return stats(db)

@router.post('/quality/semantic-recompute')
async def semantic_recompute(db:Session=DB):
    from .semantic_clusters import semantic_recompute as recompute_pairs
    return await recompute_pairs(db)

@router.get('/follows')
def follows(db:Session=DB):return [asdict(r) for r in db.scalars(select(m.UserFollow).where(m.UserFollow.user_id=='local'))]

@router.post('/follows',status_code=201)
def follow(body:FollowInput,db:Session=DB):
    if body.target_type=='company' and (not body.target_key.isdigit() or not db.get(m.Company,int(body.target_key))):raise HTTPException(400,'企业不存在')
    if body.target_type=='technology' and body.target_key not in TECHNOLOGIES:raise HTTPException(400,'技术方向不存在')
    row=db.scalar(select(m.UserFollow).where(m.UserFollow.user_id=='local',m.UserFollow.target_type==body.target_type,m.UserFollow.target_key==body.target_key))
    if not row:row=m.UserFollow(**body.model_dump());db.add(row);db.commit()
    return asdict(row)

@router.delete('/follows/{id}')
def unfollow(id:int,db:Session=DB):
    row=db.get(m.UserFollow,id)
    if row:db.delete(row);db.commit()
    return {'status':'removed'}

@router.post('/digest',status_code=201)
def digest(days:int=Query(7,ge=1,le=365),followed:bool=True,db:Session=DB):
    rows=records(db,days=days,followed=followed)
    return asdict(report(db,'关注对象行业简报',rows,f'最近{days}个UTC日期；按事件日期优先、资料日期其次；仅关注对象={followed}。'))

@router.get('/technologies')
def technologies():return list(TECHNOLOGIES)

async def run_research(id):
    async with execution_lock:
        with DBSession() as db:
            session=db.get(m.ResearchSession,id);session.status='running';db.commit();usage={}
            def trace(tool,summary):
                session.trace=[*session.trace,{'tool':tool,'summary':summary,'at':utcnow()}];db.commit()
            try:
                params=session.parameters
                known=[{'id':c.id,'name':c.name} for c in db.scalars(select(m.Company))]
                scope=await ai.structured(Scope,'Extract company scope, one technology, and optional event types/development stages explicitly requested in question. Use ONLY supplied IDs/technologies and schema enums. Empty lists/null mean no restriction. Do not infer a company not named. For broad progress queries do not restrict event types/stages. QUESTION: '+session.user_query+'\nCOMPANIES: '+json.dumps(known,ensure_ascii=False)+'\nTECHNOLOGIES: '+json.dumps(list(TECHNOLOGIES)),usage)
                if scope.technology not in TECHNOLOGIES:scope.technology=None
                if not params.get('technology'):params={**params,'technology':scope.technology}
                allowed={c['id'] for c in known}
                if not set(scope.company_ids)<=allowed:raise ValueError('模型引用未知企业')
                trace('understand_scope',json.dumps({'company_ids':scope.company_ids,'technology':params.get('technology'),'days':params['days']},ensure_ascii=False))
                rows=records(db,params['days'],params.get('company_id'),params.get('technology'))
                if scope.company_ids and not params.get('company_id'):rows=[r for r in rows if r['company_id'] in scope.company_ids]
                if scope.event_types:rows=[r for r in rows if r['event_type'] in scope.event_types]
                if scope.progress_stages:rows=[r for r in rows if r['progress_stage'] in scope.progress_stages]
                trace('query_company_history',f'按日期/企业/技术筛选，找到{len(rows)}个事件组。')
                payload=[{k:e[k] for k in ('id','title','description','company_name','evidence_levels','occurred_at','published_at')} for e in rows[:30]]
                today=datetime.now(timezone.utc).date()
                decision=await ai.structured(Decision,'Current UTC date: '+today.isoformat()+'. Assess evidence sufficiency for this research question. Do not invent dates or assert new facts. Return a short action plan, specific gaps, and at most one focused search query if existing records are stale/inadequate. No hidden reasoning. QUESTION: '+session.user_query+'\nSCOPE: '+json.dumps(params)+'\nSAVED EVIDENCE: '+json.dumps(payload,ensure_ascii=False),usage)
                trace('evidence_assessment',decision.plan_summary+'；缺口：'+'；'.join(decision.gaps))
                if not decision.sufficient and params['allow_search'] and decision.search_query:
                    from .discovery import discover_search
                    from .search import SearchInput
                    from .ingestion import ingest_candidate,article_link
                    before=db.scalar(select(func.max(m.SourceCandidate.id))) or 0
                    try:
                        result=await discover_search(db,SearchInput(query=decision.search_query,keywords=[],company_id=params.get('company_id'),start_date=today-timedelta(days=max(params['days']-1,0)) if params['days'] else None,end_date=today if params['days'] else None))
                        trace('search_web',json.dumps(result,ensure_ascii=False))
                        candidates=db.scalars(select(m.SourceCandidate).where(m.SourceCandidate.id.in_(result.get('candidate_ids',[]))).order_by(m.SourceCandidate.relevance_score.desc())).all()
                        for candidate in [c for c in candidates if article_link(c)][:3]:
                            result=await asyncio.wait_for(ingest_candidate(db,candidate,usage),timeout=100)
                            trace('fetch_extract_verify',json.dumps(result,ensure_ascii=False))
                    except Exception as exc:trace('search_error',ai.safe_error(exc))
                    rows=records(db,params['days'],params.get('company_id'),params.get('technology'))
                quality(db)
                rows=records(db,params['days'],params.get('company_id'),params.get('technology'))
                if scope.company_ids and not params.get('company_id'):rows=[r for r in rows if r['company_id'] in scope.company_ids]
                if scope.event_types:rows=[r for r in rows if r['event_type'] in scope.event_types]
                if scope.progress_stages:rows=[r for r in rows if r['progress_stage'] in scope.progress_stages]
                saved=report(db,session.user_query,rows,'用户范围：'+json.dumps({**params,'derived_scope':scope.model_dump()},ensure_ascii=False),decision.gaps)
                session.report_id=saved.id;session.summary=f'已汇编{len(rows)}个事件组；结论仅限已保存证据。';session.stop_reason='完成受控数据库优先研究；最多一次搜索、三篇正文补充。';session.status='completed'
                trace('create_research_report',f'报告 #{saved.id}；{len(rows)}个事件组。')
            except Exception as exc:
                db.rollback();session=db.get(m.ResearchSession,id);session.status='failed';session.stop_reason=ai.safe_error(exc)
            session.usage=usage;session.finished_at=utcnow();db.commit()

async def bounded_research(id):
    try:await asyncio.wait_for(run_research(id),timeout=300)
    except asyncio.TimeoutError:
        with DBSession() as db:
            row=db.get(m.ResearchSession,id);row.status='failed';row.stop_reason='等待或执行超过300秒预算，请重试';row.finished_at=utcnow();db.commit()

@router.post('/research',status_code=202)
async def research(body:ResearchInput,db:Session=DB):
    if not ai.settings.openai_api_key:raise HTTPException(409,'未配置模型，无法启动研究')
    if body.company_id and not db.get(m.Company,body.company_id):raise HTTPException(400,'企业不存在')
    if db.scalar(select(m.ResearchSession).where(m.ResearchSession.status.in_(['queued','running']))):raise HTTPException(409,'已有首页研究执行中')
    from .main import workers
    row=m.ResearchSession(user_query=body.query,parameters=body.model_dump(exclude={'query'}));db.add(row);db.commit()
    task=asyncio.create_task(bounded_research(row.id));workers.add(task);task.add_done_callback(workers.discard);return asdict(row)

@router.get('/research')
def sessions(db:Session=DB):return [asdict(s) for s in db.scalars(select(m.ResearchSession).order_by(m.ResearchSession.id.desc()).limit(20))]

@router.get('/research/{id}')
def session(id:int,db:Session=DB):
    row=db.get(m.ResearchSession,id)
    if not row:raise HTTPException(404,'研究任务不存在')
    return asdict(row)
