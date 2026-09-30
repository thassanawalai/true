# Internal AI Support Assistant System Documentation

เอกสารสรุประบบและสถาปัตยกรรมของ Internal AI Support Assistant ซึ่งเป็น API หลังบ้านที่พัฒนาขึ้นด้วยกรอบการทำงาน FastAPI ทำงานประสานกับLLM Google Gemini 3.6 Flash ระบบนี้ถูกออกแบบมาเพื่อช่วยแบ่งเบาภาระงานของทีมสนับสนุนลูกค้า โดยเน้นความปลอดภัยของข้อมูลองค์กรเป็นหลัก

## 1. ภาพรวมระบบและสถาปัตยกรรมหลัก (Core Architecture)

ระบบถูกออกแบบด้วยสถาปัตยกรรมแบบ Modular Design เพื่อให้ง่ายต่อการดูแลรักษาและการขยายขีดความสามารถในอนาคต ประกอบด้วยคุณสมบัติหลักดังนี้:

*   **RESTful API Framework:** ทำงานบน FastAPI รองรับการประมวลผลแบบ Asynchronous ทำให้ระบบสามารถรองรับผู้ใช้งานพร้อมกันจำนวนมากได้
*   **LLM Integration:** ใช้ Google GenAI SDK รุ่นล่าสุด เชื่อมต่อกับโมเดล `gemini-3.6-flash` พร้อมการฝัง System Instructions เพื่อควบคุมพฤติกรรมของ AI ให้ทำงานตามขอบเขตที่กำหนด
*   **Human-in-the-loop (Tool Execution):** AI ทำหน้าที่วิเคราะห์และตัดสินใจเลือกเครื่องมือ (Function Calling) แต่จะไม่สามารถเข้าถึงฐานข้อมูลได้โดยตรง ระบบ Backend จะเป็นผู้รับคำสั่งจาก AI มาตรวจสอบเงื่อนไขและดึงข้อมูลให้เสมอ
*   **Strict Data Isolation:** ระบบมีการตรวจสอบรหัสหรือชื่อบริษัทของผู้ใช้งาน (`user_company`) ในทุกขั้นตอนการทำงาน ป้องกันไม่ให้เกิดการรั่วไหลของข้อมูลระหว่างบริษัท (Cross-tenant Data Breach)

## 2. ความสามารถและเครื่องมือของระบบ (System Capabilities & Tools)

AI ภายในระบบได้รับการฝึกฝนให้รู้จักและเรียกใช้เครื่องมือ (Tools) 5 อย่าง เพื่อตอบสนองต่อคำร้องขอของผู้ใช้ ดังนี้:

1.  **get_ticket_status:** ตรวจสอบสถานะของ Ticket จากระบบ iTop (ระบบจำลอง) โดยจะปฏิเสธการแสดงผลทันทีหากสิทธิ์บริษัทของผู้ใช้ไม่ตรงกับข้อมูลในระบบ
2.  **search_documents (Internal RAG):** ค้นหาข้อมูล คู่มือ และวิธีแก้ปัญหาจากฐานความรู้ภายในองค์กร (Knowledge Base)
3.  **search_web (Hybrid RAG):** ค้นหาข้อมูลและวิธีแก้ไขปัญหาซอฟต์แวร์ทั่วไปจากอินเทอร์เน็ต เพื่อตอบคำถามที่ไม่มีระบุไว้ในคู่มือองค์กร
4.  **create_new_ticket:** สั่งการเปิด Ticket ใหม่เข้าสู่ระบบ iTop โดยมีเงื่อนไขบังคับว่าระบบจะต้องพยายามค้นหาคู่มือเพื่อแก้ปัญหาก่อน หากไม่พบวิธีแก้ปัญหาจึงจะทำการเปิด Ticket ให้
5.  **generate_report_html:** สร้างรายงานสรุปข้อมูลในรูปแบบ Dashboard HTML ที่มีความสวยงามและเป็นระเบียบ เพื่อใช้ในการนำเสนอต่อลูกค้า

## 3. กระบวนการทำงานโดยละเอียด (Detailed Workflow)

เมื่อผู้ใช้งานส่งข้อความเข้ามาในระบบ จะเกิดกระบวนการทำงานตามลำดับดังนี้:

