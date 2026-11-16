"""Ground truth specified by scenario, independently of production parsing."""
from datetime import datetime, timedelta
from uuid import uuid5, NAMESPACE_URL

VERSION = 'soc-live100-v1'


def identity(value):
    return str(uuid5(NAMESPACE_URL, VERSION + ':' + value))


def cases():
    result = []
    for group in range(10):
        for variant in range(10):
            index = group * 10 + variant + 1
            cid = f'EVAL-{index:03}'
            host = f'eval{index:03}-vpn-01'
            account = f'eval{index:03}.user'
            count = variant + 1
            rows = []
            def add(kind, user=account, ip='192.0.2.10', minute=None, event=None, company='A'):
                number = len(rows) + 1
                rows.append(dict(id=identity(f'{cid}:row:{number}'), event_type=kind,
                    account=user, source_ip=ip, event_id=event or f'{cid}-{number}',
                    timestamp=(datetime(2026,11,16,2,0) + timedelta(minutes=number if minute is None else minute)).isoformat(),
                    company=company))
            for _ in range(count):
                add('FAILED_LOGIN')
            expected = dict(failed_count=count, successful_count=0, failed_rows=count,
                failed_unique=count, failures_by_ip={'192.0.2.10':count},
                by_account=[{'account':account,'count':count}],
                missing_source_ip_rows=0, same_timestamp=False, success_after_failure=None, truncated=False)
            selected = None
            if group == 1:
                add('LOGIN_SUCCESS'); expected.update(successful_count=1, success_after_failure=True)
            elif group == 2:
                add('FAILED_LOGIN', user=account+'2')
                expected.update(failed_count=count+1,failed_rows=count+1,failed_unique=count+1,
                    failures_by_ip={'192.0.2.10':count+1},
                    by_account=[{'account':account,'count':count},{'account':account+'2','count':1}])
            elif group == 3:
                add('FAILED_LOGIN',ip='192.0.2.20')
                expected.update(failed_count=count+1,failed_rows=count+1,failed_unique=count+1,
                    failures_by_ip={'192.0.2.10':count,'192.0.2.20':1},by_account=[{'account':account,'count':count+1}])
            elif group == 4:
                add('FAILED_LOGIN',event=rows[0]['event_id'],minute=1)
                expected.update(failed_count=count+1,failed_rows=count+1,
                    failures_by_ip={'192.0.2.10':count+1},by_account=[{'account':account,'count':count+1}])
            elif group == 5:
                rows=[]; add('FAILED_LOGIN',ip=None)
                expected.update(failed_count=1,failed_rows=1,failed_unique=1,failures_by_ip={},
                    by_account=[{'account':account,'count':1}],missing_source_ip_rows=1)
            elif group == 6:
                add('LOGIN_SUCCESS',minute=0); expected.update(successful_count=1,success_after_failure=False)
            elif group == 7:
                rows=[]; add('FAILED_LOGIN',minute=1);add('LOGIN_SUCCESS',minute=1)
                expected.update(failed_count=1,failed_rows=1,failed_unique=1,successful_count=1,
                    failures_by_ip={'192.0.2.10':1},by_account=[{'account':account,'count':1}],
                    same_timestamp=True,success_after_failure=False)
            elif group == 8:
                selected=[r['id'] for r in rows]
                add('FAILED_LOGIN',minute=61)
            elif group == 9:
                for row in rows: row['company']='B'
                selected=[]
                expected.update(failed_count=0,failed_rows=0,failed_unique=0,failures_by_ip={},by_account=[])
            result.append(dict(case_id=cid,group=['failure','success_after','accounts','ips','duplicate',
                'missing_ip','success_before','equal_time','time_window','tenant_isolation'][group],
                host=host,asset_ip=f'198.18.0.{index}', company=rows[0]['company'], rows=rows,
                question=f'วิเคราะห์ login host={host} วันที่ 2026-11-16 ตั้งแต่ 09:00 ถึงก่อน 10:00 เขตเวลา +07:00',
                expected=expected,expected_ids=selected if selected is not None else [r['id'] for r in rows]))
    return result


