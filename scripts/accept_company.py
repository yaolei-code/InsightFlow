"""Real source collection and bounded real company-event extraction."""
import asyncio,json,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select,func
from app.db import Session,utcnow
from app import models as m,ai,adapters
from app.research import create_snapshot
from app.progress import extract_progress

async def main():
    results=[]
    with Session() as db:
        for company_name,url,kind in [
            ('Physical Intelligence','https://www.pi.website/blog/api-beta','technical_blog'),
            ('逐际动力','https://www.limxdynamics.com/zh/news/BK000065','company_news'),
            ('Physical Intelligence','https://github.com/Physical-Intelligence/openpi','github'),
            ('Physical Intelligence','https://arxiv.org/abs/2410.24164','arxiv')]:
            company=db.scalar(select(m.Company).where(m.Company.name==company_name))
            source=db.scalar(select(m.Source).where(m.Source.company_id==company.id,m.Source.url==url))
            if not source:
                source=m.Source(company_id=company.id,url=url,source_type=kind);db.add(source);db.commit()
            entry={'company':company_name,'url':url,'source_type':kind}
            try:
                text,final=await asyncio.wait_for(adapters.collect(source),timeout=90)
                snap,_,created=create_snapshot(db,source,text,final)
                source.last_status='success';source.error=None;source.last_fetched_at=utcnow();db.commit()
                entry.update(status='success',snapshot_id=snap.id,characters=len(text),new_snapshot=created)
                if kind in ('technical_blog','company_news'):
                    usage={}
                    try:
                        entry['extraction']=await extract_progress(db,snap.id,usage)
                        entry['usage']=usage
                    except Exception as exc:entry['extraction_error']=ai.safe_error(exc)
            except Exception as exc:
                db.rollback();source.last_status='error';source.error=ai.safe_error(exc);source.last_fetched_at=utcnow();db.commit()
                entry.update(status='error',error=ai.safe_error(exc))
            results.append(entry)
            print(json.dumps(entry,ensure_ascii=False),flush=True)
        result={'executed_at':utcnow(),'mock':False,'companies':db.scalar(select(func.count()).select_from(m.Company)),'events':db.scalar(select(func.count()).select_from(m.ProgressEvent)),'sources':results}
    path=Path(__file__).resolve().parents[1]/'docs'/'company-acceptance.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':asyncio.run(main())
