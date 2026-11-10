# Internal AI Support Assistant System Documentation

## SOC ITSM Demo — Gemini Developer API

คู่มือส่วนนี้ใช้กับ Customer Portal, SOC Portal และ Ticket ใน feature branch ปัจจุบัน ส่วนถัดไปเป็นเอกสารของต้นแบบก่อนหน้า

1. สร้างฐานข้อมูลสำหรับเดโมโดยเฉพาะ ตั้งค่า `DATABASE_URL` และ `DEMO_SESSION_SECRET` (สุ่มอย่างน้อย 32 ตัวอักษร) ใน environment ของ Backend หรือ `backend/.env` ซึ่ง Git จะข้าม
2. จาก `backend/` ติดตั้ง dependencies ด้วย `python -m pip install -r requirements.txt` และรัน `PYTHONPATH=. python scripts/seed_phase1.py` กับ `PYTHONPATH=. python scripts/seed_customer_data.py` บนฐานข้อมูลเดโม สำหรับฐานที่จัดการด้วย Alembic ให้ใช้ `python -m alembic upgrade head` ก่อนเริ่มแอป ส่วนการเริ่มเดโมด้วย `create_all` จะเพิ่มตาราง assessment ใหม่โดยอัตโนมัติ
3. เริ่ม Backend ด้วย `python -m uvicorn main:app --host 127.0.0.1 --port 8000` และเริ่ม Frontend จาก `frontend/` ด้วย `npm ci` แล้ว `npm run dev` เริ่มด้วย `GEMINI_ENABLED=false` เพื่อใช้ fallback และตรวจ flow โดยไม่เรียก Google
4. หลังได้รับอนุญาตให้ใช้ Gemini API จริง ตั้งค่าด้านล่างใน Backend แล้ว restart ใช้เฉพาะบัญชีและข้อความจำลอง เก็บค่าจริงใน environment ของ Backend เท่านั้น

```dotenv
GEMINI_ENABLED=true
GEMINI_API_KEY=<API key from Google AI Studio>
GEMINI_MODEL=<model available to the key with generateContent and structured output>
DEMO_AUTH_MODE=password
DEMO_LOGIN_PASSWORDS_JSON={"customer.a1@example.test":"<unique random password>","customer.b1@example.test":"<another unique random password>","support@example.test":"<another unique random password>"}
```

กำหนดรหัสผ่านแบบสุ่มแยกตามอีเมลของบัญชีที่จะใช้ ความยาว 16–256 ตัวอักษร เมื่อเปิด Gemini ระบบบังคับใช้ password login และยกเลิกการใช้ token ที่ออกจาก mock login โหมดรหัสผ่านนี้มีไว้สำหรับเดโม ตัวจำกัดคำขออยู่ในหน่วยความจำของ Backend และใช้ร่วมกันระหว่าง Ticket และ Chat ให้รัน Uvicorn หนึ่ง worker สำหรับเดโม ค่าเริ่มต้นคือ 12 ครั้งต่อนาทีต่อผู้ใช้, 60 ครั้งต่อนาทีทั้งแอป และ 250 ครั้งต่อรอบ 24 ชั่วโมงต่อ process

### ตรวจผลเดโม

- เปิด Ticket ด้วยเหตุการณ์จำลองภาษาไทยหรืออังกฤษ แล้วเปิด Ticket Detail เพื่อดู Incident Type, Impact, Urgency, เหตุผล, คำแนะนำ และแหล่งประเมิน ระบบใช้ Priority Policy `soc-severity-v1` เลือกระดับที่รุนแรงกว่าระหว่างสองแกนและผูกกับ SLA Policy ของระดับนั้น
- ถาม `What is the dashboard port in the knowledge base?` ใน Chat ของ A1 และ B1 ตรวจว่า Sources เป็น `KB-002` และ `KB-004` ตามลำดับ บัญชี SOC ต้องเลือกบริษัทก่อนถาม
- เมื่อ Gemini ใช้ไม่ได้ Ticket ใหม่แสดง `Fallback — SOC review required` พร้อมค่าเริ่มต้น P3 ส่วน Chat แสดงข้อความจากเอกสารที่เข้าถึงได้หรือคำตอบจากข้อมูลจำลองตามประเภทคำถาม
- หากต้องการใช้ Chroma ให้ใช้ index ที่มีเฉพาะ playbook จำลองที่อนุมัติแล้ว เตรียม embedding model ไว้ในเครื่องก่อน รัน `python scripts/ingest_playbooks.py --scope public` สำหรับเอกสารส่วนกลาง หรือแทน `public` ด้วย UUID ของบริษัทจำลอง จากนั้นตั้ง `DEMO_KB_CHROMA_ENABLED=true` เอกสารส่วนตัวเดิมที่ใช้ชื่อบริษัทเป็น metadata ต้อง ingest ใหม่ด้วย UUID

รันชุดทดสอบ Gemini แบบไม่ออกเครือข่ายจาก `backend/` ด้วย `DATABASE_URL=sqlite:// GEMINI_ENABLED=false python -m unittest discover -s tests -p 'test_gemini*.py' -v` สำหรับชุดเต็มให้ใช้ Backend บนพอร์ต 8000 กับฐานข้อมูลเดโมแยกที่ seed แล้ว และรัน `python -m unittest discover -s tests -v`

---


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