def exact(actual, expected):
    if type(actual) is not type(expected): return False
    if isinstance(expected, dict):
        return actual.keys()==expected.keys() and all(exact(actual[k],v) for k,v in expected.items())
    if isinstance(expected, list):
        return len(actual)==len(expected) and all(exact(a,b) for a,b in zip(actual,expected))
    return actual==expected


def grade(case, response):
    analysis=response.get('analysis',{})
    activity=analysis.get('login_activity') or {}
    checks={key: exact(activity.get(key),value) for key,value in case['expected'].items()}
    checks['evidence_ids']=sorted(f['log_id'] for f in analysis.get('findings',[]))==sorted(case['expected_ids'])
    answer=response.get('answer','')
    e=case['expected']
    checks['rendered_counts']=(f"ล็อกอินล้มเหลว {e['failed_count']} ครั้ง และสำเร็จ {e['successful_count']} ครั้ง" in answer
        if e['failed_count']+e['successful_count'] else 'ยังระบุจำนวนครั้ง' in answer)
    checks['rendered_accounts']=all(f"บัญชี {r['account']} ล็อกอินล้มเหลว {r['count']} ครั้ง" in answer for r in e['by_account'])
    checks['rendered_ips']=all(f'IP ต้นทาง {ip} ล้มเหลว {n} ครั้ง' in answer for ip,n in e['failures_by_ip'].items())
    checks['uncertainty']='ยังไม่ยืนยันการบุกรุก' in answer
    return {'facts_passed':all(checks.values()),'checks':checks,
            'gemini_passed':response.get('mode')=='gemini_demo' and response.get('provider',{}).get('succeeded') is True,
            'semantic_review':'not_scored'}


def seed(db, company_ids):
    from uuid import UUID
    from models.customer_data import CustomerAsset, CustomerLog, LogCollector
    for case in cases():
        company_id=UUID(str(company_ids[case['company']]))
        asset_id=UUID(identity(case['case_id']+':asset'))
        collector_id=UUID(identity('collector:'+case['company']))
        collector=db.get(LogCollector,collector_id)
        if collector and (collector.company_id != company_id or collector.name != VERSION):
            raise ValueError('Collector fixture mismatch')
        if collector is None:
            db.add(LogCollector(id=collector_id,company_id=company_id,name=VERSION,site='Synthetic evaluation'))
            db.flush()
        asset=db.get(CustomerAsset,asset_id)
        if asset and (asset.company_id != company_id or asset.hostname != case['host'] or asset.ip_address != case['asset_ip']):
            raise ValueError('Asset fixture mismatch')
        if asset is None:
            db.add(CustomerAsset(id=asset_id,company_id=company_id,hostname=case['host'],ip_address=case['asset_ip'],asset_type='VPN'))
            db.flush()
        for row in case['rows']:
            log_id=UUID(row['id'])
            message=f"event_id={row['event_id']} account={row['account']}"
            if row['source_ip']: message+=f" source_ip={row['source_ip']}"
            message+=f" fixture={VERSION} case={case['case_id']}"
            existing=db.get(CustomerLog,log_id)
            if existing:
                if existing.company_id != company_id or existing.asset_id != asset_id or existing.collector_id != collector_id or existing.message != message or existing.event_type != row['event_type'] or existing.occurred_at != datetime.fromisoformat(row['timestamp']):
                    raise ValueError('Existing fixture differs; refusing to overwrite')
                continue
            db.add(CustomerLog(id=log_id,company_id=company_id,asset_id=asset_id,collector_id=collector_id,
                event_type=row['event_type'],message=message,occurred_at=datetime.fromisoformat(row['timestamp'])))
    db.flush()
