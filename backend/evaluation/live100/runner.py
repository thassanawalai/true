"""Sequential resumable runner. Reserve budget before I/O; never retry uncertain calls.
Token and passwords are read only from environment and never saved in result files.
"""
import argparse
import csv
import getpass
import hashlib
import contextlib
import json
import os
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse
import httpx
from .cases import VERSION, cases, grade


class Ledger:
    def __init__(self,path,budget=250,interval=60):
        self.db=sqlite3.connect(path,timeout=30)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS attempts(
          case_id TEXT PRIMARY KEY, started REAL NOT NULL, status TEXT NOT NULL, result TEXT);
          CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
        self.budget=budget;self.interval=interval
    def bind(self,key,value):
        old=self.db.execute('SELECT value FROM config WHERE key=?',(key,)).fetchone()
        if old and old[0]!=value: raise ValueError('Run identity mismatch: '+key)
        self.db.execute('INSERT OR IGNORE INTO config VALUES(?,?)',(key,value));self.db.commit()
    def reserve(self,case_id):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            now=time.time()
            if self.db.execute('SELECT 1 FROM attempts WHERE case_id=?',(case_id,)).fetchone():
                self.db.rollback();return False
            count,last=self.db.execute('SELECT count(*),max(started) FROM attempts').fetchone()
            recent=self.db.execute('SELECT count(*) FROM attempts WHERE started>?',(now-86400,)).fetchone()[0]
            if count>=self.budget or recent>=self.budget: raise RuntimeError('Budget exhausted')
            if last and now-last<self.interval: raise RuntimeError('Cooldown active')
            self.db.execute('INSERT INTO attempts VALUES(?,?,?,NULL)',(case_id,now,'in_flight'))
            self.db.commit();return True
        except BaseException:
            self.db.rollback();raise
    def remaining_wait(self):
        last=self.db.execute('SELECT max(started) FROM attempts').fetchone()[0]
        finished=self.db.execute("SELECT value FROM config WHERE key='last_finished'").fetchone()
        last=max(last or 0,float(finished[0]) if finished else 0)
        return max(0,self.interval-(time.time()-last))
    def finish(self,case_id,status,result):
        self.db.execute("INSERT OR REPLACE INTO config VALUES('last_finished',?)",(str(time.time()),))
        self.db.execute('UPDATE attempts SET status=?,result=? WHERE case_id=?',
                        (status,json.dumps(result,ensure_ascii=False),case_id));self.db.commit()
    def report(self,path):
        rows=[dict(case_id=c,status=s,result=json.loads(r) if r else None) for c,s,r in self.db.execute('SELECT case_id,status,result FROM attempts ORDER BY case_id')]
        summary={'version':VERSION,'planned':100,'recorded':len(rows),
            'facts_passed':sum(bool((r['result'] or {}).get('facts_passed')) for r in rows),
            'gemini_passed':sum(bool((r['result'] or {}).get('gemini_passed')) for r in rows),
            'unattempted':100-len(rows),'attempts':rows}
        Path(path).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        with Path(path).with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as output:
            writer=csv.writer(output)
            writer.writerow(['case_id','status','facts_passed','gemini_passed','failure','latency_ms'])
            for row in rows:
                result=row['result'] or {}
                provider=result.get('response',{}).get('provider',{})
                writer.writerow([row['case_id'],row['status'],result.get('facts_passed'),result.get('gemini_passed'),provider.get('failure'),provider.get('latency_ms')])
        return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',required=True);p.add_argument('--state',required=True)
    p.add_argument('--limit',type=int,default=5);p.add_argument('--budget',type=int,default=250)
    p.add_argument('--interval',type=int,default=60);p.add_argument('--report',required=True)
    p.add_argument('--continue-after-review', action='store_true')
    args=p.parse_args()
    if urlparse(args.url).scheme!='https': p.error('HTTPS required')
    if not 1<=args.limit<=100 or not 1<=args.budget<=250 or args.interval<60: p.error('Invalid safety limits')
    token=os.environ.get('SOC_EVAL_TOKEN')
    if not token:
        with httpx.Client(base_url=args.url.rstrip('/'),timeout=40,follow_redirects=False) as login_client:
            response=login_client.get('/api/demo-auth/users');response.raise_for_status()
            users=[u for u in response.json() if u.get('name')=='Customer A1' and u.get('company')=='Company A (Demo)' and u.get('role')=='CUSTOMER']
            if len(users)!=1: p.error('Cannot identify Customer A1; supply SOC_EVAL_TOKEN securely')
            password=getpass.getpass('Customer A1 password (not saved): ')
            response=login_client.post('/api/demo-auth/login',json={'user_id':users[0]['id'],'password':password})
            del password
            response.raise_for_status();token=response.json()['token']
    ledger=Ledger(args.state,args.budget,args.interval)
    ledger.bind('url',args.url.rstrip('/'));ledger.bind('version',VERSION)
    stopped = ledger.db.execute("SELECT status,result FROM attempts").fetchall()
    if not args.continue_after_review and any(status!='completed' or not all(json.loads(result).get(k) for k in ('facts_passed','gemini_passed')) for status,result in stopped):
        p.error('Previous run stopped or has uncertain results. Review report before --continue-after-review.')
    ledger.bind('cases_sha256',hashlib.sha256(json.dumps(cases(),sort_keys=True).encode()).hexdigest())
    completed=0
    with httpx.Client(base_url=args.url.rstrip('/'),headers={'Authorization':'Bearer '+token},timeout=40,follow_redirects=False) as client:
        me=client.get('/api/demo-auth/me');me.raise_for_status()
        user=me.json()
        if user.get('role')!='CUSTOMER' or user.get('company')!='Company A (Demo)': raise RuntimeError('Use a Company A customer account')
        ledger.bind('user_id',str(user['id']));ledger.bind('company_id',str(user['company_id']))
        try:
            for case in cases():
                if ledger.db.execute('SELECT 1 FROM attempts WHERE case_id=?',(case['case_id'],)).fetchone(): continue
                # Wait is restart-safe because timestamps are stored in SQLite.
                while ledger.remaining_wait()>0: time.sleep(min(10,ledger.remaining_wait()))
                if not ledger.reserve(case['case_id']): continue
                try:
                    response=client.post('/api/customer-data/ask',json={'action':'analyze_log','message':case['question']})
                except httpx.TransportError as exc:
                    ledger.finish(case['case_id'],'transport_uncertain',{'error_type':type(exc).__name__})
                    break
                if response.status_code!=200:
                    ledger.finish(case['case_id'],'http_error',{'http_status':response.status_code});break
                try: payload=response.json()
                except ValueError:
                    ledger.finish(case['case_id'],'invalid_response',{});break
                try: result=grade(case,payload)
                except (KeyError,TypeError,AttributeError):
                    ledger.finish(case['case_id'],'invalid_schema',{'response':payload});break
                result.update(response=payload,question=case['question'])
                ledger.finish(case['case_id'],'completed',result)
                completed+=1
                print(case['case_id'],'facts=',result['facts_passed'],'gemini=',result['gemini_passed'],flush=True)
                # Fail closed: no retries on 429, auth errors, timeouts, missing telemetry or fallback.
                if not result['gemini_passed'] or not result['facts_passed']: break
                if completed>=args.limit: break
                if completed%10==0:
                    for _ in range(30): time.sleep(10)
        finally:
            summary=ledger.report(args.report)
            print({k:v for k,v in summary.items() if k!='attempts'})

@contextlib.contextmanager
def single_runner(path):
    with open(path, 'a+b') as lock:
        try:
            if os.name == 'nt':
                import msvcrt
                lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another evaluation runner is active') from None
        try: yield
        finally:
            if os.name == 'nt':
                lock.seek(0);msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

if __name__=='__main__':
    # One invocation per working directory; do not start parallel evaluation directories.
    with single_runner('.soc-evaluation.lock'): main()

