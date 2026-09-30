from datetime import datetime, timedelta

now = datetime.now()
time_1h_ago = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
time_4h_ago = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
time_1d_ago = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
time_plus_2h = (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
time_minus_1h = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

mock_tickets = [
    # ---------------------------------------------------------
    # เคสที่ 1: Critical Incident - Ransomware (ใกล้หมดเวลา SLA)
    # ---------------------------------------------------------
    {
        "ticket_ref": "I-002269", 
        "ticket_type": "Incident",
        "status": "assigned",   
        "impact": "1 - High",
        "urgency": "1 - High",
        "priority": "1 - Critical",
        "subject": "CrowdStrike malware alert on Server 01",
        "description": "CrowdStrike Falcon detected a malicious payload (Ransomware.WannaCry) on SRV-PROD-01. Host has been isolated. Immediate remediation required.",
        "service_name": "Endpoint Security", 
        "caller_name": "System Alert",
        "assignee_team": "SOC Tier 2",
        "assignee_agent": "Somchai Jaidee",
        "start_date": time_1h_ago,
        "last_update": time_1h_ago,
        "sla_due_date": time_plus_2h,
        "sla_status": "In Target"
    },
    # ---------------------------------------------------------
    # เคสที่ 2: High Incident - Phishing Campaign (เกินเวลา SLA แล้ว - Breached)
    # ---------------------------------------------------------
    {
        "ticket_ref": "I-002270", 
        "ticket_type": "Incident",
        "status": "in_progress",   
        "impact": "2 - Medium",
        "urgency": "1 - High",
        "priority": "2 - High",
        "subject": "Mass Phishing Email Campaign Detected",
        "description": "Multiple users reported receiving emails claiming to be from IT regarding password expiry. Malicious link leads to credential harvesting site.",
        "service_name": "Email Security", 
        "caller_name": "Multiple Users",
        "assignee_team": "SOC Tier 1",
        "assignee_agent": "Somsri Secure",
        "start_date": time_4h_ago,
        "last_update": time_1h_ago,
        "sla_due_date": time_minus_1h, 
        "sla_status": "Breached"
    },
    # ---------------------------------------------------------
    # เคสที่ 3: Normal Request - VPN Issue (สถานะ Pending)
    # ---------------------------------------------------------
    {
        "ticket_ref": "R-001001",   
        "ticket_type": "UserRequest",
        "status": "pending",
        "impact": "3 - Low",
        "urgency": "3 - Medium",
        "priority": "3 - Normal",
        "subject": "Cannot connect to Corporate VPN (Error 809)",
        "description": "User is unable to establish a VPN connection from home network. Attempted troubleshooting with IPSec settings but issue persists.",
        "service_name": "Network Access",
        "caller_name": "Wichai Networker",
        "assignee_team": "IT Helpdesk",
        "assignee_agent": "Unassigned",
        "start_date": time_1d_ago,
        "last_update": time_1d_ago,
        "sla_due_date": (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "sla_status": "In Target"
    },
    # ---------------------------------------------------------
    # เคสที่ 4: Normal Request - Firewall Rule (รอการอนุมัติ)
    # ---------------------------------------------------------
    {
        "ticket_ref": "R-001005",   
        "ticket_type": "UserRequest",
        "status": "waiting_approval",
        "impact": "2 - Medium",
        "urgency": "3 - Medium",
        "priority": "3 - Normal",
        "subject": "Request to whitelist new payment gateway IP",
        "description": "Need to open port 443 on the perimeter firewall for the new external payment gateway APIs.",
        "service_name": "Network Security",
        "caller_name": "DevOps Team",
        "assignee_team": "Security Architecture",
        "assignee_agent": "Unassigned",
        "start_date": time_1d_ago,
        "last_update": time_1h_ago,
        "sla_due_date": (now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
        "sla_status": "In Target"
    },
    # ---------------------------------------------------------
    # เคสที่ 5: Low Request - Software License (แก้ไขเสร็จแล้ว)
    # ---------------------------------------------------------
    {
        "ticket_ref": "R-001002",
        "ticket_type": "UserRequest",
        "status": "resolved",
        "impact": "3 - Low",
        "urgency": "4 - Low",
        "priority": "4 - Low",
        "subject": "Request software license for Splunk Enterprise",
        "description": "Need a license to access Splunk Enterprise for log analysis of the new web application project.",
        "service_name": "Software Provisioning",
        "caller_name": "Suda Data",
        "assignee_team": "Security Architecture",
        "assignee_agent": "Malee Admin",
        "start_date": (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
        "last_update": now.strftime("%Y-%m-%d %H:%M:%S"),
        "sla_due_date": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "sla_status": "In Target"
    }
]