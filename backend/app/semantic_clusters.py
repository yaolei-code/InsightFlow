"""Conservative rule recall + bounded model confirmation. Never deletes source events."""
from difflib import SequenceMatcher
from sqlalchemy import select
from pydantic import Field
from . import models as m,ai
from .schemas import Strict
from .intelligence_service import quality

class Pair(Strict):
    first:int
    second:int
    same_progress:bool
    shared_anchor:str
    reason:str
class Results(Strict):
    pairs:list[Pair]=Field(max_length=20)

async def semantic_recompute(db):
    quality(db)
    events=db.scalars(select(m.ProgressEvent)).all()
    members={r.event_id:r for r in db.scalars(select(m.ClusterMember))}
    candidates=[]
    for i,a in enumerate(events):
        for b in events[i+1:]:
            if a.company_id!=b.company_id or a.event_type!=b.event_type or members[a.id].cluster_id==members[b.id].cluster_id:continue
            if a.project_id and b.project_id and a.project_id!=b.project_id:continue
            if a.occurred_at and b.occurred_at and a.occurred_at!=b.occurred_at:continue
            if SequenceMatcher(None,a.title,b.title).ratio()<0.6:continue
            candidates.append({'first':a.id,'second':b.id,'first_title':a.title,'second_title':b.title,'first_description':a.description,'second_description':b.description,'first_date':a.occurred_at or a.published_at,'second_date':b.occurred_at or b.published_at})
    candidates=candidates[:20]
    if not candidates:return {'candidates':0,'merged':0,'usage':{}}
    import json
    usage={}
    result=await ai.structured(Results,'Compare only these recalled pairs. Confirm SAME specific occurrence, product/version, outcome, date and metrics, not merely similar work or related cooperation. Different releases, planned vs completed, or contradictory numbers must NOT merge. Unknown dates require strong shared product/version anchors. shared_anchor must be a verbatim distinctive product/version phrase in BOTH descriptions/titles. Generic robot/model/company words are not anchors. Return all pair judgments and brief auditable reasons, no hidden reasoning. DATA: '+json.dumps(candidates,ensure_ascii=False),usage)
    lookup={e.id:e for e in events};allowed={(p['first'],p['second']) for p in candidates};merged=0
    for pair in result.pairs:
        if (pair.first,pair.second) not in allowed or not pair.same_progress or len(pair.shared_anchor)<3:continue
        a,b=lookup[pair.first],lookup[pair.second]
        numeric_a={(x.get('name'),x.get('unit')):x.get('value') for x in a.metrics}
        numeric_b={(x.get('name'),x.get('unit')):x.get('value') for x in b.metrics}
        if any(numeric_a[k]!=numeric_b[k] for k in numeric_a.keys()&numeric_b.keys()):
            for e in (a,b):
                assessment=db.get(m.EventAssessment,e.id)
                assessment.review_status='questionable'
            continue
        if pair.shared_anchor.lower() in ('robot','model','机器人','模型'):continue
        if any(pair.shared_anchor not in e.title+' '+e.description for e in (a,b)):continue
        left,right=members[a.id].cluster_id,members[b.id].cluster_id
        if left==right:continue
        group=[lookup[id] for id,row in members.items() if row.cluster_id in (left,right)]
        if len({e.occurred_at for e in group if e.occurred_at})>1:continue
        if len({e.project_id for e in group if e.project_id})>1:continue
        for member in members.values():
            if member.cluster_id==right:member.cluster_id=left
        cluster=db.get(m.EventCluster,left);cluster.method='rule_recall+llm';cluster.reason=pair.reason
        merged+=1
    db.commit();return {'candidates':len(candidates),'merged':merged,'usage':usage}
