import os
import json
from groq import Groq

# 1. JSON Schema Groq / OpenAI
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Use this tool to search the internal security knowledge base, SOC playbooks, or incident response guides. Always use this tool first when investigating a security alert or answering a technical question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search keyword (e.g., 'CrowdStrike malware containment')."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticket_status",
            "description": "Use this tool to check the current status of an existing security incident ticket in the iTop system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The unique identifier of the ticket (e.g., '1002')."
                    }
                },
                "required": ["ticket_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_new_ticket",
            "description": "CRITICAL: Use this tool to open a new security incident ticket in the iTop system. You MUST execute this tool IMMEDIATELY when the user explicitly asks to 'open a ticket', or when they report a critical security breach.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_description": {
                        "type": "string",
                        "description": "A clear description of the security incident (e.g., 'CrowdStrike malware alert on Server 01')."
                    }
                },
                "required": ["issue_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Use this tool to search the public internet for threat intelligence, CVEs, or external security documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the internet."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report_html",
            "description": "Use this tool to generate an HTML dashboard report for security summaries or incident wrap-ups.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_title": {
                        "type": "string",
                        "description": "The title of the dashboard report."
                    },
                    "summary_data": {
                        "type": "string",
                        "description": "The summarized security data to be displayed."
                    }
                },
                "required": ["report_title", "summary_data"]
            }
        }
    }
    ,
    {
        "type": "function",
        "function": {
            "name": "get_user_tickets",
            "description": "Use this tool to list or search all open tickets associated with the user's company when they do not know a specific Ticket ID. Call this when the user asks 'What are my tickets?', 'List my tickets', or 'Do I have any open cases?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "description": "Optional filter for ticket status (e.g., 'open', 'resolved', 'all'). Default is 'open'."
                    }
                },
                "required": []
            }
        }
    }
]

# 2. get text Groq
def generate_ai_response(user_message: str) -> dict:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    system_prompt = """
    You are an elite AI Support Assistant for a Security Operations Center (SOC).
    Your primary responsibility is to facilitate security operations with precision and utmost professionalism.

    Strict Operating Guidelines:
    1. TONE & COMMUNICATION: Maintain a strictly formal, objective, and professional tone at all times. Do NOT use emojis, humor, slang, or conversational fillers. Deliver information clearly, factually, and concisely.
    2. LANGUAGE MATCHING: You MUST respond in the exact same language as the user's prompt. If the user writes in Thai, respond in highly formal Thai suitable for a corporate environment. If the user writes in English, respond in formal business English.
    3. TOOL EXECUTION: You have access to specific tools. If a user's request matches a tool's capability, YOU MUST CALL THE TOOL.
    4. DATA INTEGRITY: Do not invent, guess, or hallucinate answers for tickets, logs, or playbooks. Base all responses strictly on verified tool outputs or provided documentation.
        """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    try:
        
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=messages,
            tools=GROQ_TOOLS,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        # 3. AI > Tool 
        if response_message.tool_calls:
           
            tool_call = response_message.tool_calls[0]
            tool_name = tool_call.function.name
            
            
            arguments = json.loads(tool_call.function.arguments)
            
            return {
                "status": "tool_call",
                "tool_name": tool_name,
                "arguments": arguments
            }
        else:
            return {
                "status": "success",
                "reply": response_message.content
            }
            
    except Exception as e:
        return {
            "status": "error",
            "reply": f"Groq AI Error: {str(e)}"
        }