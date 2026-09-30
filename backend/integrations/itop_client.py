import random
from datetime import datetime, timedelta

def get_ticket_from_itop(ticket_id: str, user_company: str) -> dict:
    """
    Retrieve ticket information from the iTop system.
    This function currently uses a mock database to simulate communication with the iTop service.
    """
    print(f"[System Log] Retrieving ticket: {ticket_id} | Company access scope: {user_company}")

    mock_db = {
        "1001": {
            "status": "In Progress",
            "company": "Customer A",
            "issue": "Log Loss",
            "priority": "High",
        },
        "1002": {
            "status": "Resolved",
            "company": "Customer Y",
            "issue": "Cannot login",
            "priority": "Medium",
        },
    }

    ticket = mock_db.get(ticket_id)

    if not ticket:
        return {
            "success": False,
            "message": f"Ticket {ticket_id} was not found in the system.",
        }

    if ticket["company"] != user_company:
        return {
            "success": False,
            "message": f"Access denied. You are not authorized to access ticket {ticket_id}.",
        }

    return {
        "success": True,
        "data": ticket,
    }

def create_ticket_in_itop(issue_description: str, user_company: str) -> dict:
    """
    Create a new ticket in the iTop system.
    This function currently simulates ticket creation using a randomly generated ticket ID.
    """
    print(f"[System Log] Creating new ticket | Company: {user_company} | Issue: {issue_description}")

    # Generate a random ticket ID to simulate ticket creation.
    new_ticket_id = str(random.randint(2000, 2999))

    return {
        "success": True,
        "ticket_id": new_ticket_id,
        "message": f"The issue '{issue_description}' has been successfully submitted. Your ticket ID is {new_ticket_id}.",
    }

def get_all_tickets_from_itop(company_name: str, status_filter: str = "open") -> dict:
    now = datetime.now()
    time_2h_ago = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    time_1d_ago = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    time_3d_ago = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    mock_tickets = [
        {
            "ticket_ref": "I-002269", 
            "ticket_type": "Incident",
            "status": "assigned",   
            "priority": "1 - Critical",
            "urgency": "1 - High",
            "subject": "CrowdStrike malware alert on Server 01",
            "description": "CrowdStrike Falcon detected a malicious payload (Ransomware.WannaCry) on SRV-PROD-01. Host has been isolated from the network.",
            "service_name": "Endpoint Security", 
            "caller_name": "System Alert",
            "assignee_team": "SOC Tier 2",
            "assignee_agent": "Somchai Jaidee",
            "start_date": time_2h_ago,
            "last_update": time_2h_ago
        },
        {
            "ticket_ref": "R-001001",   
            "ticket_type": "UserRequest",
            "status": "pending",
            "priority": "3 - Normal",
            "urgency": "3 - Medium",
            "subject": "Cannot connect to Corporate VPN (Error 809)",
            "description": "User is unable to establish a VPN connection from home network. Attempted troubleshooting with IPSec settings but issue persists.",
            "service_name": "Network Access",
            "caller_name": "Wichai Networker",
            "assignee_team": "IT Helpdesk",
            "assignee_agent": "Unassigned",
            "start_date": time_1d_ago,
            "last_update": time_1d_ago
        },
        {
            "ticket_ref": "R-001002",
            "ticket_type": "UserRequest",
            "status": "resolved",
            "priority": "4 - Low",
            "urgency": "4 - Low",
            "subject": "Request software license for Splunk Enterprise",
            "description": "Need a license to access Splunk Enterprise for log analysis of the new web application project.",
            "service_name": "Software Provisioning",
            "caller_name": "Suda Data",
            "assignee_team": "Security Architecture",
            "assignee_agent": "Malee Admin",
            "start_date": time_3d_ago,
            "last_update": now.strftime("%Y-%m-%d %H:%M:%S")
        }
    ]
    filtered_tickets = mock_tickets
    if status_filter.lower() != "all":
        if status_filter.lower() == "open":
            valid_statuses = ["new", "assigned", "pending"]
            filtered_tickets = [t for t in mock_tickets if t["status"] in valid_statuses]
        else:
            filtered_tickets = [t for t in mock_tickets if t["status"] == status_filter.lower()]

    return {
        "organization": company_name,
        "total_filtered_results": len(filtered_tickets),
        "status_filter_applied": status_filter,
        "tickets": filtered_tickets
    }