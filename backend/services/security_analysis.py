"""Local, explainable triage. Call only after authorized_company has resolved scope.

No customer text, entities, timestamps or evidence from this module goes to AI.
A log label is an observation, never proof of compromise or IP ownership.
"""
from collections import Counter
import ipaddress
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from models.customer_data import CustomerAsset, CustomerLog, LogCollector
from services import knowledge_base

RULES = (
    ('suspicious_login', ('suspicious login', 'suspicious_login', 'login', 'brute force', 'brute-force', 'เข้าสู่ระบบ', 'ล็อกอิน'),
     ('SUSPICIOUS_LOGIN', 'ACCESS_DENIED', 'FAILED_LOGIN', 'LOGIN_FAILURE', 'BRUTE_FORCE')),
    ('port_scan', ('port scan', 'port_scan', 'portscan', 'สแกนพอร์ต'), ('PORT_SCAN',)),
    ('ransomware', ('ransomware', 'เรียกค่าไถ่'), ('RANSOMWARE',)),
    ('malware', ('malware', 'virus', 'มัลแวร์'), ('MALWARE', 'MALWARE_DETECTED')),
    ('phishing', ('phishing', 'ฟิชชิง', 'อีเมลหลอก'), ('PHISHING',)),
    ('data_exfiltration', ('exfiltration', 'ข้อมูลรั่ว'), ('DATA_EXFILTRATION',)),
    ('network_attack', ('ddos', 'blocked traffic', 'blocked_traffic'), ('DDOS', 'BLOCKED_TRAFFIC')),
)
ACTIONS = {
    'suspicious_login': ['ตรวจสอบบัญชีและการเข้าสู่ระบบสำเร็จหลัง alert รวมถึง source IP และผล MFA',
                         'ตรวจสอบการตั้งค่า MFA และทบทวนสิทธิ์เข้าถึง',
                         'หากยืนยันการเข้าถึงโดยไม่ได้รับอนุญาต ให้ SOC เพิกถอน session และรีเซ็ตรหัสผ่าน'],
    'phishing': ['เก็บ email headers และ URL โดยไม่เปิดลิงก์หรือไฟล์แนบ',
                 'หากกรอกรหัสผ่านแล้ว ให้ SOC ตรวจ session และเปลี่ยนรหัสผ่านผ่านช่องทางที่เชื่อถือได้'],
    'malware': ['เก็บ alert จาก EDR, process tree และ file hash ให้ SOC ตรวจสอบ',
                'หากยืนยันกิจกรรมอันตราย ให้ SOC ประเมินแยกเครื่องโดยเก็บรักษาหลักฐาน'],
    'ransomware': ['แจ้ง SOC เร่งด่วนและตรวจการเข้ารหัสไฟล์กับ EDR alerts',
                   'หากยังมีการแพร่กระจาย ให้ประสานแยกเครื่องและปกป้อง backup โดยรักษาหลักฐาน'],
    'data_exfiltration': ['ตรวจ audit logs, ปริมาณข้อมูล และปลายทางของการส่งข้อมูล',
                         'หากยืนยันการส่งข้อมูลโดยไม่ได้รับอนุญาต ให้ SOC จำกัด session และช่องทางที่เกี่ยวข้อง'],
    'network_attack': ['ตรวจอัตรา traffic และบริการที่ได้รับผลกระทบกับ firewall/IDS',
                       'ประสาน SOC ตรวจ rule และมาตรการจำกัด traffic ตามผลกระทบจริง'],
    'port_scan': ['ตรวจสอบ source/destination IP, ports, จำนวนครั้ง และช่วงเวลาจาก firewall/IDS',
                  'ตรวจสอบว่าเป็น vulnerability scanner ที่ได้รับอนุญาตหรือไม่',
                  'ทบทวนบริการที่เปิดรับและกฎ firewall; ให้ SOC ประเมินก่อนบล็อกต้นทาง'],
}
GENERIC_ACTIONS = ['เก็บรักษา log และเวลาที่พบเหตุการณ์เพื่อให้ SOC ตรวจสอบ',
                   'ตรวจสอบผลกระทบและยืนยันหลักฐานก่อนเปลี่ยนการตั้งค่าหรือแยกเครื่อง']
MAX_LOGS = 100


def classify(message):
    q = message.casefold()
    for kind, terms, events in RULES:
        if any(knowledge_base.matches(q, term) for term in (*terms, *events)):
            return kind, events
    return 'unknown_security_issue', ()


