from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
import os
from google import genai # เพิ่ม import ตัวนี้สำหรับเรียก Gemini รอบสอง

from core.llm_engine import generate_ai_response
from rag.vector_db import search_knowledge
from integrations.itop_client import get_ticket_from_itop, create_ticket_in_itop
from integrations.web_search_client import search_public_web
from integrations.report_generator import create_html_dashboard
from integrations.itop_client import get_all_tickets_from_itop

app = FastAPI(title="AI Support Assistant API")

@app.get("/")
def read_root():
    return RedirectResponse(url="/chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)

class ChatRequest(BaseModel):
    message: str
    user_company: str

# 1. ฟังก์ชัน Second Pass ให้ AI สรุปข้อมูลดิบเป็นภาษาคน
def generate_human_summary(user_message: str, tool_name: str, raw_result: dict) -> str:
    from groq import Groq # import ตรงนี้หรือไว้บนสุดก็ได้
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    prompt = f"""
    You are an elite Cybersecurity Support Assistant.
    The user asked: "{user_message}"
    You executed the tool '{tool_name}' and got this result: {raw_result}
    
    Task: Write a professional, helpful, and concise response IN THAI.
    CRITICAL FORMATTING RULES:
    1. DO NOT use raw JSON keys (like 'ticket_id', 'subject'). Translate them to natural Thai (e.g., รหัสเคส, สถานะ, รายละเอียด).
    2. If listing multiple tickets, YOU MUST format them as a Markdown Table with columns: รหัสเคส | สถานะ | รายละเอียดปัญหา.
    3. Add suitable emojis to the status (e.g., 🔴 New, 🟡 In Progress, ⏳ Pending) to make it visually clear.
    4. End with a polite closing asking if they need further updates on any specific case.
    5. STRICTLY USE THAI AND ENGLISH ONLY. DO NOT output any Chinese characters under any circumstances.
    6. For ticket status, use clear Thai terms: 
       - 'new' = 'รอดำเนินการ (New)'
       - 'assigned' = 'รับเรื่องแล้ว (Assigned)'
       - 'pending' = 'รอการตอบกลับ (Pending)'
       - 'resolved' = 'แก้ไขเรียบร้อย (Resolved)'
    """
    
    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

@app.get("/chat", response_class=FileResponse)
def get_chat_ui():
    return "../frontend/templates/chat.html"
    
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    ai_result = generate_ai_response(request.message)
    
    if ai_result.get("status") == "tool_call":
        tool_name = ai_result.get("tool_name")
        args = ai_result.get("arguments")
        
        # 2. เก็บผลลัพธ์ของ Tool ไว้ในตัวแปร แทนที่จะ return กลับไปตรงๆ
        tool_data = {}
        
        if tool_name == "get_ticket_status":
            ticket_id = args.get("ticket_id")
            tool_data = get_ticket_from_itop(ticket_id, request.user_company)
            
        elif tool_name == "search_documents":
            search_query = args.get("query")
            tool_data = search_knowledge(search_query, request.user_company)
            
        elif tool_name == "create_new_ticket":
            issue = args.get("issue_description")
            tool_data = create_ticket_in_itop(issue, request.user_company)

        elif tool_name == "search_web":
            web_query = args.get("query")
            tool_data = search_public_web(web_query)
            
        elif tool_name == "generate_report_html":
            title = args.get("report_title")
            data = args.get("summary_data")
            tool_data = create_html_dashboard(title, data, request.user_company)
            
        elif tool_name == "get_user_tickets":
            status_filter = args.get("status_filter", "open")
            tool_data = get_all_tickets_from_itop(request.user_company, status_filter)

        # 3. โยน JSON กลับไปให้ Gemini สรุป ก่อนส่งขึ้นหน้าเว็บ
        human_reply = generate_human_summary(request.message, tool_name, tool_data)
        
        return {
            "status": "success", 
            "reply": human_reply
        }
            
    elif ai_result.get("status") == "success":
        return {"status": "success", "reply": ai_result.get("reply")}
        
    return {"status": "error", "message": ai_result.get("reply")}