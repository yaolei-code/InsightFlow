"""Explicit real-LLM acceptance using an existing snapshot, no re-fetch or Mock."""
import asyncio
import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select
from app.db import Session, utcnow
from app.models import Snapshot
from app.extraction import extract_saved_snapshot
from app.ai import safe_error
from app.config import settings

async def main():
    usage={}
    result={'executed_at':utcnow(),'model':settings.openai_model,'protocol':settings.llm_protocol,'mock':False}
    with Session() as db:
        snap=db.scalar(select(Snapshot).where(Snapshot.source_id==1).order_by(Snapshot.sequence.desc()))
        if not snap:
            result.update(status='failed',error='未找到真实快照')
        else:
            result.update(snapshot_id=snap.id,source_url=snap.source_url)
            try:
                counts=await extract_saved_snapshot(db,snap.id,usage)
                result.update(status='completed',counts=counts)
            except Exception as exc:
                result.update(status='failed',error=safe_error(exc))
    result['usage']=usage
    text=json.dumps(result,ensure_ascii=False,indent=2)
    (Path(__file__).resolve().parents[1]/'docs'/'stage2-acceptance.json').write_text(text+'\n',encoding='utf-8',newline='\n')
    print(text)

if __name__=='__main__':asyncio.run(main())
