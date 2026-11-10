"""Authorize first; use tenant reads locally and static verified demo data externally."""
from core.demo_telemetry import FIXTURES
from models.models import Company
from models.customer_data import CustomerAsset, LogCollector, CustomerLog
from routers.customer_data import authorized_company
from services import gemini_support
from services.knowledge_answers import COMPANY_SCOPES, answer_from_knowledge

TOPICS = {
    'ransomware': ('ransomware', 'เรียกค่าไถ่'),
    'malware': ('malware', 'มัลแวร์', 'virus'),
    'phishing': ('phishing', 'ฟิชชิง', 'อีเมลหลอก'),
    'account_security': ('login', 'password', 'mfa', 'เข้าสู่ระบบ', 'รหัสผ่าน'),
    'network_attack': ('scan', 'firewall', 'ddos', 'เครือข่าย'),
    'endpoint_detection': ('edr', 'crowdstrike', 'endpoint', 'อุปกรณ์ปลายทาง'),
    'siem_monitoring': ('siem', 'monitor', 'เฝ้าระวัง'),
    'vulnerability': ('vulnerability', 'patch', 'cve', 'ช่องโหว่', 'แพตช์'),
    'data_protection': ('backup', 'exfiltration', 'สำรองข้อมูล', 'ข้อมูลรั่ว'),
    'incident_response': ('incident', 'breach', 'contain', 'เหตุการณ์', 'รับมือ'),
}


def question_topics(message):
    # Only fixed enums leave the server. Never send arbitrary user/prompt text,
    # credentials, asset names from another company, or transcript bodies.
    q = message[:1000].casefold()
    if any(word in q for word in ('collector', 'lc', 'ตัวเก็บ', 'คอลเลกเตอร์')):
        category = 'collectors'
    elif any(word in q for word in ('ip', 'asset', 'host', 'server', 'เครื่อง', 'ไอพี', 'อุปกรณ์')):
        category = 'assets'
    else:
        category = 'logs'
    return {'category': category, 'topics': [name for name, words in TOPICS.items()
            if any(word in q for word in words)] or ['security_support']}


def verified_demo(company_name, assets, collectors, logs):
    fixture = FIXTURES.get(company_name)
    if not fixture:
        return []
    collector_name, site, entries = fixture
    evidence = []
    safe_assets, safe_collectors = {}, set()
    for asset in assets:
        if any((asset.ip_address, asset.hostname, asset.asset_type) == entry[:3] for entry in entries):
            safe_assets[asset.id] = asset
            evidence.append({'kind': 'asset', 'ip': asset.ip_address, 'hostname': asset.hostname, 'type': asset.asset_type})
    for collector in collectors:
        if (collector.name, collector.site) == (collector_name, site):
            safe_collectors.add(collector.id)
            evidence.append({'kind': 'collector', 'name': collector_name, 'site': site})
    for log in logs:
        asset = safe_assets.get(log.asset_id)
        if asset and log.collector_id in safe_collectors and any(
            (asset.ip_address, log.event_type, log.message) == (entry[0], entry[3], entry[4]) for entry in entries):
            evidence.append({'kind': 'event', 'hostname': asset.hostname, 'event': log.event_type, 'message': log.message})
    return evidence[:12]


def answer_question(message, db, user, company_id=None, history=None):
    cid = authorized_company(db, user, company_id)  # before any retrieval/provider
    company = db.get(Company, cid)
    is_demo = company and company.name in COMPANY_SCOPES and user.email.endswith('@example.test')
    if is_demo:
        kb_answer = answer_from_knowledge(message, company, user)
        if kb_answer is not None:
            return {**kb_answer, 'company_id': str(cid), 'category': 'knowledge_base'}
    assets = db.query(CustomerAsset).filter(CustomerAsset.company_id == cid).order_by(CustomerAsset.ip_address).limit(20).all()
    collectors = db.query(LogCollector).filter(LogCollector.company_id == cid).order_by(LogCollector.name).limit(10).all()
    logs = db.query(CustomerLog).filter(CustomerLog.company_id == cid).order_by(CustomerLog.occurred_at.desc()).limit(20).all()
    names = {asset.id: asset.hostname for asset in assets}
    kind = question_topics(message)['category']
    if kind == 'collectors':
        answer = ('Log collectors: ' + '; '.join(f'{c.name} ({c.site})' for c in collectors)) if collectors else 'No log collectors found.'
    elif kind == 'assets':
        answer = ('Assets: ' + '; '.join(f'{a.hostname} [{a.ip_address}] ({a.asset_type})' for a in assets)) if assets else 'No assets found.'
    else:
        answer = ('Recent security events: ' + '; '.join(f"{log.event_type} on {names.get(log.asset_id, 'unknown asset')}: {log.message}" for log in logs[:10])) if logs else 'No security events found.'
    answer = answer[:3000]
    result = {'answer': answer, 'source': 'tenant_scoped_mock_data', 'mode': 'rule_based_demo',
              'category': kind, 'company_id': str(cid),
              'counts': {'assets': len(assets), 'collectors': len(collectors), 'logs': len(logs)}}
    if not is_demo or not gemini_support.configured():
        return result
    context = {'data_kind': 'verified_static_demo_telemetry', 'question': question_topics(message),
        'recent_topics': [question_topics(item.get('content', '')) for item in (history or [])[-gemini_support.MAX_HISTORY:]
                          if item.get('role') == 'customer'],
        'mock_telemetry': verified_demo(company.name, assets, collectors, logs)}
    advice = gemini_support.guidance(context, user_id=user.id)
    if advice:
        result.update(mode='gemini_demo', answer='ข้อมูลจากระบบ demo (ไม่ใช่หลักฐานระบบจริง):\n' + answer
                      + '\n\nคำแนะนำทั่วไปจาก Gemini (ไม่ใช่ผลตรวจระบบ):\n' + advice)
    return result