def extract_entities(message):
    ips = set()
    for token in re.findall(r'[0-9a-fA-F:.]+', message):
        try:
            ips.add(str(ipaddress.ip_address(token.strip('.'))))
        except ValueError:
            pass
    host_text = re.sub(r'[\w.+-]+@[\w.-]+', '', message)
    host_text = re.sub(r'\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?', '', host_text)
    host_text = re.sub(r'(?i)\b(?:user(?:name)?|account)(?:\s*[:=]\s*|\s+)[\w.@\\-]+', '', host_text)
    hosts = {h for h in re.findall(r'\b(?:[a-zA-Z0-9]+[-.])+[a-zA-Z0-9-]+\b', host_text)
             if '.' in h or any(c.isdigit() for c in h)}
    hosts.update(re.findall(r'(?i)\b(?:host(?:name)?|server)(?:\s*[:=]\s*|\s+)([\w.-]+)', host_text))
    hosts = {h.casefold() for h in hosts if h not in ips and not re.fullmatch(r'[\d.-]+', h)}
    users = re.findall(r'(?i)\b(?:user(?:name)?|account)(?:\s*[:=]\s*|\s+)([\w.@\\-]+)', message)
    stamps = re.findall(r'\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?)?\b', message)
    valid_stamps = []
    for value in stamps:
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            valid_stamps.append(value)
        except ValueError:
            pass
    return {'ip_addresses': sorted(ips), 'hostnames': sorted(hosts),
            'usernames': sorted(set(users)), 'timestamps': valid_stamps,
            'event_types': sorted({event for _, _, events in RULES for event in events
                                   if knowledge_base.matches(message.casefold(), event.casefold())})}


