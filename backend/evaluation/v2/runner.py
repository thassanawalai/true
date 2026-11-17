"""Serial HTTPS runner: raw-first persistence; fallback is scored, not discarded.
No automatic replay of an uncertain POST. All data stays in a private output directory.
"""
import argparse
import getpass
import json
import os
import sqlite3
import time
from pathlib import Path
import httpx
from evaluation.live100.runner import single_runner
from .scenarios import VERSION, suite, manifest, digest
from .scoring import evaluate, summarize

NAMES={'a1':'Customer A1','a2':'Customer A2','b1':'Customer B1','support':'SOC Support','admin':'SOC Admin'}

def policy(status,payload,grade):
    """Control flow is independent of quality except confirmed tenant leakage."""
    if any(x in grade.get('critical_failed',[]) for x in ('company','tenant_canaries','denial_no_data')):
        return 'pause_security',0
    provider=payload.get('provider',payload.get('evaluation',{}).get('provider',{}))
    reason=provider.get('failure')
    if status in (401,403) and grade.get('outcome')=='fail':return 'pause_auth',0
    if reason in ('provider_auth_error','provider_model_not_found'):return 'pause_configuration',0
    if reason=='usage_limit':return 'pause_quota',0
    if status==429 or reason=='provider_rate_limited':return 'backoff',300
    return 'continue',60


