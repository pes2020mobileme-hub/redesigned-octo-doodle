# 🤖 Discord Server Builder

เว็บ Dashboard สร้างโครงสร้างเซิร์ฟเวอร์ Discord อัตโนมัติ (Category, Channel, ข้อความ, Embed) พร้อม Template สำเร็จรูป 10 แบบ

- **Backend:** Python + Flask + discord.py
- **Frontend:** HTML + CSS + JavaScript (Dark mode โทน Discord)
- **รองรับ:** ภาษาไทย + มือถือ

---

## 1. ติดตั้ง Python

1. ดาวน์โหลด Python จาก https://www.python.org/downloads/
2. เลือกเวอร์ชัน **3.10 – 3.12** (แนะนำ 3.11)
3. ตอนติดตั้ง **ติ๊ก “Add Python to PATH”** ให้เรียบร้อย
4. ตรวจสอบโดยเปิด Command Prompt แล้วพิมพ์:

```bash
python --version
```

ต้องแสดงเลขเวอร์ชันจึงจะถูกต้อง

---

## 2. สร้าง Discord Application

1. เปิด https://discord.com/developers/applications
2. กดปุ่ม **New Application**
3. ตั้งชื่อแอป เช่น `Server Builder`
4. กด **Create**

---

## 3. สร้าง Discord Bot

1. ในหน้าแอป ให้ไปที่เมนู **Bot** (ทางซ้าย)
2. กด **Add Bot** แล้วยืนยัน
3. มีปุ่ม **Reset Token** ให้กดเพื่อดู Token (แสดงครั้งเดียว)
4. คัดลอก Token เก็บไว้ แล้วจะเอาไปใส่ในไฟล์ `.env`

> ⚠️ ห้ามเผยแพร่ Token ต่อใคร และห้ามวาง Token ใน source code (มีไว้ใน `.env` เท่านั้น และ `.env` อยู่ใน `.gitignore` แล้ว)

---

## 4. เอา Token ใส่ .env

สร้างไฟล์ `.env` ในโฟลเดอร์โปรเจกต์ (มีไฟล์ตัวอย่างให้อยู่แล้ว: `.env.example`)

เปิด `.env` แล้วแก้ให้เป็น:

```env
DISCORD_TOKEN=วาง_โทเค็น_จริง_ของคุณ_ตรงนี้
FLASK_SECRET=เปลี่ยนเป็นรหัสลับของตัวเอง
PORT=5000
```

---

## 5. เปิด Developer Mode

1. เปิด Discord → ตั้งค่า (**Settings**)
2. ไปที่ **Advanced**
3. เปิดสวิตช์ **Developer Mode**

---

## 6. หา Server ID

1. คลิกขวาที่ชื่อเซิร์ฟเวอร์ (ไอคอนอยู่ซ้ายสุด)
2. เลือก **Copy Server ID** (เป็นตัวเลข 17–20 หลัก เช่น `123456789012345678`)
3. เอาเลขนี้ไปกรอกใน Dashboard

---

## 7. เชิญ Bot เข้า Server

1. ในหน้า Discord Developer Portal → เมนู **OAuth2 > URL Generator**
2. ติ๊ก **bot** ในช่อง Scopes
3. ถ้าเป็น Admin ให้ติ๊ก **Administrator** ไว้ก่อนก็ได้
4. ด้านล่างจะได้ URL คัดลอกไปเปิดในเบราว์เซอร์
5. เลือกเซิร์ฟเวอร์ แล้วกด **Authorize**

จะได้ URL ลักษณะนี้ (ตัวอย่าง):

```
https://discord.com/oauth2/authorize?client_id=123456789&permissions=8&integration_type=0&scope=bot
```

---

## 8. อธิบาย Permission

Bot ต้องมีสิทธิ์เหล่านี้ในเซิร์ฟเวอร์จึงจะทำงานได้ครบ:

| Permission | ใช้ทำอะไร |
|---|---|
| `Manage Channels` | สร้าง/จัดการ Category และ Channel |
| `Send Messages` | ส่งข้อความและ Embed ลงช่อง |
| `View Channels` | มองเห็นช่องที่สร้าง |
| `Administrator` | (ทางลัด) ได้ทุกสิทธิ์ข้างต้น |

> ถ้าไม่มีสิทธิ์ ระบบจะแสดงข้อความข้อผิดพลาดที่เข้าใจง่ายแทนการเงียบ