def analyze(message, db, cid):
    kind, events = classify(message)
    entities = extract_entities(message)
    asset_query = db.query(CustomerAsset).filter(CustomerAsset.company_id == cid)
    identifiers = entities['ip_addresses'] + entities['hostnames']
    if identifiers:
        asset_query = asset_query.filter(or_(CustomerAsset.ip_address.in_(entities['ip_addresses']),
                                            func.lower(CustomerAsset.hostname).in_(entities['hostnames'])))
    assets = asset_query.order_by(CustomerAsset.hostname).limit(21).all()
    # Validate both relationships as well as the log itself, including malformed
    # cross-company foreign keys. The schema does not enforce composite tenancy.
    query = db.query(CustomerLog, CustomerAsset).join(CustomerAsset, CustomerLog.asset_id == CustomerAsset.id).join(
        LogCollector, CustomerLog.collector_id == LogCollector.id).filter(
            CustomerLog.company_id == cid, CustomerAsset.company_id == cid, LogCollector.company_id == cid)
    if events:
        query = query.filter(func.upper(CustomerLog.event_type).in_(events))
    else:
        query = query.filter(False)  # unrelated recent logs are not incident evidence
    if identifiers:
        clauses = [CustomerAsset.ip_address.in_(entities['ip_addresses']),
                   func.lower(CustomerAsset.hostname).in_(entities['hostnames'])]
        # IP may be a source in an unstructured message, not an owned asset.
        clauses += [CustomerLog.message.contains(ip, autoescape=True) for ip in entities['ip_addresses']]
        query = query.filter(or_(*clauses))
    for username in entities['usernames']:
        query = query.filter(CustomerLog.message.contains(username, autoescape=True))
    missing = []
    if entities['timestamps']:
        dates = [datetime.fromisoformat(s.replace('Z', '+00:00')) for s in entities['timestamps']]
        dates = [d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d for d in dates]
        start, end = min(dates), max(dates)
        # Day-only reports search that day; precise times use a 15-minute margin.
        day_only = all(len(s) == 10 for s in entities['timestamps'])
        query = query.filter(CustomerLog.occurred_at >= (start if day_only else start - timedelta(minutes=15)),
                             CustomerLog.occurred_at < end + (timedelta(days=1) if day_only else timedelta(minutes=15)))
        if any(datetime.fromisoformat(s.replace('Z', '+00:00')).tzinfo is None for s in entities['timestamps']):
            missing.append('เวลาที่ไม่ระบุ timezone ถูกตีความเป็น UTC; กรุณายืนยัน timezone')
    else:
        missing.append('ช่วงเวลาและ timezone ของเหตุการณ์ เพื่อยืนยันว่า log ตรงกับเรื่องที่รายงาน')
    rows = query.order_by(CustomerLog.occurred_at.desc(), CustomerLog.id).limit(MAX_LOGS + 1).all()
    truncated = len(rows) > MAX_LOGS
    # Token validation avoids substring matches such as 192.0.2.1 vs .10.
    findings = []
    failed_by_account = Counter()
    for log, asset in rows[:MAX_LOGS]:
        log_entities = extract_entities(log.message)
        if identifiers and not (asset.ip_address in entities['ip_addresses'] or asset.hostname.casefold() in entities['hostnames']
                                or set(entities['ip_addresses']) & set(log_entities['ip_addresses'])):
            continue
        if any(not re.search(r'(?<![\w.@-])' + re.escape(u) + r'(?![\w.@-])', log.message) for u in entities['usernames']):
            continue
        if kind == 'suspicious_login' and log.event_type.upper() in ('FAILED_LOGIN', 'LOGIN_FAILURE'):
            accounts = set(re.findall(
                r'(?i)(?<![\w.-])(?:account|user(?:name)?)\s*[:=]\s*([\w.@\\-]+)',
                log.message,
            ))
            account = next(iter(accounts)) if len(accounts) == 1 else None
            failed_by_account[account] += 1
        findings.append({'log_id': str(log.id), 'asset_id': str(asset.id), 'hostname': asset.hostname,
                         'ip_address': asset.ip_address, 'event_type': log.event_type,
                         'occurred_at': log.occurred_at.isoformat(), 'message': log.message[:300]})
    if not findings:
        missing.append('ไม่พบ log ที่สัมพันธ์กับรายงานในขอบเขตที่ค้นหา; การไม่มีข้อมูลไม่ยืนยันว่าระบบปลอดภัย')
    if not identifiers:
        missing.append('เครื่องหรือ IP ที่เกี่ยวข้อง; ขณะนี้สัมพันธ์กันเพียงประเภทเหตุการณ์ ยังไม่ยืนยันว่าเป็นเหตุเดียวกัน')
    if not entities['usernames'] and kind == 'suspicious_login':
        missing.append('ชื่อบัญชี ผล MFA และมีการเข้าสู่ระบบสำเร็จหลังความล้มเหลวหรือไม่')
    if kind == 'port_scan':
        missing.append('ต้นทาง ปลายทาง พอร์ต จำนวนครั้ง และรายการ scanner ที่ได้รับอนุญาต')
    missing.append('ผลกระทบจริงและหลักฐานเพิ่มเติมเพื่อยืนยันหรือหักล้างการบุกรุก')
    if truncated:
        missing.append('ผลค้นหาจำกัด 100 logs; กรุณาจำกัดช่วงเวลาหรือระบุเครื่องให้ชัดเจน')
    hypotheses = {
        'suspicious_login': 'อาจเป็นการเดารหัสผ่านหรือผู้ใช้กรอกรหัสผิด; ยังยืนยัน account compromise ไม่ได้',
        'port_scan': 'อาจเป็น reconnaissance หรือการสแกนที่ได้รับอนุญาต; ยังยืนยันการเจาะระบบไม่ได้',
    }
    risk = 'UNKNOWN' if not findings else ('HIGH' if kind in ('ransomware', 'data_exfiltration') else 'MEDIUM')
    reasons = ['ไม่มีหลักฐานสัมพันธ์เพียงพอที่จะประเมินระดับความเสี่ยง'] if not findings else [
        f'พบ {len(findings)} log ที่ตรงกับเงื่อนไขค้นหา แต่ event label ไม่ใช่ข้อยืนยันการบุกรุก',
        'ระดับนี้เป็นการคัดกรองเบื้องต้น; ยังไม่ทราบผลกระทบและความสำเร็จของการโจมตี']
    if risk == 'HIGH':
        reasons.append('ประเภท alert อาจกระทบความพร้อมใช้หรือความลับของข้อมูลอย่างรุนแรง จึงควรตรวจสอบเร่งด่วน')
    return {'issue_type': kind, 'entities': entities, 'findings': findings,
            'failed_logins_by_account': [
                {'account': account, 'count': count}
                for account, count in sorted(failed_by_account.items(), key=lambda item: (item[0] is None, item[0] or ''))
            ],
            'assets': [{'id': str(a.id), 'hostname': a.hostname, 'ip_address': a.ip_address} for a in assets[:20]] if identifiers else [],
            'hypotheses': [hypotheses.get(kind, 'รายงานอาจเป็นภัยคุกคามหรือ false positive; ต้องตรวจสอบหลักฐานเพิ่มเติม')],
            'risk': {'level': risk, 'reasons': reasons}, 'recommendations': ACTIONS.get(kind, GENERIC_ACTIONS),
            'missing_information': missing, 'truncated': truncated,
            'correlation': 'entity_and_event' if identifiers else 'event_type_only'}


