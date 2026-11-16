"""Generate PostgreSQL seed SQL and manifest; does not execute SQL."""
import argparse
import json
from pathlib import Path
from .cases import VERSION, cases, identity

def literal(value): return "'"+str(value).replace("'","''")+"'"

def sql():
    statements=['BEGIN;', '''DO $$ BEGIN
IF (SELECT count(*) FROM companies WHERE name='Company A (Demo)') <> 1 OR
   (SELECT count(*) FROM companies WHERE name='Company B (Demo)') <> 1 THEN
RAISE EXCEPTION 'Expected exactly one Company A (Demo) and Company B (Demo)';
END IF; END $$;''']
    def company(letter): return "(SELECT id FROM companies WHERE name="+literal('Company '+letter+' (Demo)')+")"
    def insert(table,fields,values):
        statements.append(f'INSERT INTO {table} ({", ".join(fields)}) VALUES ({", ".join(values)}) ON CONFLICT (id) DO NOTHING;')
    for letter in ('A','B'):
        insert('log_collectors',['id','company_id','name','site'],[literal(identity('collector:'+letter)),company(letter),literal(VERSION),literal('Synthetic evaluation')])
        statements.append('DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM log_collectors WHERE id='+literal(identity('collector:'+letter))+
            ' AND company_id='+company(letter)+' AND name='+literal(VERSION)+
            ") THEN RAISE EXCEPTION 'Collector fixture mismatch'; END IF; END $$;")
    for case in cases():
        aid=identity(case['case_id']+':asset');cid=identity('collector:'+case['company'])
        insert('customer_assets',['id','company_id','ip_address','hostname','asset_type'],
               [literal(aid),company(case['company']),literal(case['asset_ip']),literal(case['host']),literal('VPN')])
        statements.append('DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM customer_assets WHERE id='+literal(aid)+
            ' AND company_id='+company(case['company'])+' AND hostname='+literal(case['host'])+' AND ip_address='+literal(case['asset_ip'])+
            ") THEN RAISE EXCEPTION 'Asset fixture mismatch'; END IF; END $$;")
        for row in case['rows']:
            message=f"event_id={row['event_id']} account={row['account']}"
            if row['source_ip']: message+=f" source_ip={row['source_ip']}"
            message+=f" fixture={VERSION} case={case['case_id']}"
            insert('customer_logs',['id','company_id','asset_id','collector_id','event_type','message','occurred_at'],
                [literal(row['id']),company(case['company']),literal(aid),literal(cid),literal(row['event_type']),literal(message),literal(row['timestamp'])])
            statements.append('DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM customer_logs WHERE id='+literal(row['id'])+
                ' AND company_id='+company(case['company'])+' AND asset_id='+literal(aid)+' AND collector_id='+literal(cid)+
                ' AND event_type='+literal(row['event_type'])+' AND message='+literal(message)+
                ' AND occurred_at='+literal(row['timestamp'])+"::timestamp) THEN RAISE EXCEPTION 'Fixture mismatch'; END IF; END $$;")
    statements+=['COMMIT;',f"SELECT count(*) AS retained_evaluation_logs FROM customer_logs WHERE message LIKE '%fixture={VERSION} %';"]
    return '\n'.join(statements)+'\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'manifest.json').write_text(json.dumps({'version':VERSION,'cases':cases()},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'seed.sql').write_text(sql(),encoding='utf-8')
    print('Prepared',len(cases()),'cases;',sum(len(c['rows']) for c in cases()),'logs. No database writes executed.')
if __name__=='__main__':main()