---

## 9. ติดตั้ง dependencies

### Windows

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 10. รัน Bot / Web

```bash
python app.py
```

เมื่อรันสำเร็จ ระบบจะเปิดเว็บเซิร์ฟเวอร์บนพอร์ต 5000 และ **เริ่ม Discord Bot อัตโนมัติ** (บอทจะออนตลอดเวลา ถ้าหลุดการเชื่อมต่อจะรีสตาร์ทเอง)

---

## 11. เปิด Dashboard

เปิดเบราว์เซอร์:

```text
http://127.0.0.1:5000
```

1. กด **▶ เริ่ม Bot** เพื่อให้ Bot เชื่อมต่อ Discord
2. รอสถานะเปลี่ยนเป็น **Bot Online**

---

## 11.1 โฮสต์บอทออน 24/7 ฟรี (Render)

โปรเจกต์มีไฟล์ `Dockerfile` ให้พร้อมแล้ว — ใช้บริการฟรีที่เปิดตลอดได้โดยไม่ต้องเปิดเครื่อง

1. **เปิด Server Members Intent** — ไปที่ Discord Developer Portal → เลือกแอป → **Bot** → เปิดสวิตช์ **SERVER MEMBERS INTENT** (จำเป็นสำหรับ Auto Role / Welcome เมื่อมีคนเข้าร่วม)
2. สร้าง repo บน GitHub แล้ว push โค้ดขึ้น (อย่าลืมว่า `.env` อยู่ใน `.gitignore` แล้ว — จะเซ็ตผ่าน Environment ของ Render แทน)
3. เข้า https://dashboard.render.com → **New + → Web Service** → เลือก repo ของคุณ
4. ตั้งค่า:
   - **Runtime:** Docker
   - **Plan:** Free
5. ไปที่แท็บ **Environment** แล้วเพิ่ม:
   ```text
   DISCORD_TOKEN=โทเค็นจริงของคุณ
   FLASK_SECRET=รหัสลับแบบสุ่ม
   PORT=5000
   DISCORD_ENABLE_MEMBERS_INTENT=1
   ```
6. กด **Deploy** รอสัก 2–3 นาที จะได้ลิงก์สาธารณะ เช่น `https://xxx.onrender.com`
7. เปิดลิงก์นั้น ใช้ **ลิงก์เชิญบอท** ในหน้า แล้วเลือกเซิร์ฟเวอร์ → สร้างได้เลย

> ⚠️ Render ฟรีจะหลับถ้าไม่มีคนเปิดหน้าเว็บเกิน ~15 นาที — สร้างบัญชีฟรีที่ https://uptimerobot.com
> แล้วป้อน URL `https://xxx.onrender.com/api/status` ให้ **ping ทุก 10 นาที** จะทำให้บอทออนตลอดเวลา

---

## 12. สร้างเซิร์ฟเวอร์ (คลิกเดียว)

ไม่ต้องพิมพ์อะไร — ทำตามนี้:

1. เปิดหน้า Dashboard (บอทเริ่มอัตโนมัติแล้ว)
2. กด **➕ เชิญบอท** แล้วเลือกเซิร์ฟเวอร์ใน Discord (ลิงก์สร้างสิทธิ์ครบให้อัตโนมัติ)
3. รายชื่อเซิร์ฟเวอร์จะโผล่ในกล่องเลือกด้านบน → เลือกเซิร์ฟเวอร์
4. เลือก Template แล้วกด **⚡ สร้างเลย** → สร้างทั้งเซิร์ฟเวอร์ในคลิกเดียว

> Template 3 แบบ (Community / Gaming / Support) มาพร้อมระบบอัตโนมัติครบ:
> **Role + Permission**, **Auto Role**, **Welcome Embed**, **Rules**, **Log Channel**, **ปุ่ม Role (Button)**, และ **Ticket System**

---

## 12.1 สร้างแบบวิธีเดิม (ถ้าต้องการ)

ในส่วน **ตัวแก้ไข**:
- กด **➕ เพิ่ม Category**
- พิมพ์ชื่อ Category เช่น `INFORMATION`
- จัดการลบได้ด้วยปุ่ม 🗑️

---

## 13. สร้าง Channel

ภายในแต่ละ Category:
- กด **➕ เพิ่ม Channel**
- เลือกประเภท **💬 Text** หรือ **🔊 Voice**
- ตั้งชื่อช่อง เช่น `announcements`

