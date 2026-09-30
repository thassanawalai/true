from groq import Groq

client = Groq(api_key="")

print("กำลังดึงรายชื่อโมเดล...")
models = client.models.list()

print("โมเดลที่มีสิทธิ์ใช้งานได้:")
for m in models.data:
    print(f"- {m.id}")