def safe(value):
    # Render untrusted record fields as inert Markdown text, never links/images.
    return re.sub(r'([\\`*{}\[\]()<>!#|])', r'\\\1', str(value).replace('\n', ' ').replace('\r', ' '))


def render_failed_logins(analysis):
    rows = analysis.get('failed_logins_by_account', [])
    if not rows:
        return ''
    lines = [
        f"- {('บัญชี ' + safe(row['account'])) if row['account'] else 'ไม่ทราบบัญชี'}"
        f" ล็อกอินล้มเหลว {row['count']} ครั้ง"
        for row in rows
    ]
    return '\n\nล็อกอินล้มเหลวจาก Log ที่ตรวจพบ:\n' + '\n'.join(lines)


def render(analysis, documents, advice=None):
    findings = analysis['findings']
    evidence = ['Confirmed evidence (stored records; not confirmation of compromise):']
    evidence += [f"- Asset inventory: {safe(a['hostname'])} [{safe(a['ip_address'])}] (inventory match only)." for a in analysis['assets']]
    evidence += [f"- Log {f['log_id']}: {safe(f['event_type'])} — {safe(f['hostname'])} [{safe(f['ip_address'])}] at {f['occurred_at']} (stored UTC). Record: {safe(f['message'])}" for f in findings[:10]]
    if not findings:
        evidence.append('- ไม่พบหลักฐานที่สัมพันธ์เพียงพอ')
    if len(findings) > 10:
        evidence.append(f'- แสดง 10 จาก {len(findings)} logs ที่สัมพันธ์')
    evidence += ['Hypotheses (unconfirmed):'] + ['- ' + h for h in analysis['hypotheses']]
    actions = '\n'.join('- ' + a for a in analysis['recommendations'])
    if advice:
        actions += '\n\nคำแนะนำทั่วไปจาก Gemini (ไม่ใช่ผลตรวจระบบ):\n' + advice
    actions += '\n\n' + knowledge_base.render(documents)
    sections = [
        ('Incident Summary', f"ประเภทปัญหา: {analysis['issue_type']}\nวิเคราะห์จากรายงานและข้อมูล tenant ที่ได้รับอนุญาต; ไม่ยืนยันการบุกรุกหรือเจ้าของ source IP" + render_failed_logins(analysis)),
        ('Evidence & Findings', '\n'.join(evidence)),
        ('Risk Assessment', analysis['risk']['level'] + '\n' + '\n'.join('- ' + r for r in analysis['risk']['reasons'])),
        ('Recommended Actions', actions),
        ('Missing Information', '\n'.join('- ' + m for m in analysis['missing_information'])),
    ]
    return '\n\n'.join('## ' + title + '\n' + body for title, body in sections)


def render_brief(analysis, documents):
    """Customer summary; raw IDs, timestamps and records require explicit details."""
    findings = analysis['findings']
    risk = {'UNKNOWN': 'ยังประเมินไม่ได้', 'MEDIUM': 'ปานกลาง', 'HIGH': 'สูง'}[analysis['risk']['level']]
    evidence = [f"- {safe(f['event_type'])} บน {safe(f['hostname'])}" for f in findings[:3]]
    if not evidence:
        evidence = ['- ไม่พบ Log ที่สัมพันธ์ในขอบเขตที่ค้นหา การไม่มีข้อมูลไม่ยืนยันว่าระบบปลอดภัย']
    summary = f"พบ {len(findings)} Log ที่ตรงกับเงื่อนไขค้นหา ยังไม่ยืนยันการบุกรุก"
    if analysis['truncated']:
        summary += ' (ผลค้นหาจำกัด 100 รายการ)'
    return ('## สรุปการวิเคราะห์ Log\n' + summary + render_failed_logins(analysis) + '\n\n'
            + '**ความเสี่ยงเบื้องต้น:** ' + risk + ' (' + analysis['risk']['level'] + ')\n\n'
            + '**หลักฐานที่พบในระบบ:**\n' + '\n'.join(evidence) + '\n\n'
            + '**ข้อสันนิษฐาน — ยังไม่ยืนยัน:** ' + analysis['hypotheses'][0] + '\n\n'
            + '**ขั้นตอนถัดไป:**\n' + '\n'.join('- ' + a for a in analysis['recommendations'][:3])
            + knowledge_base.reference_lines(documents))
