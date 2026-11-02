"""Database-first intelligence. Scores are prioritization, not truth probabilities."""
import hashlib,json,re
from urllib.parse import urlsplit
from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from . import models as m
from .db import utcnow
from .research import asdict

TECHNOLOGIES={'VLA':r'vla|vision.language.action|机器人.*模型|foundation model|helix|π0|pi0','World Model':r'世界模型|world model','Simulation':r'仿真|simulation','Data Collection':r'数据|dataset|teleop|遥操作','Model Training':r'训练|training|learning','Dexterous Manipulation':r'灵巧|dexter|manipulation|抓取','Real-world Deployment':r'部署|deployment|交付|试点|pilot|factory|工厂|量产','Robot Foundation Model':r'基础模型|foundation model|通用.*模型'}

def directions(event):
    text=' '.join(event.capability_tags)
    return [name for name,pattern in TECHNOLOGIES.items() if re.search(pattern,text,re.I)]

def quality(db):
    events=db.scalars(select(m.ProgressEvent)).all()
    assessments={r.event_id:r for r in db.scalars(select(m.EventAssessment))}
    members={r.event_id:r for r in db.scalars(select(m.ClusterMember))}
    clusters={r.fingerprint:r for r in db.scalars(select(m.EventCluster))}
    semantic_ids={r.id for r in clusters.values() if r.method=='rule_recall+llm'}
    evidence={r.id:r for r in db.scalars(select(m.EventEvidence))}
    for e in events:
        factors={'technical_progress':20 if e.event_type in ('model_release','technology_breakthrough','benchmark_result') else 10,'deployment_stage':{'pilot':20,'commercial_deployment':30,'scaled_production':35,'demonstration':10}.get(e.progress_stage,0),'potential_relevance':10 if e.event_type in ('open_source_release','customer_cooperation','product_release') else 5,'novelty':5 if e.occurred_at or e.published_at else 0,'evidence_strength':{'company_claim':0,'technical_artifact':10,'customer_confirmation':15,'independent_verification':20}.get(e.evidence_level,0)}
        factors.pop('novelty')
        known=e.occurred_at or e.published_at
        today=datetime.now(timezone.utc).date()
        factors['recency_proxy']=5 if known and (today-timedelta(days=29)).isoformat()<=known<=today.isoformat() else 0
        factors['novelty_proxy']=5 if sum(x.company_id==e.company_id and x.event_type==e.event_type and x.title==e.title for x in events)==1 else 0
        assessment=assessments.get(e.id)
        if not assessment:assessment=m.EventAssessment(event_id=e.id,review_status='pending');db.add(assessment)
        assessment.score=min(100,sum(factors.values()));assessment.factors=factors;assessment.updated_at=utcnow()
        date=e.occurred_at or e.published_at
        # Never merge merely similar headlines or unknown-date recurrences.
        quote=' '.join(evidence[x].evidence_text for x in e.evidence_ids if x in evidence)
        signature=[e.company_id,e.project_id,e.event_type,date,re.sub(r'\W+','',e.title).lower(),None if date else hashlib.sha256(quote.encode()).hexdigest() or e.id]
        if not date and not quote:signature.append(e.id)
        fingerprint=hashlib.sha256(json.dumps(signature,ensure_ascii=False).encode()).hexdigest()
        cluster=clusters.get(fingerprint)
        if not cluster:
            cluster=m.EventCluster(fingerprint=fingerprint,method='conservative_rule',reason='同企业/项目/类型、同日期及规范化标题；日期未知时还需相同引文')
            db.add(cluster);db.flush();clusters[fingerprint]=cluster
        member=members.get(e.id)
        if member:
            if member.cluster_id not in semantic_ids:member.cluster_id=cluster.id
        else:db.add(m.ClusterMember(event_id=e.id,cluster_id=cluster.id))
    db.commit()

def records(db,days=0,company_id=None,technology=None,level=None,followed=False,sort='importance',deduplicate=True):
    # Batch joins/maps, no per-card queries.
    events=db.scalars(select(m.ProgressEvent)).all()
    assessments={r.event_id:r for r in db.scalars(select(m.EventAssessment))}
    members={r.event_id:r.cluster_id for r in db.scalars(select(m.ClusterMember))}
    companies={r.id:r for r in db.scalars(select(m.Company))}
    evidence_map={r.id:r for r in db.scalars(select(m.EventEvidence))}
    follows=db.scalars(select(m.UserFollow).where(m.UserFollow.user_id=='local')).all()
    company_follows={int(f.target_key) for f in follows if f.target_type=='company'}
    tech_follows={f.target_key for f in follows if f.target_type=='technology'}
    today=datetime.now(timezone.utc).date();start=today-timedelta(days=max(days-1,0))
    output=[]
    for e in events:
        date=e.occurred_at or e.published_at
        if days and (not date or not start.isoformat()<=date[:10]<=today.isoformat()):continue
        if company_id and e.company_id!=company_id:continue
        tech=directions(e)
        if technology and technology not in tech and not any(technology.casefold() in t.casefold() for t in e.capability_tags):continue
        if level and e.evidence_level!=level:continue
        matches=e.company_id in company_follows or bool(set(tech)&tech_follows)
        if followed and not matches:continue
        a=assessments.get(e.id);score=a.score if a else 0
        urls=list(dict.fromkeys(evidence_map[i].source_url for i in e.evidence_ids if i in evidence_map))
        output.append({**asdict(e),'source_urls':urls,'source_domains':list(dict.fromkeys(urlsplit(u).hostname for u in urls)),'company_name':companies[e.company_id].name,'directions':tech,'importance':min(100,score+(10 if matches else 0)),'importance_factors':{**(a.factors if a else {}),'follow_relevance':10 if matches else 0},'review_status':a.review_status if a else 'pending','reviewed_at':a.reviewed_at if a else None,'cluster_id':members.get(e.id),'member_ids':[e.id],'evidence_levels':[e.evidence_level]})
    if deduplicate:
        grouped={}
        for row in output:
            key=row['cluster_id'] or 'event-'+str(row['id'])
            if key not in grouped:grouped[key]=row
            else:
                base=grouped[key];base['member_ids']+=row['member_ids'];base['evidence_ids']=list(dict.fromkeys(base['evidence_ids']+row['evidence_ids']));base['evidence_levels']=list(dict.fromkeys(base['evidence_levels']+row['evidence_levels']))
                base['source_urls']=list(dict.fromkeys(base['source_urls']+row['source_urls']));base['source_domains']=list(dict.fromkeys(base['source_domains']+row['source_domains']))
        output=list(grouped.values())
    output.sort(key=lambda e:(e['importance'] if sort=='importance' else 0,e['occurred_at'] or e['published_at'] or ''),reverse=True)
    return output

