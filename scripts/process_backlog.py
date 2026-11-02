"""Drain the current backlog through the live API; retry initial failures once."""
import json,time,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.stdout.reconfigure(encoding='utf-8')
BASE='http://127.0.0.1:8000/api'
OUTPUT=Path(__file__).resolve().parents[1]/'docs'/'backlog-processing.json'

def request(path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=Request(BASE+path,data=data,headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=15) as response:return json.load(response)

def candidates():
    rows=[];offset=0
    while True:
        payload=request(f'/source-candidates?offset={offset}&limit=200')
        rows.extend(payload['items']);offset+=200
        if offset>=payload['total']:return rows

def save(data):
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def batch(ids,retry,result):
    while True:
        try:
            run=request('/discovery/ingest',{'limit':30,'candidate_ids':ids,'retry_failed':retry});break
        except HTTPError as exc:
            if exc.code!=409:raise
            print('等待当前研究任务完成',flush=True);time.sleep(15)
    print(json.dumps({'run':run['id'],'selected':len(ids),'retry':retry}),flush=True)
    last=None
    while True:
        run=request('/discovery-runs/'+str(run['id']))
        progress=run.get('result',{}).get('processed',0)
        if progress!=last:
            print(json.dumps({'run':run['id'],'status':run['status'],'processed':progress,'completed':run.get('result',{}).get('completed',0)}),flush=True);last=progress
        if run['status'] not in ('queued','running'):break
        time.sleep(5)
    result['runs'].append(run);save(result)
    if run['status']!='completed':raise RuntimeError('批次未完成：'+str(run['id']))

def main():
    initial=candidates()
    todo=[r['id'] for r in initial if r['processing_status']=='not_started' and r['review_status']!='rejected']
    retries=[r['id'] for r in initial if r['processing_status']=='failed' and r['review_status']!='rejected']
    result={'started_at':datetime.now(timezone.utc).isoformat(),'initial':{'total':len(initial),'not_started':len(todo),'retry_once':len(retries)},'runs':[],'before':request('/coverage')}
    save(result);print(json.dumps(result['initial']),flush=True)
    for retry,ids in [(False,todo),(True,retries)]:
        for start in range(0,len(ids),30):batch(ids[start:start+30],retry,result)
    final=candidates();counts={}
    for row in final:counts[row['processing_status']]=counts.get(row['processing_status'],0)+1
    result.update(finished_at=datetime.now(timezone.utc).isoformat(),after=request('/coverage'),processing_counts=counts,remaining_not_started=sum(r['processing_status']=='not_started' and r['review_status']!='rejected' for r in final),failures=[{'id':r['id'],'url':r['url'],'reason':r['processing_error']} for r in final if r['processing_status']=='failed'])
    save(result);print(json.dumps({'finished':True,'counts':counts,'remaining':result['remaining_not_started'],'events':result['after']['events']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
