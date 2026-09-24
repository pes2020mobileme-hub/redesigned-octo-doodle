import asyncio
import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

from bot import discord_bot

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "CHANGE_ME")

with open(BASE_DIR / "templates.json", "r", encoding="utf-8") as file:
    TEMPLATE_DATA = json.load(file)

CUSTOM_TEMPLATES_FILE = BASE_DIR / "custom_templates.json"


def load_custom_templates():
    if CUSTOM_TEMPLATES_FILE.exists():
        try:
            with open(CUSTOM_TEMPLATES_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def all_templates():
    return TEMPLATE_DATA.get("templates", []) + load_custom_templates()


log_queue = queue.Queue()
build_lock = threading.Lock()
bot_started = False


def add_log(message):
    if isinstance(message, dict):
        entry = dict(message)
    else:
        entry = {"type": "info", "message": str(message)}
    entry.setdefault("timestamp", time.strftime("%H:%M:%S"))
    log_queue.put(entry)


@app.route("/")
def index():
    return render_template(
        "index.html",
        templates=all_templates(),
    )


@app.route("/api/status")
def status():
    bot = discord_bot.bot_user()
    stats = discord_bot.stats()
    return jsonify(
        {
            "online": discord_bot.is_ready(),
            "bot": str(bot) if bot else None,
            "client_id": str(bot.id) if bot else None,
            "invite_url": discord_bot.invite_url(),
            "guilds": discord_bot.guilds(),
            "guild_count": stats["guild_count"],
            "member_count": stats["member_count"],
            "uptime_seconds": stats["uptime_seconds"],
        }
    )


@app.route("/api/start", methods=["POST"])
def start():
    if discord_bot.is_ready():
        return jsonify({"success": True, "message": "Bot กำลังทำงานอยู่แล้ว"})

    if bot_started and not discord_bot.can_restart():
        return jsonify(
            {
                "success": False,
                "error": "Bot กำลังเริ่มอยู่ กรุณารอสักครู่แล้วลองใหม่",
            }
        )

    if try_start_bot():
        return jsonify({"success": True, "message": "กำลังเริ่ม Bot"})
    return jsonify({"success": False, "error": "เริ่ม Bot ไม่สำเร็จ"}), 400


def _wait_ready():
    time.sleep(15)
    if not discord_bot.is_ready():
        add_log(
            {
                "type": "error",
                "message": (
                    "❌ Bot เริ่มไม่สำเร็จ ตรวจสอบ Token ใน .env "
                    "ว่าถูกต้องและอินเทอร์เน็ตทำงานปกติ"
                ),
            }
        )


def try_start_bot(initial=False):
    global bot_started

    if discord_bot.is_ready():
        return True

    if bot_started and not discord_bot.can_restart():
        return True

    bot_started = False
    token = os.getenv("DISCORD_TOKEN", "")
    try:
        discord_bot.start(token, add_log)
        bot_started = True
        if initial:
            add_log("🤖 เริ่ม Discord Bot อัตโนมัติ (เปิดโปรแกรม)...")
        else:
            add_log("🤖 กำลังเริ่ม Discord Bot...")
    except ValueError as exc:
        add_log({"type": "error", "message": f"❌ {exc}"})
        return False

    threading.Thread(target=_wait_ready, daemon=True).start()
    return True


def keep_alive():
    while True:
        time.sleep(15)
        if bot_started and not discord_bot.is_ready() and discord_bot.can_restart():
            add_log(
                {
                    "type": "error",
                    "message": "🔌 Bot หลุดการเชื่อมต่อ — กำลังเริ่มใหม่อัตโนมัติ...",
                }
            )
            try_start_bot()


def format_uptime(seconds):
    seconds = int(seconds or 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}ชม {minutes}นาที"
    return f"{minutes}นาที {secs}วิ"


def status_logger():
    while True:
        time.sleep(60)
        st = discord_bot.stats()
        if st["online"]:
            msg = (
                f"🟢 สถานะ: ออนไลน์ · 🤖 {st['bot']} · "
                f"📁 {st['guild_count']} เซิร์ฟเวอร์ · "
                f"👥 {st['member_count']:,} สมาชิก"
            )
            if st.get("uptime_seconds") is not None:
                msg += f" · ⏱️ {format_uptime(st['uptime_seconds'])}"
            add_log({"type": "status", "message": msg})
        else:
            add_log(
                {
                    "type": "error",
                    "message": "🔴 สถานะ: บอทออฟไลน์ — กำลังรอเชื่อมต่อใหม่อัตโนมัติ...",
                }
            )


@app.route("/api/restart", methods=["POST"])
def restart_bot():
    if not discord_bot.is_ready() and not bot_started:
        return jsonify(
            {"success": False, "error": "บอทยังไม่เริ่มอยู่ จึงไม่ต้อง restart"}
        ), 400

    add_log("🔄 รับคำสั่ง restart บอท...")
    ok = discord_bot.restart(add_log)
    if not ok:
        return jsonify(
            {"success": False, "error": "restart ไม่สำเร็จ ดูรายละเอียดใน Log"}
        ), 500
    return jsonify({"success": True, "message": "กำลัง restart บอท..."})


@app.route("/api/build", methods=["POST"])
def build():
    data = request.get_json(silent=True) or {}

    guild_id = (data.get("guild_id") or "").strip()
    if not guild_id:
        return jsonify({"success": False, "error": "กรุณากรอก Server ID"}), 400

    try:
        guild_id_int = int(guild_id)
    except (TypeError, ValueError):
        return jsonify(
            {"success": False, "error": "Server ID ต้องเป็นตัวเลขเท่านั้น"}
        ), 400

    if not discord_bot.is_ready():
        return jsonify(
            {
                "success": False,
                "error": "Bot ยังไม่ Online กรุณากดเริ่ม Bot ก่อน",
            }
        ), 400

    template_id = data.get("template_id")
    payload = None

    if template_id:
        selected = next(
            (
                t
                for t in all_templates()
                if t.get("id") == template_id
            ),
            None,
        )
        if selected is None:
            return jsonify({"success": False, "error": "ไม่พบ Template นี้"}), 404
        payload = selected
    else:
        categories = data.get("categories")
        if not isinstance(categories, list) or not categories:
            return jsonify(
                {
                    "success": False,
                    "error": "กรุณาเลือก Template หรือระบุ Categories",
                }
            ), 400
        payload = {
            "categories": categories,
            "roles": data.get("roles", []),
            "log_channel": data.get("log_channel"),
        }

    if not build_lock.acquire(blocking=False):
        return jsonify(
            {"success": False, "error": "กำลังสร้างอยู่ รอให้เสร็จก่อน"}
        ), 409

    try:
        add_log("🚀 เริ่มสร้างเซิร์ฟเวอร์...")
        future = discord_bot.run_build(guild_id_int, payload, add_log)
        result = future.result(timeout=300)
        add_log("🎉 สร้างเสร็จทั้งหมด")
        return jsonify({"success": True, "result": result})
    except asyncio.CancelledError:
        add_log({"type": "error", "message": "❌ ยกเลิกการสร้าง"})
        return jsonify({"success": False, "error": "ยกเลิกการสร้าง"}), 500
    except Exception as exc:
        message = str(exc)
        add_log({"type": "error", "message": f"❌ {message}"})
        return jsonify({"success": False, "error": message}), 500
    finally:
        build_lock.release()


@app.route("/api/guild-structure", methods=["POST"])
def guild_structure():
    data = request.get_json(silent=True) or {}

    guild_id = (data.get("guild_id") or "").strip()
    if not guild_id:
        return jsonify({"success": False, "error": "กรุณากรอก Server ID"}), 400

    try:
        guild_id_int = int(guild_id)
    except (TypeError, ValueError):
        return jsonify(
            {"success": False, "error": "Server ID ต้องเป็นตัวเลขเท่านั้น"}
        ), 400

    if not discord_bot.is_ready():
        return jsonify(
            {
                "success": False,
                "error": "Bot ยังไม่ Online กรุณากดเริ่ม Bot ก่อน",
            }
        ), 400

    try:
        future = discord_bot.run_guild_structure(guild_id_int, None)
        categories = future.result(timeout=300)
        return jsonify({"success": True, "categories": categories})
    except Exception as exc:
        message = str(exc)
        add_log({"type": "error", "message": f"❌ {message}"})
        return jsonify({"success": False, "error": message}), 500


@app.route("/api/delete", methods=["POST"])
def delete_rooms():
    data = request.get_json(silent=True) or {}

    guild_id = (data.get("guild_id") or "").strip()
    if not guild_id:
        return jsonify({"success": False, "error": "กรุณากรอก Server ID"}), 400

    try:
        guild_id_int = int(guild_id)
    except (TypeError, ValueError):
        return jsonify(
            {"success": False, "error": "Server ID ต้องเป็นตัวเลขเท่านั้น"}
        ), 400

    if not discord_bot.is_ready():
        return jsonify(
            {
                "success": False,
                "error": "Bot ยังไม่ Online กรุณากดเริ่ม Bot ก่อน",
            }
        ), 400

    def _ids(raw):
        ids = set()
        for item in raw or []:
            try:
                ids.add(int(item))
            except (TypeError, ValueError):
                continue
        return ids

    category_ids = _ids(data.get("category_ids"))
    channel_ids = _ids(data.get("channel_ids"))

    if not category_ids and not channel_ids:
        return jsonify(
            {"success": False, "error": "กรุณาเลือกห้องที่จะลบก่อน"}
        ), 400

    if not build_lock.acquire(blocking=False):
        return jsonify(
            {"success": False, "error": "กำลังมีงานอยู่ รอให้เสร็จก่อน"}
        ), 409

    try:
        add_log("🗑️ เริ่มลบข้อมูลเดิม...")
        future = discord_bot.run_delete(
            guild_id_int, category_ids, channel_ids, add_log
        )
        result = future.result(timeout=300)
        add_log("🎉 ลบเสร็จทั้งหมด")
        return jsonify({"success": True, "result": result})
    except Exception as exc:
        message = str(exc)
        add_log({"type": "error", "message": f"❌ {message}"})
        return jsonify({"success": False, "error": message}), 500
    finally:
        build_lock.release()


@app.route("/api/templates", methods=["POST"])
def create_template():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    categories = data.get("categories")

    if not name:
        return jsonify({"success": False, "error": "กรุณาตั้งชื่อ Template"}), 400
    if not isinstance(categories, list) or not categories:
        return jsonify({"success": False, "error": "Template ไม่มีข้อมูล"}), 400

    template_id = "custom_" + str(uuid.uuid4().hex[:10])
    custom = load_custom_templates()
    custom.append(
        {
            "id": template_id,
            "name": name,
            "category": "Custom",
            "description": "Template ที่สร้างเอง",
            "custom": True,
            "categories": categories,
        }
    )
    try:
        with open(CUSTOM_TEMPLATES_FILE, "w", encoding="utf-8") as file:
            json.dump(custom, file, ensure_ascii=False, indent=2)
    except OSError as exc:
        return jsonify({"success": False, "error": f"บันทึกไฟล์ไม่สำเร็จ: {exc}"}), 500

    return jsonify({"success": True, "template_id": template_id})


@app.route("/api/templates/delete", methods=["POST"])
def delete_template():
    data = request.get_json(silent=True) or {}

    template_id = data.get("template_id")
    if not template_id:
        return jsonify({"success": False, "error": "ไม่พบ Template"}), 400

    custom = load_custom_templates()
    remaining = [t for t in custom if t.get("id") != template_id]
    if len(remaining) == len(custom):
        return jsonify({"success": False, "error": "ไม่พบ Template นี้"}), 404

    try:
        with open(CUSTOM_TEMPLATES_FILE, "w", encoding="utf-8") as file:
            json.dump(remaining, file, ensure_ascii=False, indent=2)
    except OSError as exc:
        return jsonify({"success": False, "error": f"บันทึกไฟล์ไม่สำเร็จ: {exc}"}), 500

    return jsonify({"success": True})


@app.route("/api/logs")
def logs():
    def stream():
        while True:
            entry = log_queue.get()
            yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"

    return Response(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    try_start_bot(initial=True)
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=status_logger, daemon=True).start()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        threaded=True,
    )