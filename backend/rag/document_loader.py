def get_mock_knowledge_base():
    """
    Return the mock knowledge base used by the RAG system.

    Each document includes an access control rule that determines
    which company is authorized to access the document.
    """

    return [
        {
            "doc_id": "KB-001",
            "keywords": ("log loss", "logs stopped", "ล็อกหาย", "log หาย", "ไม่ได้รับ log"),
            "title": "Basic Log Loss Troubleshooting",
            "content": (
                "If a Log Loss issue occurs and data is not being received, "
                "check the firewall connection and verify that the Log Server "
                "has sufficient available disk space."
            ),
            "allowed_company": "ALL",  # General document accessible to all companies
        },
        {
            "doc_id": "KB-002",
            "keywords": ("dashboard port", "dashboard access", "network architecture", "8081", "พอร์ต dashboard"),
            "title": "Customer A Network Architecture Guide",
            "content": (
                "For Customer A, always use port 8081 to access the Dashboard. "
                "The primary server is located in Zone B."
            ),
            "allowed_company": "Customer A",  # Confidential information for Customer A
        },
        {
            "doc_id": "KB-003",
            "keywords": ("password reset", "reset password", "รีเซ็ตรหัสผ่าน"),
            "title": "Customer Y Password Reset Procedure",
            "content": (
                "Users of the Customer Y system must complete identity "
                "verification through the 2FA application before resetting "
                "their password."
            ),
            "allowed_company": "Customer Y",  # Confidential information for Customer Y
        },
        {
            "doc_id": "KB-004",
            "title": "Company B Demo Dashboard Recovery",
            "keywords": ("dashboard port", "dashboard access", "network architecture", "9443", "พอร์ต dashboard"),
            "content": "In the Company B exercise, the recovery dashboard is reached on port 9443.",
            "allowed_company": "Customer B",
        },
        {
            "doc_id": "KB-005",
            "title": "Phishing Response Playbook",
            "keywords": ("phishing playbook", "report phishing", "phishing email", "อีเมลฟิชชิง", "ฟิชชิง"),
            "content": (
                "Report a suspected phishing email to the SOC using the reporting channel. "
                "Preserve the original message and headers. Avoid opening links or attachments. "
                "If credentials were entered, report that fact to the SOC immediately."
            ),
            "allowed_company": "ALL",
        },
    ]
