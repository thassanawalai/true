# ตัวทดสอบ SOC จำนวน 100 เคส

## ขอบเขต
ทดสอบระบบที่ deploy ผ่าน `/api/customer-data/ask` โดยใช้ session ของ Customer A1
ตรวจการค้นหา Log, จำนวน, บัญชี, IP, เวลา, ข้อมูลข้ามบริษัท, ข้อความที่แสดง และสถานะ Gemini
นี่เป็น API integration test ไม่ใช่การคลิกหน้าเว็บ 100 รอบ และไม่ใช่การวัดว่า Gemini อ่าน Log ทุกแถว
ระบบเดิมนับ Log ด้วย Backend; Gemini รับเฉพาะ verified static telemetry และ KB
ไม่ได้เปลี่ยนขอบเขตส่งข้อมูลให้ผู้ให้บริการภายนอกในงานนี้

100 เคส = 10 รูปแบบ × 10 ตัวแปร ไม่ใช่ 100 ตัวอย่างอิสระจากข้อมูลใช้งานจริง
กลุ่ม: ล้มเหลวพื้นฐาน, สำเร็จภายหลัง, หลายบัญชี, หลาย IP, event_id ซ้ำ,
IP หาย, สำเร็จก่อนล้มเหลว, เวลาเท่ากัน, ขอบเขตเวลา, การแยกบริษัท
เฉลยเขียนจากข้อกำหนดสถานการณ์ ไม่เรียก production parser มาสร้างเฉลย
การทดสอบยังไม่ครอบคลุม aggregate logs, มากกว่า 100 แถว, ภาษาอิสระทั้งหมด หรือความหมายของคำแนะนำทั้งหมด

## โควตาและการหยุด
- ส่งทีละเคส ระยะพักอย่างน้อย 60 วินาทีหลังคำตอบ พักเพิ่ม 5 นาทีทุก 10 เคส
- ค่าเริ่มต้น 5 เคสต่อ invocation; เพิ่ม `--limit 100` หลังตรวจ pilot
- การวิเคราะห์หนึ่งเคสเรียก Gemini ได้สูงสุดหนึ่งครั้ง; SDK retries ปิดอยู่
- เก็บการจองงบก่อนส่งคำขอใน SQLite ไม่ล้างเมื่อหยุดโปรแกรม
- จำกัดงบทั้ง run และ rolling 24 ชั่วโมง ไม่เกิน 250; ไม่ใช่ตัวนับโควตาของ Google
- ไม่ยิง retry อัตโนมัติ: 429, timeout, fallback, คำตอบผิด หรือไม่มี provider metadata ทำให้หยุด
- HTTP timeout อาจใช้โควตาแล้ว จึงคงสถานะไม่แน่ชัดและไม่ยิงซ้ำ
- ทำต่อโดยใช้ไฟล์ state เดิม; ถ้าเคยหยุดจากความผิดพลาดต้องตรวจ report แล้วเพิ่ม `--continue-after-review`
- flag ดังกล่าวข้ามเคสที่บันทึกไว้ ไม่เปลี่ยนผลที่ผิดเป็นผ่าน และไม่ retry เคสเดิม
- มี process lock ใน working directory เดียวกัน อย่าเปิด runner หลาย directory/state พร้อมกัน
- ผู้ใช้เว็บและโปรแกรมอื่นยังใช้โควตาร่วมกันได้; ตัวนับ Backend ยังเป็น in-memory ต่อ process
- Backend ค่าเริ่มต้น 10 RPM / 250 ต่อวัน; Environment ที่ตั้งไว้อาจ override ได้
- ยังไม่มีตัวจำกัด TPM แบบกระจายศูนย์; prompt จำกัดขนาดและ runner ส่งช้า

## ขั้นตอนใช้งาน
ใช้ Python 3.12 และรันจาก `backend/` ของ checkout นี้

```bash
python -m pip install -r requirements-demo.txt httpx
python -m evaluation.live100.prepare --output evaluation/live100/generated
```

