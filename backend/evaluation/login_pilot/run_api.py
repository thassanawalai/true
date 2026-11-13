"""Run synthetic pilot against the actual FastAPI app in an isolated SQLite DB."""
import os
import sys
import tempfile
import json
import csv
import secrets
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parents[1]))
from scoring import grade

def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as directory:
        os.environ.update(DATABASE_URL='sqlite:///' + directory + '/pilot.sqlite',
                          GEMINI_ENABLED='false', PYTHON_DOTENV_DISABLED='1',
                          DEMO_AUTH_MODE='mock', RENDER='false', APP_ENV='test',
                          DEMO_SESSION_SECRET=secrets.token_hex(32))
        from main import app
        from core.database import Base, engine, SessionLocal
        from models.models import Company, User, RoleEnum
        from models.customer_data import CustomerAsset, CustomerLog, LogCollector
        from fastapi.testclient import TestClient
        Base.metadata.create_all(engine)
        results = []
        with TestClient(app) as client:
            for folder in sorted((ROOT/'cases').iterdir()):
                case = json.loads((folder/'input.json').read_text())
                truth = json.loads((folder/'ground_truth.json').read_text())
                with SessionLocal() as db:
                    company = Company(name=case['case_id'])
                    db.add(company)
                    db.flush()
                    user = User(email=case['case_id']+'@example.test', full_name='Pilot',
                                role=RoleEnum.CUSTOMER, company_id=company.id)
                    asset = CustomerAsset(company_id=company.id, ip_address='203.0.113.10',
                                          hostname='pilot-vpn-01', asset_type='VPN')
                    collector = LogCollector(company_id=company.id,name='Pilot',site='Synthetic')
                    db.add_all([user,asset,collector])
                    db.flush()
                    uid = str(user.id)
                    for row in case['logs']:
                        db.add(CustomerLog(company_id=company.id,asset_id=asset.id,collector_id=collector.id,
                            event_type='FAILED_LOGIN' if row['status']=='failure' else 'LOGIN_SUCCESS',
                            message=f"event_id={row['event_id']} account={row['account']} source_ip={row['source_ip']} status={row['status']}",
                            occurred_at=datetime.fromisoformat(row['timestamp']).astimezone(timezone.utc).replace(tzinfo=None)))
                    db.commit()
                login = client.post('/api/demo-auth/login',json={'user_id':uid})
                login.raise_for_status()
                question = 'วิเคราะห์ VPN login วันที่ 2026-11-13: ' + case['question']
                question += '\n' + case.get('playbook','')
                response = client.post('/api/customer-data/ask',json={'action':'analyze_log','message':question},
                                       headers={'Authorization':'Bearer '+login.json()['token']})
                response.raise_for_status()
                payload = response.json()
                activity = payload['analysis']['login_activity']
                fields = dict(activity)
                if len(activity['by_account']) == 1:
                    fields['account'] = activity['by_account'][0]['account']
                answer = payload['answer']
                if 'รายการที่มีเวลาเท่ากันยังยืนยันลำดับก่อนหลังไม่ได้' in answer:
                    fields['conclusion'] = 'order_undetermined'
                elif 'ยังยืนยัน account compromise ไม่ได้' in answer:
                    fields['conclusion'] = 'insufficient_evidence'
                if 'ตรวจสอบบัญชีและการเข้าสู่ระบบสำเร็จหลัง alert รวมถึง source IP และผล MFA' in answer:
                    fields.update(check_success_history=True,check_mfa_results=True)
                result = dict(case_id=case['case_id'],request=question,response=payload,
                              **grade(truth,fields))
                results.append(result)
                print(case['case_id'],result['status'],result['score'],result['maximum'])
        (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        with (output/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f)
            writer.writerow(['case_id','status','score','maximum','checks','answer'])
            for row in results:
                writer.writerow([row['case_id'],row['status'],row['score'],row['maximum'],
                                 json.dumps(row['checks'],ensure_ascii=False),row['response']['answer']])
        engine.dispose()

if __name__ == '__main__':
    main()
