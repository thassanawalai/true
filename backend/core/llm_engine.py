import os
import json
import google.generativeai as genai
from sqlalchemy.orm import Session
from models.models import Ticket
from rag.vector_db import search_knowledge
from services.ticket_service import create_ticket_from_ai

# 1. Initialize Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# 2. Define Tools using Gemini's Schema format
soc_tools = [
    {
        "function_declarations": [
            {
                "name": "search_documents",
                "description": "Use this tool to search the internal security knowledge base, SOC playbooks, or incident response guides.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "The search keyword."}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_ticket_status",
                "description": "Check the current status of an existing security incident ticket.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "ticket_id": {"type": "STRING", "description": "The unique ticket number or ID."}
                    },
                    "required": ["ticket_id"]
                }
            },
            {
                "name": "create_new_ticket",
                "description": "CRITICAL: Use this tool to open a new security incident ticket.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "issue_description": {"type": "STRING", "description": "A clear description of the security incident."}
                    },
                    "required": ["issue_description"]
                }
            },
            {
                "name": "get_user_tickets",
                "description": "List all recent tickets in the system when the user asks 'What are my tickets?'.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            }
        ]
    }
]

def generate_ai_response(user_message: str, db: Session) -> dict:
    system_prompt = """
    You are an elite AI Support Assistant for a Security Operations Center (SOC).
    Your primary responsibility is to facilitate security operations with precision, utmost professionalism, and proactive incident response.

    Strict Operating Guidelines:
    1. CONCISE RESPONSE: Be extremely concise and direct. Use short paragraphs. Hide complex internal analysis from the user. NEVER omit critical security warnings.
    2. GUIDED TROUBLESHOOTING (ONE STEP AT A TIME): NEVER ask a list of 3-5 questions at once. Ask ONLY ONE logical question at a time. Adapt your first question based on the specific incident type (e.g., for EDR failures, ask about the OS or error codes; for logins, ask for user verification).
    3. AUTONOMOUS TOOL EXECUTION: If a user's request matches a tool's capability, YOU MUST CALL THE TOOL IMMEDIATELY. NEVER ask "Should I search the playbook?". Just execute it.
    4. INCIDENT TRIAGE & ESCALATION: Guide the user step-by-step. If an incident is critical or the user denies the action, advise immediate containment and utilize `create_new_ticket`.
    5. DATA INTEGRITY: Do not invent or hallucinate data. Base responses strictly on verified tool outputs.
    6. TONE: Maintain a formal, objective, and professional tone. Respond in the exact same language as the user's prompt.
    """

    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash-lite",
            tools=soc_tools,
            system_instruction=system_prompt
        )

        chat = model.start_chat()
        
        # Step 1: Send user message to Gemini
        response = chat.send_message(user_message)
        
        # Step 2: Intercept Tool Call if Gemini decides to use one
        if response.parts and response.parts[0].function_call:
            function_call = response.parts[0].function_call
            tool_name = function_call.name
            
            # Extract arguments
            arguments = type(function_call).to_dict(function_call).get('args', {})
            tool_result_content = ""
            
            # Step 3: Execute Database/RAG Logic
            if tool_name == "get_user_tickets":
                recent_tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(5).all()
                if recent_tickets:
                    ticket_lines = [f"- {t.ticket_number}: {t.subject} (Status: {t.status}, Priority: {t.priority})" for t in recent_tickets]
                    tool_result_content = "Here are the recent tickets:\n" + "\n".join(ticket_lines)
                else:
                    tool_result_content = "No tickets found."

            elif tool_name == "get_ticket_status":
                ticket_id = arguments.get("ticket_id", "")
                ticket = db.query(Ticket).filter(Ticket.ticket_number.ilike(f"%{ticket_id}%")).first()
                if ticket:
                    tool_result_content = f"Ticket {ticket.ticket_number} ('{ticket.subject}') is currently marked as {ticket.status}."
                else:
                    tool_result_content = f"Could not find any ticket matching ID: {ticket_id}."
            
            elif tool_name == "create_new_ticket":
                tool_result_content = "System instruction: Please instruct the user to use the 'Create Ticket' button in the UI to ensure accurate Impact and Urgency matrix calculation."
                
            elif tool_name == "search_documents":
                search_query = arguments.get("query", "")
                rag_results = search_knowledge(query=search_query, user_company="True Digital Group (Demo)")
                if rag_results:
                    extracted_texts = [doc.page_content for doc in rag_results]
                    tool_result_content = "Found relevant playbook information:\n\n" + "\n---\n".join(extracted_texts)
                else:
                    tool_result_content = "No relevant playbook documents found for this query in the knowledge base."
            elif tool_name == "create_new_ticket":
                issue_description = arguments.get("issue_description", "No description provided.")
                
                ticket_result = create_ticket_from_ai(db=db, issue_description=issue_description)
                
                if ticket_result.get("success"):
                    ticket_no = ticket_result["ticket_number"]
                    priority = ticket_result["priority"]
                    tool_result_content = f"Successfully created ticket {ticket_no} with {priority} priority. The SOC team has been notified."
                else:
                    error_msg = ticket_result.get("error")
                    tool_result_content = f"Failed to create ticket due to database error: {error_msg}. Please contact support directly."

            # Step 4: Feed the tool result back to Gemini to get the final human-readable response
            response = chat.send_message(
                {
                    "function_response": {
                        "name": tool_name,
                        "response": {"result": tool_result_content}
                    }
                }
            )
            
            return {"status": "success", "reply": response.text}
            
        else:
            # Normal conversational response without tools
            return {"status": "success", "reply": response.text}
            
    except Exception as e:
        print(f"[DEBUG] Gemini Error: {str(e)}")
        return {"status": "error", "reply": f"Gemini AI Engine Error: {str(e)}"}