ตรวจและรัน `generated/seed.sql` ใน Neon SQL Editor ของฐานที่ Render ใช้
SQL ตรวจชื่อบริษัท A/B ก่อนทำงาน ใช้ UUID คงที่ และ `ON CONFLICT (id) DO NOTHING`
ไม่ลบหรือแก้ไขข้อมูลเดิม; ถ้าข้อมูล fixture เดิมไม่ตรงจะ abort transaction
ถ้า editor แสดง transaction aborted ให้ ROLLBACK ก่อนแก้สาเหตุและรันใหม่
ผลต้องแสดง retained_evaluation_logs = 530
ห้ามเปลี่ยนรหัส fixture แล้วใส่ชุดใหม่ซ้ำโดยไม่ตั้งใจ

Deploy โค้ดที่มี provider metadata ก่อนเรียก runner มิฉะนั้น runner จะหยุดอย่างปลอดภัย

```bash
python -m evaluation.live100.runner --url https://soc-itsm-ai-demo.onrender.com --state evaluation-state.sqlite --report evaluation-results.json --limit 5
```

โปรแกรมถามรหัสผ่าน Customer A1 ผ่าน getpass ไม่แสดงและไม่บันทึกรหัสผ่าน
หรือกำหนด `SOC_EVAL_TOKEN` ผ่านช่องทางจัดการ secrets ของเครื่อง ไม่ใส่ token ใน command line
ไม่ต้องมี Gemini key บนเครื่องทดสอบ เพราะ Backend เป็นผู้เรียก Gemini

ตรวจผล pilot แล้วทำต่อด้วย state เดิม:

```bash
python -m evaluation.live100.runner --url https://soc-itsm-ai-demo.onrender.com --state evaluation-state.sqlite --report evaluation-results.json --limit 100
```

หากเครื่องหยุดหรือ terminal ปิด งานหยุดด้วย ต้องรันคำสั่งเดิมเพื่อทำต่อ
ไม่ได้ติดตั้งงาน background หรือ scheduled automation

## การให้คะแนนและหลักฐาน
- ทุก expected field ต้องตรง รวมชุด log_id; ตัวเลขในข้อความต้องตรงกับเฉลย
- เก็บผลรายข้อพร้อมคำถามและ response เต็ม; JSON และ CSV ออกหลังจบหรือหยุด
- facts_passed แยกจาก gemini_passed; fallback ไม่นับว่า Gemini ผ่าน
- semantic_review = not_scored ไม่อ้างว่าได้ตรวจความหมายทุกประโยค
- พบคำตอบผิดจะหยุดเพื่อให้แก้ก่อน ไม่ยิงใหม่จนผ่านแล้วทิ้งผลเดิม
- mode=gemini_demo หมายถึงคำตอบจาก provider ผ่านตัวกรองของระบบ ไม่ใช่การรับรองคุณภาพความหมาย
- 10 เคสข้ามบริษัทจะเชื่อถือได้เมื่อยืนยันว่า seed ฝั่ง B อยู่จริงแล้ว มิฉะนั้นผลว่างอาจเป็นเพราะไม่มีข้อมูล
- เก็บไฟล์ state, report และ manifest ไว้เป็นหลักฐาน ห้ามแชร์ session token

## การตรวจออฟไลน์
```bash
# ตั้ง DATABASE_URL เป็น SQLite สำหรับทดสอบ, ปิด Gemini และ dotenv
python -m unittest discover -s tests -p test_live100.py -v
```
ชุดทดสอบใช้ FastAPI และ SQLite จริง แต่ mock SDK และปิด network
จึงเป็นหลักฐานการทำงานของโค้ด ไม่ใช่ผล Render/Neon/Gemini จริง

## การปรับพฤติกรรม fallback
เมื่อข้อเท็จจริงผ่านและ provider.succeeded=true โดยไม่มี failure โปรแกรมจะเก็บ fallback แล้วทำเคสถัดไป รวมถึง resume ผลเดิมชนิดนี้ได้ทันที ส่วนข้อเท็จจริงผิด การเรียก provider ล้มเหลว หรือสถานะไม่แน่ชัดยังหยุดตามเดิม คะแนน gemini_passed ของเคส fallback ยังคงเป็น false