def detail(db,id):
    row=db.get(m.ProgressEvent,id)
    if not row:raise ValueError('事件不存在')
    match=next((x for x in records(db) if id in x['member_ids']),None)
    evidences=db.scalars(select(m.EventEvidence).where(m.EventEvidence.id.in_(match['evidence_ids']))).all()
    snapshots={r.id:r for r in db.scalars(select(m.Snapshot).where(m.Snapshot.id.in_([e.snapshot_id for e in evidences])))}
    sources={r.id:r for r in db.scalars(select(m.Source).where(m.Source.id.in_([s.source_id for s in snapshots.values()])))}
    match['evidence']=[{**asdict(e),'source_type':sources[snapshots[e.snapshot_id].source_id].source_type,'published_at':snapshots[e.snapshot_id].published_at,'collected_at':snapshots[e.snapshot_id].created_at,'verification_status':'verified' if e.evidence_text in snapshots[e.snapshot_id].content else 'unverified'} for e in evidences]
    match['uncertainties']=['原文匹配不等于独立验证；模型提取的阶段仍需审阅。']
    if not row.occurred_at:match['uncertainties'].append('实际事件日期未知。')
    if not any(e.evidence_level in ('customer_confirmation','independent_verification') for e in evidences):match['uncertainties'].append('尚未保存客户确认或第三方独立验证。')
    return match

def report(db,title,rows,scope,gaps=None):
    lines=[f'# {title}','## Executive Summary',f'本次汇编 {len(rows)} 个保守去重事件组。高重要性不是高可信度。','## Research Scope',scope,'## Company Progress']
    for e in rows:
        lines.append(f"### {e['company_name']} · {e['title']}\n{e['description']}\n日期：{e['occurred_at'] or e['published_at'] or 'unknown'}；阶段：{e['progress_stage']}；证据：{', '.join(e['evidence_levels'])}；审核：{e['review_status']}；重要性：{e['importance']}")
    if not rows:lines.append('当前数据库没有符合条件的新增事件，不代表行业没有进展。')
    for heading,filtered in [('新模型与产品',[e for e in rows if e['event_type'] in ('model_release','product_release','open_source_release')]),('技术成果',[e for e in rows if e['event_type'] in ('technology_breakthrough','benchmark_result')]),('客户试点与商业化',[e for e in rows if e['progress_stage'] in ('pilot','commercial_deployment','scaled_production')]),('值得进一步验证的声明',[e for e in rows if e['review_status']!='reviewed'])]:
        lines+=['## '+heading,'\n'.join(f"- {e['company_name']}：{e['title']}（证据 {e['evidence_ids']}）" for e in filtered) or '当前范围没有匹配的已保存记录。']
    lines+=['## Technology Analysis','按已保存技术标签归类，不作领先排名。','## Deployment Analysis','演示、试点、商业部署及规划分别标识；合作不等于交付。','## Competitive Comparison','不同公司产品与应用场景可能不可直接比较。','## Evidence & Sources']
    ids=list(dict.fromkeys(i for e in rows for i in e['evidence_ids']))
    evidence=db.scalars(select(m.EventEvidence).where(m.EventEvidence.id.in_(ids))).all()
    snapshots={s.id:s for s in db.scalars(select(m.Snapshot).where(m.Snapshot.id.in_([e.snapshot_id for e in evidence])))}
    for e in evidence:
        s=snapshots[e.snapshot_id];lines.append(f'[E{e.id}] {e.source_url} | published={s.published_at or "unknown"} | collected={s.created_at} | Snapshot {s.id}\n> {e.evidence_text}')
    lines+=['## Information Gaps','\n'.join(gaps or ['企业自述需补充客户确认；未知时间不作为最新新闻。']),'## Recommended Follow-up','跟踪项目开放状态、客户发布与实际交付证据。']
    row=m.ResearchReport(title=title,markdown='\n\n'.join(lines),evidence_claim_ids=[]);db.add(row);db.commit();return row
