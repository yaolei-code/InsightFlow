"""Analyze saved product snapshots through the existing bounded research queue."""
import json,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
def call(path,body=None):
    req=Request('http://127.0.0.1:8000/api'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=15) as response:return json.load(response)
for source in call('/sources?limit=200'):
    if not source.get('product_id') or not source['is_active']:continue
    snapshots=call('/sources/'+str(source['id'])+'/snapshots?limit=1')
    if not snapshots:continue
    while True:
        try:task=call('/snapshots/'+str(snapshots[0]['id'])+'/extract',{});break
        except HTTPError as exc:
            if exc.code!=409:raise
            time.sleep(5)
    print(json.dumps({'product_id':source['product_id'],'snapshot_id':snapshots[0]['id'],'task_id':task['id']}),flush=True)
    while task['status'] in ('queued','running'):
        time.sleep(5);task=call('/tasks/'+str(task['id']))
    print(json.dumps({'task':task['id'],'status':task['status'],'logs':task['logs']},ensure_ascii=True),flush=True)
