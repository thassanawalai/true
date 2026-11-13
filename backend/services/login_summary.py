"""Authentication facts derived only from the selected tenant log rows."""
import ipaddress
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

FAILED = {'FAILED_LOGIN', 'LOGIN_FAILURE'}
SUCCESS = {'LOGIN_SUCCESS', 'SUCCESSFUL_LOGIN', 'LOGIN_SUCCESSFUL'}
ACCOUNT = r'(?i)(?:(?<![\w.-])(?:account|username|user)\b|บัญชี(?:ผู้ใช้)?|เฉพาะ)(?:\s*[:=]\s*|\s+)([A-Za-z0-9_][\w.@\\-]*)'


def accounts(text):
    return sorted(set(re.findall(ACCOUNT, text)))


def exact_window(message):
    """Explicit time ranges with one calendar date and numeric timezone."""
    day = re.search(r'\b\d{4}-\d{2}-\d{2}\b', message)
    interval = re.search(r'(?:ตั้งแต่|from)\s*(\d{2}:\d{2})\s*(ถึงก่อน|ก่อน|ถึง|until|to)\s*(\d{2}:\d{2})', message, re.I)
    zone = re.search(r'(?:timezone|เขตเวลา|UTC)\s*([+-]\d{2}:\d{2})', message, re.I)
    if not (day and interval and zone):
        return None
    try:
        start = datetime.fromisoformat(day[0] + 'T' + interval[1] + ':00' + zone[1])
        end = datetime.fromisoformat(day[0] + 'T' + interval[3] + ':00' + zone[1])
    except ValueError:
        return None
    if end < start:
        end += timedelta(days=1)
    return (start.astimezone(timezone.utc).replace(tzinfo=None),
            end.astimezone(timezone.utc).replace(tzinfo=None),
            interval[2].lower() in {'ถึง', 'to'})


def summarize(rows, truncated):
    failed, successful = [], []
    for log, asset in rows:
        if log.event_type.upper() in FAILED:
            failed.append(log)
        elif log.event_type.upper() in SUCCESS:
            successful.append(log)
    by_account, by_ip = Counter(), Counter()
    missing_ip = 0
    unique, unknown_ids = set(), 0
    for log in failed:
        names = accounts(log.message)
        by_account[names[0] if len(names) == 1 else None] += 1
        source = re.search(r'(?i)\b(?:source_ip|src_ip|src)\s*[:=]\s*([^\s,;]+)', log.message)
        try:
            address = str(ipaddress.ip_address(source[1])) if source else None
        except ValueError:
            address = None
        if address:
            by_ip[address] += 1
        else:
            missing_ip += 1
        event_id = re.search(r'(?i)\b(?:event_id|source_event_id)\s*[:=]\s*([\w.-]+)', log.message)
        if event_id:
            unique.add((str(log.collector_id), str(log.asset_id), event_id[1]))
        else:
            unknown_ids += 1
    pairs = []
    tied = False
    for failure in failed:
        failure_accounts = accounts(failure.message)
        if len(failure_accounts) != 1:
            continue
        for success in successful:
            if failure.asset_id == success.asset_id and accounts(success.message) == failure_accounts:
                pairs.append(success.occurred_at > failure.occurred_at)
                tied |= success.occurred_at == failure.occurred_at
    return {
        'failed_count': len(failed), 'failed_rows': len(failed),
        'successful_count': len(successful),
        'failed_unique': len(unique) if not unknown_ids else None,
        'missing_event_id_rows': unknown_ids,
        'failures_by_ip': dict(sorted(by_ip.items())),
        'missing_source_ip_rows': missing_ip,
        'source_ip_missing': missing_ip > 0,
        'by_account': [{'account': k, 'count': v} for k, v in
                       sorted(by_account.items(), key=lambda item: item[0] or '')],
        'success_after_failure': any(pairs) if pairs else None,
        'same_timestamp': tied, 'truncated': truncated,
    }
