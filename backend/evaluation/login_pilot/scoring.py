"""Generate synthetic authentication logs and verify a deterministic rubric."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent
IP_A = "192.0.2.10"
IP_B = "198.51.100.20"


def event(number, minute, account="a.user", ip=IP_A, status="failure"):
    return dict(event_id=f"E{number:02}", timestamp=f"2026-11-13T09:{minute:02}:00+07:00",
                account=account, source_ip=ip, status=status)


def cases():
    failures = [event(i, i) for i in range(1, 6)]
    unknown = "insufficient_evidence"
    yield failures, "บัญชีใดล้มเหลวกี่ครั้ง และยืนยันการยึดบัญชีได้ไหม?", {
        "scope": {"account": "a.user"}, "facts": {"failed_count": 5},
        "interpretation": {"conclusion": unknown}}
    yield failures + [event(6, 6, status="success")], "ระบุจำนวนที่ล้มเหลวและสำเร็จ พร้อมบอกว่าสำเร็จเกิดหลังรายการล้มเหลวหรือไม่", {
        "facts": {"failed_count": 5, "successful_count": 1, "success_after_failure": True}}
    yield failures + [event(6, 6, account="b.user")], "เฉพาะ a.user ล้มเหลวกี่ครั้ง?", {
        "scope": {"account": "a.user"}, "facts": {"failed_count": 5}}
    yield failures + [event(6, 6, ip=IP_B)], "แจกแจงจำนวนครั้งที่ล้มเหลวตาม IP", {
        "facts": {"failures_by_ip": {IP_A: 5, IP_B: 1}}}
    yield failures, "นับการล้มเหลวตั้งแต่ 09:02 ถึงก่อน 09:05 เขตเวลา +07:00", {
        "facts": {"failed_count": 3}}
    yield failures + [failures[0]], "มีรายการล้มเหลวกี่แถว และกี่เหตุการณ์เมื่อไม่นับ event_id ซ้ำ?", {
        "facts": {"failed_rows": 6, "failed_unique": 5}}
    yield [event(1, 1, ip=None)], "ระบุว่าข้อมูล IP ต้นทางหายหรือไม่", {
        "facts": {"source_ip_missing": True}}
    yield [event(1, 1, status="success")], "พบการล็อกอินสำเร็จและล้มเหลวอย่างละกี่ครั้ง?", {
        "facts": {"successful_count": 1, "failed_count": 0}}
    yield failures, "ตามคู่มือที่ให้มา ควรตรวจข้อมูลอะไรเพิ่มก่อนยืนยันการยึดบัญชี?", {
        "next_steps": {"check_success_history": True, "check_mfa_results": True}}
    yield [event(1, 1), event(2, 1, status="success")], "ข้อมูลเวลาที่เท่ากันนี้ยืนยันได้ไหมว่าเหตุการณ์ใดมาก่อน?", {
        "interpretation": {"conclusion": "order_undetermined"}}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def generate():
    for index, (logs, question, dimensions) in enumerate(cases(), 1):
        case_id = f"LOG-{index:03}"
        directory = ROOT / "cases" / case_id
        directory.mkdir(parents=True, exist_ok=True)
        prompt = {"case_id": case_id, "question": question, "logs": logs}
        if index == 9:
            prompt["playbook"] = "ก่อนยืนยันการยึดบัญชี ให้ตรวจประวัติการเข้าสู่ระบบสำเร็จและผล MFA"
        write_json(directory / "input.json", prompt)
        write_json(directory / "ground_truth.json", {
            "case_id": case_id, "dimensions": dimensions,
            "critical": {"conclusion": ["confirmed_compromise", "definitely_safe"]} if index == 1 else {}})


def same_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            same_value(actual[key], value) for key, value in expected.items())
    return actual == expected


def grade(truth, answer):
    checks, scores = {}, {}
    for dimension, expected in truth["dimensions"].items():
        items = {}
        for key, value in expected.items():
            if key not in answer:
                items[key] = "missing"
            else:
                items[key] = "correct" if same_value(answer[key], value) else "wrong"
        statuses = set(items.values())
        checks[dimension] = items
        scores[dimension] = 2 if statuses == {"correct"} else (
            1 if statuses == {"correct", "missing"} else 0)
    critical = [key for key, values in truth["critical"].items() if answer.get(key) in values]
    passed = not critical and all(score == 2 for score in scores.values())
    return dict(status="pass" if passed else "fail", checks=checks, scores=scores,
                score=sum(scores.values()), maximum=2 * len(scores), critical=critical)


def self_test():
    truth = read_json(ROOT / "cases/LOG-001/ground_truth.json")
    base = dict(account="a.user", failed_count=5, conclusion="insufficient_evidence")
    tests = [
        ("correct", base, "pass", 6),
        ("missing_conclusion", {k: v for k, v in base.items() if k != "conclusion"}, "fail", 4),
        ("wrong_count", dict(base, failed_count=4), "fail", 4),
        ("unsupported_conclusion", dict(base, conclusion="confirmed_compromise"), "fail", 4),
    ]
    ninth = read_json(ROOT / "cases/LOG-009/ground_truth.json")
    assert grade(ninth, {"check_mfa_results": True})["score"] == 1
    for name, answer, status, score in tests:
        result = grade(truth, answer)
        assert (result["status"], result["score"]) == (status, score), (name, result)
        assert bool(result["critical"]) == (name == "unsupported_conclusion")
        print(name, result["status"], f'{result["score"]}/{result["maximum"]}')


def report(responses, output):
    supplied = read_json(responses)
    if not isinstance(supplied, dict):
        raise ValueError("Responses must map case IDs to records")
    rows = []
    paths = sorted((ROOT / "cases").glob("LOG-*/ground_truth.json"))
    if not paths:
        raise ValueError("Generate the dataset before scoring")
    unknown = supplied.keys() - {path.parent.name for path in paths}
    if unknown:
        raise ValueError(f"Unknown case IDs: {sorted(unknown)}")
    for path in paths:
        truth = read_json(path)
        case_id = truth["case_id"]
        entry = supplied.get(case_id)
        if entry is None:
            result = {"status": "not_run"}
        elif not isinstance(entry, dict):
            result = {"status": "unscorable"}
        elif entry.get("system_error"):
            result = {"status": "system_error", "reason": entry["system_error"]}
        elif isinstance(entry.get("fields"), dict):
            result = grade(truth, entry["fields"])
        else:
            result = {"status": "unscorable"}
        rows.append(dict(case_id=case_id, response=entry, **result))
    with output.open("x", encoding="utf-8-sig", newline="") as stream:
        fields = ["case_id", "status", "score", "maximum", "checks", "scores", "critical",
                  "reason", "response"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False)
                             if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate")
    sub.add_parser("self-test")
    scorer = sub.add_parser("score")
    scorer.add_argument("responses", type=Path)
    scorer.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        generate()
    elif args.command == "self-test":
        self_test()
    else:
        report(args.responses, args.output)


if __name__ == "__main__":
    main()