> ถ้า Category / Channel มีชื่อซ้ำกับของเดิมที่เซิร์ฟเวอร์แล้ว ระบบจะ **ใช้ที่มีอยู่เดิม** ไม่สร้างซ้ำ

---

## 14. ส่งข้อความ

1. เลือก Channel แบบ Text
2. กรอกข้อความในช่อง **Channel Message** (เช่น `🎉 ยินดีต้อนรับ!`)
3. ถ้าช่องว่างจะไม่ส่งข้อความ

---

## 15. ส่ง Embed

1. เปิด **☑ Enable Embed**
2. กรอก **Embed Title** / **Embed Description** / **Embed Footer**
3. เลือก **Embed Color** จากจานสี
4. ดูตัวอย่าง Embed ได้ทันทีในบัตรของช่องนั้น
5. ระบบจะส่ง Embed ลงช่องหลังกดสร้างทั้งหมด

---

## ใช้ Template สำเร็จรูป

ในหน้าแรกมี **10 Template** ให้เลือก เช่น Community, Gaming, Shop, Support, Creator, Esports ฯลฯ

1. กด **👁 Preview** เพื่อดูโครงสร้างทั้งหมด
2. กด **เลือก** เพื่อโหลดเข้าตัวแก้ไข
3. ใส่ **Server ID**
4. กด **🚀 สร้างทั้งหมด**

---

## ลำดับการทำงาน (flow)

```text
เริ่ม Bot
  ↓
Bot Online
  ↓
เลือก Template หรือแก้ไขเอง
  ↓
กรอก Server ID
  ↓
สร้างทั้งหมด
  ↓
Discord Bot ตรวจสอบ Server / สิทธิ์
  ↓
สร้าง Category → Channel → ส่งข้อความ → ส่ง Embed
  ↓
Log แสดงผลแบบ real-time
  ↓
เสร็จ ✅
```

---

## Troubleshooting

| ปัญหา | สาเหตุ / วิธีแก้ |
|---|---|
| `Bot ยังไม่ Online` | ยังไม่กดเริ่ม Bot หรือกำลังเชื่อมต่ออยู่ รอ 5–10 วิ แล้วลองใหม่ |
| `กรุณาใส่ Discord Token` | ยังไม่ได้ใส่ Token จริงใน `.env` แล้วเริ่มโปรเจกต์ใหม่ |
| `Bot เริ่มไม่สำเร็จ` | Token ผิด หมดอายุ หรือไม่มีอินเทอร์เน็ต ตรวจสอบที่ Developer Portal |
| `ไม่พบเซิร์ฟเวอร์นี้` | Server ID ผิด หรือยังไม่ได้เชิญ Bot เข้าเซิร์ฟเวอร์ |
| `Bot ขาดสิทธิ์...` | ใช้ลิงก์เชิญใหม่พร้อมสิทธิ์ Administrator (permissions=8) |
| สร้าง Category ซ้ำ | ระบบตรวจเจอชื่อเดิมแล้วจะใช้ของเดิม (เป็นไปตามการออกแบบ) |
| พอร์ต 5000 ชนกับอะไร | เปลี่ยนได้ใน `.env` ด้วยตัวแปร `PORT=เลขพอร์ตใหม่` |
| หน้าเว็บไม่โหลด | รัน `python app.py` แล้วเปิด `http://127.0.0.1:5000` |
| เร็วเลย rate limit | Discord จำกัดการสร้างช่อง อย่ากดซ้ำถี่ ๆ ติดต่อกัน |

---

## โครงสร้างไฟล์

```text
discord-server-builder/
├── app.py              # Flask Web Dashboard + REST API
├── bot.py              # Discord Bot (discord.py) + build_server
├── templates.json      # ข้อมูล Template ทั้ง 10 แบบ
├── requirements.txt    # dependencies ที่กำหนดเวอร์ชันแล้ว
├── .env                # Token / Secret / Port (ห้ามแชร์)
├── .env.example        # ตัวอย่างไฟล์ .env
├── .gitignore
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── app.js
```

## API

```text
GET  /                หน้า Dashboard
GET  /api/status      สถานะ Bot
POST /api/start       เริ่ม Bot
POST /api/build       สร้างเซิร์ฟเวอร์ (รองรับ template_id หรือ categories)
GET  /api/logs        Log แบบ SSE (real-time)
```