**ขั้นตอนที่ 1: การรับข้อมูล (Input Reception)**
*   ผู้ใช้งานส่งข้อความและข้อมูลบริษัท (`user_company`) เข้ามาที่ Endpoint `/api/chat`

**ขั้นตอนที่ 2: การวิเคราะห์เจตนา (Intent Analysis)**
*   ระบบส่งข้อความของผู้ใช้ พร้อมกับรายชื่อเครื่องมือ (SUPPORT_TOOLS) และคำสั่งควบคุมพฤติกรรม (SYSTEM_INSTRUCTION) ไปยัง Gemini API

**ขั้นตอนที่ 3: การตัดสินใจ (Decision Making)**
*   โมเดล AI วิเคราะห์ข้อความและประเมินว่าสามารถตอบคำถามได้ทันที หรือจำเป็นต้องใช้เครื่องมือเสริม
*   หากผู้ใช้แจ้งปัญหาทางเทคนิค AI จะถูกบังคับให้ดำเนินการตามลำดับขั้น คือ เรียกใช้ `search_documents` หรือ `search_web` ก่อน

**ขั้นตอนที่ 4: การประมวลผลเครื่องมือ (Tool Execution)**
*   หาก AI ร้องขอการใช้เครื่องมือ (Function Calling) ระบบ Backend จะรับคำสั่งนั้นมาทำงานตามฟังก์ชันที่กำหนดในโฟลเดอร์ `integrations` หรือ `rag`
*   ในกระบวนการนี้จะมีการตรวจสอบ `user_company` เสมอ เพื่อความปลอดภัยของข้อมูล
*   ระบบ Backend ส่งคืนผลลัพธ์ (เช่น สถานะ Ticket, เนื้อหาคู่มือ, หรือหมายเลข Ticket ใหม่) กลับไปยังผู้ใช้

## 4. โครงสร้างของระบบ (Project Structure)

```text
ai-support-assistant/
├── main.py                     # ส่วนควบคุมหลักของระบบ (API Endpoints และ Routing)
├── core/                       
│   ├── llm_engine.py           # ระบบประมวลผล LLM และการเชื่อมต่อ Google GenAI SDK
│   ├── prompts.py              # กฎและข้อบังคับในการทำงานของ AI (System Instructions)
│   └── tools_config.py         # โครงสร้างและคำอธิบายเครื่องมือสำหรับ Function Calling
├── integrations/
│   ├── itop_client.py          # การเชื่อมต่อระบบบริหารจัดการ Ticket (Mock iTop)
│   ├── web_search_client.py    # การจำลองระบบค้นหาข้อมูลจากอินเทอร์เน็ตภายนอก
│   └── report_generator.py     # ระบบสร้าง Dashboard HTML สำหรับการทำรายงานสรุป
├── rag/
│   ├── document_loader.py      # ระบบจำลองการอ่านเอกสารองค์กร
│   └── vector_db.py            # ระบบฐานข้อมูลคู่มือพร้อมการกรองสิทธิ์ Data Isolation
├── templates/
│   └── chat.html               # หน้าจอ User Interface แบบ HTML/JS สำหรับการทดสอบ
└── requirements.txt            # รายการ Dependencies ที่จำเป็นสำหรับโปรเจกต์

How to Run (Development Mode)
1. ติดตั้ง Libraries ที่จำเป็น
pip install fastapi uvicorn pydantic google-genai
2. ตั้งค่า Environment Variable (รอ API Key จาก IT)
export GEMINI_API_KEY="your_api_key_here"
3. สตาร์ทเซิร์ฟเวอร์
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
4. ทดสอบ API

เปิดเบราว์เซอร์ไปที่: http://localhost:8080/docs (หรือใช้ Web Preview บน Cloud Shell)
ทดสอบ Endpoint: POST /api/chat
Security Note
ระบบจะทำการคืนค่า 400 INVALID_ARGUMENT หาก GEMINI_API_KEY ไม่ถูกต้อง

การส่ง Request จำเป็นต้องระบุ user_company เสมอ เพื่อให้ระบบ Backend นำไปกรองสิทธิ์ในการใช้งาน Tools ต่างๆ