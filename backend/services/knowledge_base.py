"""Small local keyword/tag KB. Authorization precedes scoring, never semantic search."""
import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from uuid import UUID

CATALOG = Path(__file__).resolve().parents[1] / 'data' / 'soc_knowledge.json'
MAX_RESULTS = 2


def fingerprint(document):
    return hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


# Public content reviewed for outbound use. Update explicitly after source review;
# a new/edited document or a private document must not silently leave the server.
APPROVED_PUBLIC_DIGESTS = {
    'KB-001': '5d6bf97d202ae5269139b6087816e3e00d4845b3ea31de75180c70eb2a4d5b5e',
    'KB-002': '104a53befe5a14ef58eca5ba657adf27573cef18efb984a3b96d41c1440ae2b4',
    'KB-003': '331311c2b3e9205d49261d32af78808cb6865525f26f73b581ca571945d26995',
    'KB-004': 'a5e821d7c42c8166dda273d5900e3e823bb73e30395c7d77beb71509f349cf26',
    'KB-005': 'da9298df2ca815216006184d71c7a3eec5240653be32e8cf78ac846bb6db62d3',
    'KB-006': 'cbd2f492ef1addf543a3ec6eb3569e9bba735a6dc382fcdcda43c84cf35191c4',
    'KB-007': 'c3355a168e102cb04d68262f18cd9313b84e0d13e5327ee4b9a9eee1b6d8e8cb',
    'KB-008': 'bb1b8d8472cfbf72f31338bac8b29af032a21b47c93241504719ee80effae914',
    'KB-009': '2f486685849ba6530f804d662b6ba3a5f4baf3cbc630be38a393d9a33c33acc8',
    'KB-010': 'a379de17b10c4a4ab1a07f281cd6fbd645dd695401874e6bb9deeba7f242a269',
}


@lru_cache(maxsize=1)
def _catalog():
    documents = json.loads(CATALOG.read_text(encoding='utf-8'))
    ids = set()
    for doc in documents:
        if (not re.fullmatch(r'KB-\d{3}', doc['id']) or doc['id'] in ids
                or doc['scope'] not in ('public', 'company')
                or not doc['tags'] or not all(isinstance(t, str) and t.strip() for t in doc['tags'])
                or not doc['content'] or len(doc['content']) > 800
                or not doc['source']['url'].startswith('https://')):
            raise ValueError('Invalid KB catalog')
        if doc['scope'] == 'company':
            UUID(doc['company_id'])
        elif doc.get('company_id') is not None:
            raise ValueError('Public KB must not have a company owner')
        ids.add(doc['id'])
    return documents


def matches(query, tag):
    tag = unicodedata.normalize('NFKC', tag).casefold()
    # ASCII word boundaries prevent "ip" matching "phishing"; Thai uses substring
    # matching because no tokenizer/dependency is introduced.
    if tag.isascii():
        return bool(re.search(r'(?<![a-z0-9_])' + re.escape(tag) + r'(?![a-z0-9_])', query))
    return tag in query


def retrieve(message, company_id, *, documents=None):
    """company_id must already be authorized by the API's authorized_company().

    documents is an offline-test seam; HTTP clients cannot supply a catalog.
    Fail closed for unknown scopes. Only authorized documents reach matches().
    """
    cid = str(UUID(str(company_id)))
    catalog = _catalog() if documents is None else documents
    allowed = [d for d in catalog if
               (d.get('scope') == 'public' and d.get('company_id') is None)
               or (d.get('scope') == 'company' and d.get('company_id') == cid)]
    query = unicodedata.normalize('NFKC', message[:1000]).casefold()
    scored = [(sum(2 if ' ' in tag else 1 for tag in set(d['tags']) if matches(query, tag)), d)
              for d in allowed]
    ranked = sorted(((score, doc) for score, doc in scored if score), key=lambda item: (-item[0], item[1]['id']))
    # Copies prevent callers from mutating the cached catalog.
    return json.loads(json.dumps([doc for _, doc in ranked[:MAX_RESULTS]]))


def public_context(documents):
    """Only exact reviewed public catalog content may be added to Gemini input."""
    return [{'id': d['id'], 'title': d['title'], 'content': d['content']}
            for d in documents if d.get('scope') == 'public' and d.get('company_id') is None
            and APPROVED_PUBLIC_DIGESTS.get(d['id']) == fingerprint(d)]


def citations(documents):
    return [{'id': d['id'], 'title': d['title'], 'source': dict(d['source'])} for d in documents]


def render(documents):
    if not documents:
        return 'ไม่พบเอกสาร KB ที่ตรงกับคำถามในขอบเขตสิทธิ์ จึงยังมีหลักฐานไม่เพียงพอที่จะสรุปเหตุการณ์ กรุณาระบุประเภทเหตุการณ์หรือให้ SOC ตรวจสอบเพิ่มเติม'
    return 'ความรู้ประกอบจาก KB (คำแนะนำทั่วไป ไม่ใช่หลักฐานเหตุการณ์):\n' + '\n\n'.join(
        f"[{d['id']}] {d['title']}\n{d['content']}\nแหล่งอ้างอิง: [{d['source']['title']}]({d['source']['url']})"
        for d in documents)


def reference_lines(documents):
    if not documents:
        return ''
    return '\n\n### แหล่งอ้างอิง\n' + '\n'.join(
        f"- [{d['id']}] [{d['source']['title']}]({d['source']['url']})" for d in documents)


def render_conversation(documents):
    if not documents:
        return ('ยังไม่พบคำแนะนำที่ตรงกับคำถามใน KB ค่ะ ลองระบุเรื่องที่ต้องการทราบ เช่น phishing, MFA หรือ log หาย'
                '\n\nยังมีหลักฐานไม่เพียงพอที่จะสรุปเหตุการณ์ และการไม่มีข้อมูลไม่ยืนยันว่าระบบปลอดภัย')
    return documents[0]['content'] + reference_lines(documents)
