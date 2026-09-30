def search_documents(query: str) -> str:
    """
    Use this tool to search the internal security knowledge base, SOC playbooks, or incident response guides.
    Always use this tool first when investigating a security alert or answering a technical question.
    
    Args:
        query: The search keyword (e.g., 'CrowdStrike malware containment').
    """
    pass

def get_ticket_status(ticket_id: str) -> str:
    """
    Use this tool to check the current status of an existing security incident ticket in the iTop system.
    
    Args:
        ticket_id: The unique identifier of the ticket (e.g., '1002').
    """
    pass

def create_new_ticket(issue_description: str) -> str:
    """
    CRITICAL: Use this tool to open a new security incident ticket in the iTop system.
    You MUST execute this tool IMMEDIATELY when the user explicitly asks to 'open a ticket', 
    or when they report a critical security breach (e.g., Malware, CrowdStrike alerts, Phishing).
    
    Args:
        issue_description: A clear description of the security incident (e.g., 'CrowdStrike malware alert on Server 01').
    """
    pass

def search_web(query: str) -> str:
    """
    Use this tool to search the public internet for threat intelligence, CVEs, or external security documentation.
    
    Args:
        query: The search query to look up on the internet.
    """
    pass

def generate_report_html(report_title: str, summary_data: str) -> str:
    """
    Use this tool to generate an HTML dashboard report for security summaries or incident wrap-ups.
    
    Args:
        report_title: The title of the dashboard report.
        summary_data: The summarized security data to be displayed.
    """
    pass

# ==========================================
# List of all tools to be provided to the LLM
# ==========================================
SOC_TOOLS = [
    search_documents,
    get_ticket_status,
    create_new_ticket,
    search_web,
    generate_report_html
]