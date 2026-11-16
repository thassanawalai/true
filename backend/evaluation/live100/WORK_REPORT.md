# รายงานการพัฒนาตัวทดสอบ SOC 100 เคส

วันที่ 16 พฤศจิกายน 2026 (ประเทศไทย)
ฐานโค้ด: feature/render-gemini-login commit 08d16c1

## งานที่ทำเสร็จ
1. แยก worktree เพื่อรักษางานค้างใน checkout เดิม
2. สร้าง 100 เคสจาก 10 รูปแบบ × 10 ตัวแปร พร้อมเฉลยและ Log จำลอง 530 แถว
3. เตรียม SQL สำหรับ Neon แบบ transaction มี UUID คงที่ ไม่ลบข้อมูล
   ตรวจบริษัท A/B และตรวจความตรงกันของข้อมูลเดิมก่อนยอมรับ fixture
4. สร้าง runner เรียก API ของระบบจริงทีละเคส เว้นอย่างน้อย 60 วินาทีหลังคำตอบ
   พักทุก 10 เคส จองงบก่อนเรียก เก็บสถานะลง SQLite และทำต่อจากไฟล์เดิมได้
5. หยุดเมื่อ fallback, คำตอบผิด, 429, ข้อผิดพลาด HTTP, timeout หรือข้อมูลตอบกลับไม่ครบ
   ไม่ retry คำขอที่อาจใช้โควตาไปแล้ว ไม่ลบประวัติผลที่ผิด
6. บันทึก provider metadata: request ID, model, attempted, succeeded, failure,
   HTTP status เมื่อมี, latency และจำนวน tokens เมื่อ SDK คืนข้อมูล
7. ส่ง metadata กลับใน API วิเคราะห์ และผล POST ข้อความแชท
   ไม่เปลี่ยน schema ประวัติข้อความเดิม; metadata ของแชทไม่ได้ persist ใน RoomMessage
8. ลด default global RPM จาก 60 เป็น 10 และให้ incident_json ใช้ตัวจำกัดร่วมกับ chat/ticket
9. เพิ่มรายงาน JSON/CSV และคู่มือใช้งาน

## ผลตรวจสอบ
| การตรวจ | ผล |
|---|---|
| 100 เคสผ่าน FastAPI + SQLite โดย mock Gemini และปิด network | 100/100 ผ่าน |
| ชุดทดสอบออฟไลน์ที่เกี่ยวข้อง รวม regression | 105 tests ผ่าน |
| นำเข้า fixture ซ้ำผ่าน ORM | จำนวนแถวไม่เพิ่ม |
| จำลอง 429 และตรวจ metadata | ผ่าน ไม่เปิดเผยข้อความ error ที่อาจมีข้อมูลลับ |
| คิวหยุด/ทำต่อ/งบ/ระยะพัก | ผ่าน |
| จำลอง fallback ใน runner | หยุดและเก็บผลเดิมตามคาด |
| ตรวจ SQL ด้วย PostgreSQL parser | ผ่าน 1,268 statements |
| git diff --check | ผ่าน |
| Gemini จริงที่เรียกในรอบพัฒนานี้ | 0 ครั้ง |
| 100 เคสบน Render + Neon + Gemini จริง | ยังไม่ได้รัน |

105 tests เป็นจำนวน test methods; การตรวจ 100 เคสอยู่ภายในหนึ่ง method ไม่ใช่ผลรวมตัวอย่างอิสระ 205 ตัวอย่าง
SQL ผ่านการ parse syntax แต่ยังไม่ได้ execute บน PostgreSQL/Neon ในรอบนี้
การรัน discover ทั้งหมดครั้งแรกพบ 2 ชุดที่ต้องมี local HTTP server/database fixture
(test_chat_rooms และ test_portal_api) จึงแยกออกจาก offline regression อย่างชัดเจน
ไม่ได้อ้างว่าชุด live HTTP เดิมสองชุดนี้ผ่าน

## ข้อจำกัดที่ยังคงอยู่
- 100 เคสนี้มี 10 รูปแบบหลัก ยังไม่ครอบคลุม aggregate logs, การตัดเกิน 100 แถว หรือคำถามภาษาอิสระทั้งหมด
- ไม่ใช้ LLM judge และไม่ให้คะแนน semantic correctness ของคำแนะนำทั้งหมด
- ระบบนับข้อมูลด้วย Backend; Gemini รับเฉพาะ verified demo context และ KB ตามขอบเขตเดิม
- ตัวจำกัด Backend เป็นหน่วยความจำต่อ process ไม่ใช่ shared persistent provider quota
  runner มี ledger ถาวรเฉพาะงานนี้ ไม่ทราบคำขอจากบริการอื่นใน Google project
- ไม่มี automatic daily scheduler/background service; โปรแกรมต้องเปิดทำงานอยู่ หรือเริ่มใหม่เพื่อ resume
- ไม่มี auto retry สำหรับ 429 ในรุ่นนี้ จงใจหยุดเพื่อไม่เผาโควตาหรือซ่อนความผิดพลาด
- ไม่มี browser E2E 100 รอบ ผล API ไม่ใช่หลักฐานว่า UI ทุกจุดผ่าน
- การที่หน้าเว็บตอบ HTTP 200 ไม่ยืนยัน deployment commit หรือ Gemini ทำงาน

## สิ่งที่ยังติดการเข้าถึง
ตรวจแล้วไม่มีแท็บ browser ที่ล็อกอินอยู่ และไม่มี DATABASE_URL/session ของระบบจริงในสภาพแวดล้อมงานนี้
จึงยังนำเข้า Neon หรือรัน authenticated pilot บน Render ไม่ได้
ไม่ได้ขอให้ส่ง API key หรือรหัสผ่านลงแชท

## ขั้นตอนปิดงานทดสอบจริง
1. ตรวจว่า Render deploy commit ที่มี provider metadata สำเร็จ
2. รัน generated/seed.sql ใน Neon SQL Editor ผลต้องเป็น 530 แถว
3. รัน runner --limit 5 ตาม README โดยกรอกรหัสผ่าน Customer A1 ใน terminal ผ่าน getpass
4. ตรวจ JSON/CSV ถ้าข้อเท็จจริงและ Gemini ผ่านทั้ง 5 เคส จึงรัน --limit 100 โดยใช้ state เดิม
5. เก็บ manifest, seed SQL, SQLite ledger, JSON และ CSV เป็นหลักฐาน

เอกสารนี้รายงานงานพัฒนาและผลออฟไลน์เท่านั้น ไม่ใช้แทนรายงานผลระบบจริง
