"""Bounded real discovery; never auto-approve candidates or create events from snippets."""
import asyncio,json,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select,func
from app.db import Session,utcnow
from app import models as m
from app.discovery import discover_seed,discover_search
from app.search import SearchInput

async def main():
    output={'executed_at':utcnow(),'mock':False,'seeds':[],'searches':[]}
    # Serial DB writes avoid long-lived competing SQLite transactions.
    with Session() as db:
        for seed in db.scalars(select(m.DiscoverySeed).order_by(m.DiscoverySeed.id)).all():
            try:
                result=await asyncio.wait_for(discover_seed(db,seed),timeout=100)
                entry={'name':seed.name,'url':seed.url,'status':seed.last_status,**result}
            except Exception as exc:
                db.rollback();seed.last_status='error';seed.error=type(exc).__name__;seed.last_checked_at=utcnow();db.commit()
                entry={'name':seed.name,'url':seed.url,'status':'error','error':type(exc).__name__}
            output['seeds'].append(entry);print(json.dumps(entry,ensure_ascii=False),flush=True)
        now=datetime.now(timezone.utc).date()
        company=db.scalar(select(m.Company).where(m.Company.name=='智元机器人'))
        searches=[SearchInput(kind='industry',query='具身智能 工厂 客户试点 商业交付',keywords=['机器人','商业部署'],start_date=now-timedelta(days=30),end_date=now),SearchInput(kind='company',company_id=company.id,keywords=['客户试点','机器人发布'],start_date=now-timedelta(days=30),end_date=now),SearchInput(kind='technology',query='VLA robot foundation model open source',keywords=['deployment'],domains=['pi.website','figure.ai','1x.tech']),SearchInput(kind='github',query='unitree',provider='github')]
        for body in searches:
            run=m.DiscoveryRun(kind='search',status='running',parameters=body.model_dump(mode='json'));db.add(run);db.commit()
            try:
                result=await discover_search(db,body);run.status='completed';run.result=result;entry=result
            except Exception as exc:
                db.rollback();entry={'status':'failed','error':str(exc)[:250]};run.status='failed';run.error=str(exc)[:250]
            run.finished_at=utcnow();db.commit();output['searches'].append(entry);print(json.dumps(entry,ensure_ascii=False),flush=True)
        output['counts']={key:db.scalar(select(func.count()).select_from(model)) for key,model in [('candidates',m.SourceCandidate),('sources',m.Source),('snapshots',m.Snapshot),('events',m.ProgressEvent)]}
    (Path(__file__).resolve().parents[1]/'docs'/'coverage-acceptance.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':asyncio.run(main())
