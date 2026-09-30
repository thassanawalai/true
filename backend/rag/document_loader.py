def get_mock_knowledge_base():
    """
    Return the mock knowledge base used by the RAG system.

    Each document includes an access control rule that determines
    which company is authorized to access the document.
    """

    return [
        {
            "doc_id": "KB-001",
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
            "title": "Customer A Network Architecture Guide",
            "content": (
                "For Customer A, always use port 8081 to access the Dashboard. "
                "The primary server is located in Zone B."
            ),
            "allowed_company": "Customer A",  # Confidential information for Customer A
        },
        {
            "doc_id": "KB-003",
            "title": "Customer Y Password Reset Procedure",
            "content": (
                "Users of the Customer Y system must complete identity "
                "verification through the 2FA application before resetting "
                "their password."
            ),
            "allowed_company": "Customer Y",  # Confidential information for Customer Y
        },
    ]