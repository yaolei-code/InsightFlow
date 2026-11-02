"""Actual collector probe. Saves real results, never synthesizes snapshots."""
import asyncio
import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.db import Session
from app.models import Source
from app.research import process_source
from sqlalchemy import select

async def main():
    with Session() as db:
        for source in db.scalars(select(Source)):
            result=await process_source(db,source,{})
            print(json.dumps({'url':source.url,'status':source.last_status,'message':result},ensure_ascii=False))

if __name__=='__main__': asyncio.run(main())
