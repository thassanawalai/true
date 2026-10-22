import os

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from models.models import Ticket
from rag.vector_db import search_knowledge
from services.ticket_service import create_ticket_from_ai


SYSTEM_PROMPT = """You are an AI Support Assistant for a Security Operations Center (SOC).
Respond in the same language as the user. Be concise and professional.
For incident triage, ask only one focused question at a time. Use search_documents
for questions about response procedures. Never claim a ticket was created unless
create_new_ticket returns a successful ticket number. Escalate critical incidents.
Use only information returned by tools when describing playbook or ticket data."""

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
COMPANY_NAME = "True Digital Group (Demo)"

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="search_documents",
            description="Search internal SOC playbooks for incident response guidance.",
            parameters_json_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        types.FunctionDeclaration(
            name="create_new_ticket",
            description="Create a database ticket for a security incident requiring SOC follow-up.",
            parameters_json_schema={
                "type": "object",
                "properties": {"issue_description": {"type": "string"}},
                "required": ["issue_description"],
            },
        ),
        types.FunctionDeclaration(
            name="get_ticket_status",
            description="Look up a ticket by its INC number.",
            parameters_json_schema={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            },
        ),
        types.FunctionDeclaration(
            name="get_user_tickets",
            description="List the latest tickets in this demo system.",
            parameters_json_schema={"type": "object", "properties": {}},
        ),
    ])
]


def _run_tool(name: str, args: dict, db: Session) -> str:
    if name == "search_documents":
        results = search_knowledge(
            query=args.get("query", ""), user_company=COMPANY_NAME, k=3
        )
        if not results:
            return "No relevant playbook passages were found."
        return "Relevant playbook passages:\n\n" + "\n---\n".join(
            doc.page_content for doc in results
        )

    if name == "create_new_ticket":
        result = create_ticket_from_ai(db, args.get("issue_description", "Incident reported by user."))
        if result["success"]:
            return (
                f"Ticket {result['ticket_number']} created successfully. "
                f"Priority: {result['priority']}; status: OPEN."
            )
        return f"Ticket creation failed: {result['error']}"

    if name == "get_ticket_status":
        ticket_id = args.get("ticket_id", "").strip()
        ticket = db.query(Ticket).filter(Ticket.ticket_number == ticket_id).first()
        if not ticket:
            return f"No ticket found for {ticket_id}."
        return f"{ticket.ticket_number}: {ticket.subject}; status {ticket.status}; priority {ticket.priority.value}."

    if name == "get_user_tickets":
        tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(5).all()
        if not tickets:
            return "There are no tickets yet."
        return "Recent tickets:\n" + "\n".join(
            f"{t.ticket_number}: {t.subject} ({t.status}, {t.priority.value})" for t in tickets
        )

    return f"Unsupported tool: {name}"


def generate_ai_response(user_message: str, db: Session, history: list[dict] | None = None) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"status": "error", "reply": "GEMINI_API_KEY is not configured."}

    client = genai.Client(api_key=api_key)
    contents = [
        types.Content(
            role="model" if item["role"] == "assistant" else "user",
            parts=[types.Part(text=item["content"])],
        )
        for item in (history or [])
        if item.get("content", "").strip()
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=TOOLS)

    try:
        for _ in range(3):
            response = client.models.generate_content(
                model=MODEL_NAME, contents=contents, config=config
            )
            candidate = response.candidates[0]
            calls = [part.function_call for part in candidate.content.parts if part.function_call]
            if not calls:
                return {"status": "success", "reply": response.text or "ขออภัย ระบบยังไม่มีคำตอบในขณะนี้"}

            contents.append(candidate.content)
            function_responses = []
            for call in calls:
                result = _run_tool(call.name, dict(call.args or {}), db)
                function_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=call.name,
                            response={"result": result},
                            id=call.id,
                        )
                    )
                )
            contents.append(types.Content(role="user", parts=function_responses))

        return {"status": "error", "reply": "The assistant exceeded the tool-call limit for this turn."}
    except Exception as exc:
        print(f"[Gemini] {type(exc).__name__}: {exc}")
        return {"status": "error", "reply": f"Gemini request failed: {exc}"}
