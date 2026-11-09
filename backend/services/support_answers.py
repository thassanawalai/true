"""Authorize first; use tenant reads locally and static verified demo data externally."""
import re
from core.demo_telemetry import FIXTURES
from models.models import Company
from models.customer_data import CustomerAsset, LogCollector, CustomerLog
from routers.customer_data import authorized_company
from services import gemini_support, knowledge_base, security_analysis

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
    if re.fullmatch(r'(?:สวัสดี(?:ครับ|ค่ะ|คะ)?|หวัดดี(?:ครับ|ค่ะ)?|hello|hi|hey)[\s!.]*', message.strip(), re.IGNORECASE):
        return {'answer': 'สวัสดีค่ะ มีเรื่องความปลอดภัยใดให้ช่วยแนะนำบ้างคะ? เช่น อีเมลน่าสงสัย การเข้าสู่ระบบ หรือการรับมือเหตุการณ์',
                'source': 'tenant_scoped_mock_data', 'mode': 'rule_based_demo',
                'citations': [], 'retrieval': 'keyword_tag', 'kb_status': 'no_match',
                'category': 'logs', 'company_id': str(cid),
                'counts': {'assets': 0, 'collectors': 0, 'logs': 0}}
    documents = knowledge_base.retrieve(message, cid)
    topics = question_topics(message)
    inventory_only = bool(re.fullmatch(r'(?:show |list |recent )?(?:logs|events|assets|collectors)[?.! ]*',
                                       message.strip(), re.IGNORECASE))
    analysis = (security_analysis.analyze(message, db, cid)
                if not inventory_only and (topics['category'] == 'logs' or topics['topics'] != ['security_support']
                    or security_analysis.classify(message)[0] != 'unknown_security_issue') else None)
    assets = db.query(CustomerAsset).filter(CustomerAsset.company_id == cid).order_by(CustomerAsset.ip_address).limit(20).all()
    collectors = db.query(LogCollector).filter(LogCollector.company_id == cid).order_by(LogCollector.name).limit(10).all()
    logs = (db.query(CustomerLog)
            .join(CustomerAsset, CustomerLog.asset_id == CustomerAsset.id)
            .join(LogCollector, CustomerLog.collector_id == LogCollector.id)
            .filter(CustomerLog.company_id == cid, CustomerAsset.company_id == cid,
                    LogCollector.company_id == cid)
            .order_by(CustomerLog.occurred_at.desc()).limit(20).all())
    names = {asset.id: asset.hostname for asset in assets}
    kind = question_topics(message)['category']
    if kind == 'collectors':
        answer = ('ตัวเก็บ Log: ' + '; '.join(f'{c.name} ({c.site})' for c in collectors)) if collectors else 'ไม่พบตัวเก็บ Log ในข้อมูลที่ได้รับอนุญาต'
    elif kind == 'assets':
        answer = ('อุปกรณ์: ' + '; '.join(f'{a.hostname} [{a.ip_address}] ({a.asset_type})' for a in assets)) if assets else 'ไม่พบอุปกรณ์ในข้อมูลที่ได้รับอนุญาต'
    else:
        answer = ('เหตุการณ์ล่าสุด: ' + '; '.join(f"{log.event_type} บน {names.get(log.asset_id, 'อุปกรณ์ที่ไม่ทราบชื่อ')}: {log.message}" for log in logs[:10])) if logs else 'ไม่พบเหตุการณ์ในข้อมูลที่ได้รับอนุญาต การไม่มีข้อมูลไม่ยืนยันว่าระบบปลอดภัย'
    answer = answer[:3000]
    evidence = 'ข้อมูลจากระบบ demo (ไม่ใช่หลักฐานระบบจริง):\n' + answer
    local_answer = (security_analysis.render(analysis, documents) if analysis else
                    evidence + '\n\n' + knowledge_base.render(documents))
    result = {'answer': local_answer, 'source': 'tenant_scoped_mock_data', 'mode': 'rule_based_demo',
              'citations': knowledge_base.citations(documents),
              'retrieval': 'keyword_tag', 'kb_status': 'matched' if documents else 'no_match',
              'category': kind, 'company_id': str(cid),
              'counts': {'assets': len(assets), 'collectors': len(collectors), 'logs': len(logs)}}
    if analysis:
        result['analysis'] = analysis
    if not gemini_support.configured():
        result['answer'] += '\n\nขณะนี้ไม่ได้ใช้ AI (Gemini); ใช้การวิเคราะห์ภายในระบบและ KB ที่ได้รับอนุญาต'
        return result
    company = db.get(Company, cid)
    context = {'data_kind': 'verified_static_demo_telemetry', 'question': question_topics(message),
        'recent_topics': [question_topics(item.get('content', '')) for item in (history or [])[-gemini_support.MAX_HISTORY:]
                          if item.get('role') == 'customer'],
        'mock_telemetry': verified_demo(company.name, assets, collectors, logs),
        'public_knowledge': knowledge_base.public_context(documents)}
    advice = gemini_support.guidance(context)
    # Model suggestions select reviewed actions; model-authored facts and
    # identifiers are never rendered, including hallucinated tenant data.
    advice = safe_guidance(advice)
    # Citation provenance is rendered by the backend, never invented by a model.
    if advice and not re.search(r'\bKB[-_]|https?://', advice, re.IGNORECASE):
        result.update(mode='gemini_demo', answer=(security_analysis.render(analysis, documents, advice)
                      if analysis else local_answer + '\n\nคำแนะนำทั่วไปจาก Gemini (ไม่ใช่ผลตรวจระบบ):\n' + advice))
    else:
        result['answer'] += '\n\nAI ไม่พร้อมใช้งานหรือคำตอบไม่ผ่านการตรวจสอบ จึงใช้การวิเคราะห์ภายในระบบและ KB แทน'
    return result


def safe_guidance(text):
    """Gemini can select reviewed actions, never introduce facts into an answer."""
    if not text or not gemini_support.validate_text(text):
        return None
    if re.search(r'\bKB[-_]|https?://', text, re.IGNORECASE):
        return None
    choices = (
        (('mfa', 'สิทธิ์'), 'ตรวจสอบการตั้งค่า MFA และทบทวนสิทธิ์เข้าถึง'),
        (('บัญชี', 'เข้าสู่ระบบ'), 'ตรวจสอบบัญชีและการเข้าสู่ระบบสำเร็จหลัง alert รวมถึง source IP และผล MFA'),
        (('firewall', 'พอร์ต', 'scanner'), 'ตรวจสอบกฎ firewall และยืนยันว่าเป็น scanner ที่ได้รับอนุญาตหรือไม่'),
        (('soc', 'หลักฐาน'), 'หลักฐานจำลองยังไม่เพียงพอ ควรให้ SOC ตรวจสอบเพิ่มเติมก่อนสรุปเหตุการณ์'),
    )
    selected = [action for terms, action in choices if any(term in text.casefold() for term in terms)]
    return '\n'.join(selected[:3]) or None