class Store:
    def __init__(self,directory):
        self.root=Path(directory);self.root.mkdir(parents=True,exist_ok=True)
        os.chmod(self.root,0o700)
        self.db=sqlite3.connect(self.root/'state.sqlite')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,started REAL,finished REAL,status TEXT,record TEXT);
            CREATE TABLE IF NOT EXISTS rooms(scenario_id TEXT PRIMARY KEY,room_id TEXT);''')
    def bind(self,k,v):
        value=json.dumps(v,sort_keys=True);old=self.db.execute('SELECT value FROM config WHERE key=?',(k,)).fetchone()
        if old and old[0]!=value:raise ValueError('Run identity mismatch: '+k)
        self.db.execute('INSERT OR IGNORE INTO config VALUES(?,?)',(k,value));self.db.commit()
    def get(self,k,default=None):
        row=self.db.execute('SELECT value FROM config WHERE key=?',(k,)).fetchone()
        return json.loads(row[0]) if row else default
    def set(self,k,v):
        self.db.execute('INSERT OR REPLACE INTO config VALUES(?,?)',(k,json.dumps(v)));self.db.commit()
    def seen(self,key):return bool(self.db.execute('SELECT 1 FROM calls WHERE id=?',(key,)).fetchone())
    def wait_seconds(self):return max(0,self.get('not_before',0)-time.time())
    def reserve(self,key,budget):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.seen(key):self.db.rollback();return False
            n=self.db.execute('SELECT count(*) FROM calls WHERE started>?',(time.time()-86400,)).fetchone()[0]
            if n>=budget:raise RuntimeError('Local rolling-24h conservative request budget exhausted')
            if self.wait_seconds()>0:raise RuntimeError('Cooldown active')
            self.db.execute('INSERT INTO calls VALUES(?,?,NULL,?,NULL)',(key,time.time(),'in_flight'))
            self.db.commit();return True
        except BaseException:self.db.rollback();raise
    def save(self,key,record,state='captured'):
        # SQLite is the durable source of truth; raw API response is committed BEFORE grading.
        self.db.execute('UPDATE calls SET finished=?,status=?,record=? WHERE id=?',
                        (time.time(),state,json.dumps(record,ensure_ascii=False),key));self.db.commit()
    def records(self):
        return [json.loads(x[0]) for x in self.db.execute('SELECT record FROM calls WHERE record IS NOT NULL ORDER BY started')]
    def export(self):
        records=self.records();summary=summarize(records,100)
        summary['in_flight_or_uncertain']=self.db.execute("SELECT count(*) FROM calls WHERE status IN ('in_flight','transport_uncertain')").fetchone()[0]
        summary['blocked_scenarios']=self.get('blocked',[])
        summary['run_kind']='live'
        summary['scenario_status']={}
        for case in suite():
            rows=[r for r in records if r.get('scenario_id')==case['id']]
            outcomes=[r.get('grade',{}).get('outcome','pending') for r in rows]
            summary['scenario_status'][case['id']]=('fail' if 'fail' in outcomes else 'unattempted' if not rows else
                'incomplete' if len(rows)!=len(case['turns']) else 'pending' if 'pending' in outcomes else 'pass')
        (self.root/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        (self.root/'responses.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
        import csv
        with (self.root/'assertions.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f);w.writerow(['scenario','turn','dimension','assertion','label','critical','reason'])
            for r in records:
                for a in r.get('grade',{}).get('assertions',[]):
                    w.writerow([r['scenario_id'],r['turn'],a['dimension'],a['id'],a['label'],a['critical'],a['reason']])
        return summary


def login(client,actors):
    response=client.get('/api/demo-auth/users');response.raise_for_status();users=response.json()
    tokens={};identities={}
    companies={label:next(u['company_id'] for u in users if u.get('company')==f'Company {label} (Demo)') for label in ('A','B')}
    for actor in actors:
        if actor=='anonymous':continue
        token=os.environ.get('SOC_EVAL_TOKEN_'+actor.upper()) or (os.environ.get('SOC_EVAL_TOKEN') if actor=='a1' else None)
        expected=[u for u in users if u['name']==NAMES[actor]]
        if len(expected)!=1:raise RuntimeError('Cannot uniquely identify '+actor)
        if not token:
            password=getpass.getpass(NAMES[actor]+' password (not saved): ')
            r=client.post('/api/demo-auth/login',json={'user_id':expected[0]['id'],'password':password})
            del password;r.raise_for_status();token=r.json()['token']
        r=client.get('/api/demo-auth/me',headers={'Authorization':'Bearer '+token});r.raise_for_status()
        me=r.json()
        if me['id']!=expected[0]['id']:raise RuntimeError('Wrong identity for '+actor)
        tokens[actor]=token;identities[actor]={'id':me['id'],'company_id':me['company_id'],'role':me['role']}
    return tokens,identities,companies


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--url',required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--actors',default='a1',help='Comma-separated a1,a2,b1,support,admin; anonymous always included')
    ap.add_argument('--limit',type=int,default=5,help='Maximum NEW response requests, not scenarios')
    ap.add_argument('--budget',type=int,default=150,help='Conservative app requests per rolling 24h, reserve judge budget separately')
    ap.add_argument('--interval',type=int,default=60)
    ap.add_argument('--resume-reviewed',action='store_true',help='Acknowledge uncertain requests; never replay them')
    args=ap.parse_args()
    if not args.url.startswith('https://') or not 1<=args.limit<=150 or not 1<=args.budget<=250 or args.interval<60:
        ap.error('Require HTTPS, limit 1..150, budget 1..250, interval >=60 seconds')
    actors=set(args.actors.split(','))|{'anonymous'}
    if not actors <= set(NAMES)|{'anonymous'}:ap.error('Unknown actor')
    store=Store(args.output)
    with single_runner(str(Path(args.output).resolve().parent/'.soc-evaluation-v2.lock')):
        store.bind('url',args.url.rstrip('/'));store.bind('manifest',manifest())
        if not args.resume_reviewed and store.db.execute("SELECT count(*) FROM calls WHERE status IN ('in_flight','transport_uncertain')").fetchone()[0]:
            store.export();ap.error('Uncertain POST found. Review raw results; --resume-reviewed skips it permanently.')
        with httpx.Client(base_url=args.url.rstrip('/'),timeout=40,follow_redirects=False) as client:
            tokens,identities,companies=login(client,actors)
            for actor,identity in identities.items():store.bind('actor:'+actor,identity)
            blocked=[];made=0
            try:
                for case in suite():
                    actor=case['actor']
                    if actor not in actors:
                        blocked.append({'scenario':case['id'],'reason':'missing_actor_session:'+actor});continue
                    headers={'Authorization':'Bearer '+tokens[actor]} if actor in tokens else {}
                    for ti,turn in enumerate(case['turns']):
                        key=f"{case['id']}:{ti}"
                        if store.seen(key):continue
                        if made>=args.limit:return
                        # Expired room mid-scenario is NOT recreated: that would erase context.
                        while store.wait_seconds()>0:time.sleep(min(10,store.wait_seconds()))
                        payload=dict(turn);target=payload.pop('company_ref',None)
                        if target:payload['company_id']=companies[target]
                        path='/api/customer-data/ask'
                        if case['room']:
                            row=store.db.execute('SELECT room_id FROM rooms WHERE scenario_id=?',(case['id'],)).fetchone()
                            if row:room_id=row[0]
                            else:
                                r=client.post('/api/chat-rooms',json={},headers=headers);r.raise_for_status();room_id=r.json()['id']
                                store.db.execute('INSERT INTO rooms VALUES(?,?)',(case['id'],room_id));store.db.commit()
                            path=f'/api/chat-rooms/{room_id}/messages';payload['content']=payload.pop('message')
                        if not store.reserve(key,args.budget):continue
                        start=time.monotonic();made+=1
                        record={'scenario_id':case['id'],'group':case['group'],'family':case['family'],'turn':ti,
                                'request':{'path':path,'payload':payload},'run_kind':'live','fault_injected':False}
                        try:r=client.post(path,json=payload,headers=headers)
                        except httpx.TransportError as exc:
                            record['error_type']=type(exc).__name__;store.save(key,record,'transport_uncertain')
                            store.set('not_before',time.time()+args.interval);return
                        record.update(http_status=r.status_code,latency_ms=round((time.monotonic()-start)*1000))
                        try:raw=r.json()
                        except ValueError:raw={'invalid_json':True,'body_length':len(r.content)}
                        record['response']=raw;store.save(key,record)
                        scope=None
                        if r.status_code==200 and actor in identities:
                            company=companies[target] if target else identities[actor]['company_id']
                            scope={'company_id':company,'forbidden_identifiers':[]}
                        record['grade']=evaluate(case,ti,r.status_code,raw,scope)
                        store.save(key,record,'graded')
                        action,delay=policy(r.status_code,raw,record['grade'])
                        count=store.db.execute('SELECT count(*) FROM calls').fetchone()[0]
                        delay=max(delay,args.interval,300 if count%10==0 else 0)
                        store.set('not_before',time.time()+delay)
                        store.export()
                        print(key,record['grade']['outcome'],record['grade']['route'],action,flush=True)
                        if action.startswith('pause'):store.set('pause_reason',action);return
            finally:
                store.set('blocked',blocked)
                result=store.export()
                print(json.dumps({k:result[k] for k in ('recorded_responses','response_outcomes','provider_attempts','in_flight_or_uncertain')},ensure_ascii=False))

if __name__=='__main__':main()
