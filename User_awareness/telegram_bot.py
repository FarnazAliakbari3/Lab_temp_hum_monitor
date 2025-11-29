"""Simple Telegram bot using telepot and requests.

Set envs:
- TELEGRAM_BOT_TOKEN
- REGISTRY_API_URL (default http://localhost:8080)
- ALERT_POLL_SEC (default 30)
- ALERT_COOLDOWN_SEC (default 300)
"""

import os
import time
import shlex
import requests
import telepot
from telepot.loop import MessageLoop

REGISTRY_API = os.getenv("REGISTRY_API_URL", "http://localhost:8080")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALERT_POLL_SEC = int(os.getenv("ALERT_POLL_SEC", "30"))
ALERT_COOLDOWN_SEC = int(os.getenv("ALERT_COOLDOWN_SEC", "300"))

KNOWN_CHATS = set()
_last_alert = {}


def _get(endpoint):
    url = f"{REGISTRY_API.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"error": "registry unreachable"}


def _post(endpoint, payload):
    url = f"{REGISTRY_API.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"error": "registry unreachable"}


def fmt_status(data):
    labs = data.get("labs", [])
    if not labs:
        return "No labs registered."
    lines = []
    for lab in labs:
        lines.append(f"{lab.get('lab_id')} ({lab.get('name','')})")
        thr = lab.get("thresholds", {})
        lines.append(
            f"  Thr temp {thr.get('t_low','?')}..{thr.get('t_high','?')} hum {thr.get('h_low','?')}..{thr.get('h_high','?')}"
        )
        lines.append(f"  Last sensor: {lab.get('last_sensor_seen','never')}")
        if lab.get("alerts", {}).get("sensor_offline"):
            lines.append("  ALERT: sensor offline")
        for s in lab.get("sensors", []):
            rd = s.get("reading") or {}
            lines.append(f"   - {s.get('sensor_id')} t={rd.get('t','?')} h={rd.get('h','?')} ts={rd.get('ts','?')}")
        for a in lab.get("actuators", []):
            st = a.get("state") or {}
            lines.append(f"   - {a.get('actuator_id')} {a.get('type','')} state={st.get('state','?')} ts={st.get('ts','?')}")
        lines.append("")
    return "\n".join(lines).strip()


def track_alert(lab_id, kind):
    _last_alert[(lab_id, kind)] = int(time.time())


def should_alert(lab_id, kind):
    last = _last_alert.get((lab_id, kind), 0)
    return (int(time.time()) - last) >= ALERT_COOLDOWN_SEC


def poll_alerts(bot):
    while True:
        if not KNOWN_CHATS:
            time.sleep(ALERT_POLL_SEC)
            continue
        data = _get("status")
        labs = data.get("labs", [])
        for lab in labs:
            lab_id = lab.get("lab_id")
            thr = lab.get("thresholds", {})
            for sensor in lab.get("sensors", []):
                rd = sensor.get("reading") or {}
                sid = sensor.get("sensor_id")
                t = rd.get("t")
                h = rd.get("h")
                if t is not None:
                    if t > thr.get("t_high", 999) and should_alert(lab_id, "t_high"):
                        msg = f"ALERT {lab_id}: temp {t} > {thr.get('t_high')} (sensor {sid})"
                        for chat in KNOWN_CHATS:
                            bot.sendMessage(chat, msg)
                        track_alert(lab_id, "t_high")
                    if t < thr.get("t_low", -999) and should_alert(lab_id, "t_low"):
                        msg = f"ALERT {lab_id}: temp {t} < {thr.get('t_low')} (sensor {sid})"
                        for chat in KNOWN_CHATS:
                            bot.sendMessage(chat, msg)
                        track_alert(lab_id, "t_low")
                if h is not None:
                    if h > thr.get("h_high", 999) and should_alert(lab_id, "h_high"):
                        msg = f"ALERT {lab_id}: humidity {h} > {thr.get('h_high')} (sensor {sid})"
                        for chat in KNOWN_CHATS:
                            bot.sendMessage(chat, msg)
                        track_alert(lab_id, "h_high")
                    if h < thr.get("h_low", -999) and should_alert(lab_id, "h_low"):
                        msg = f"ALERT {lab_id}: humidity {h} < {thr.get('h_low')} (sensor {sid})"
                        for chat in KNOWN_CHATS:
                            bot.sendMessage(chat, msg)
                        track_alert(lab_id, "h_low")
        time.sleep(ALERT_POLL_SEC)


def handle(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    if content_type != "text":
        return
    text = msg["text"].strip()
    parts = shlex.split(text)
    if not parts:
        return
    cmd = parts[0].lower()

    if cmd in ("/start", "/help"):
        KNOWN_CHATS.add(chat_id)
        bot.sendMessage(
            chat_id,
            "Commands:\n"
            "/status\n"
            "/list_labs\n"
            "/turn_on <lab> <actuator>\n"
            "/turn_off <lab> <actuator>\n"
            "/turn_on_all <lab>\n"
            "/turn_off_all <lab>\n"
            "/add_lab <lab> \"name\" [notes]\n"
            "/remove_lab <lab>\n"
            "/add_sensor <lab> <sensor_id> <type>\n"
            "/remove_sensor <sensor_id>\n"
            "/add_actuator <lab> <actuator_id> <type>\n"
            "/remove_actuator <actuator_id>\n",
        )
        return

    if cmd == "/status":
        data = _get("status")
        bot.sendMessage(chat_id, fmt_status(data))
        return

    if cmd == "/list_labs":
        labs = _get("labs").get("labs", [])
        if not labs:
            bot.sendMessage(chat_id, "No labs.")
        else:
            bot.sendMessage(chat_id, "\n".join(f"- {l['lab_id']} ({l.get('name','')})" for l in labs))
        return

    if cmd in ("/turn_on", "/turn_off"):
        if len(parts) != 3:
            bot.sendMessage(chat_id, f"Usage: {cmd} <lab> <actuator>")
            return
        action = "ON" if cmd == "/turn_on" else "OFF"
        payload = {"lab_id": parts[1], "actuator_id": parts[2], "action": action, "source": "bot"}
        res = _post("command", payload)
        bot.sendMessage(chat_id, "OK" if res.get("ok") else f"Error: {res.get('error','unknown')}")
        return

    if cmd in ("/turn_on_all", "/turn_off_all"):
        if len(parts) != 2:
            bot.sendMessage(chat_id, f"Usage: {cmd} <lab>")
            return
        lab_id = parts[1]
        action = "ON" if cmd == "/turn_on_all" else "OFF"
        status = _get("status")
        labs = [l for l in status.get("labs", []) if l.get("lab_id") == lab_id]
        if not labs:
            bot.sendMessage(chat_id, "Lab not found.")
            return
        errors = []
        for act in labs[0].get("actuators", []):
            payload = {"lab_id": lab_id, "actuator_id": act.get("actuator_id"), "action": action, "source": "bot"}
            res = _post("command", payload)
            if not res.get("ok"):
                errors.append(f"{act.get('actuator_id')}: {res.get('error','unknown')}")
        bot.sendMessage(chat_id, "Done." if not errors else "\n".join(errors))
        return

    if cmd == "/add_lab":
        if len(parts) < 3:
            bot.sendMessage(chat_id, "Usage: /add_lab <lab_id> \"<name>\" [notes]")
            return
        lab_id, name = parts[1], parts[2]
        notes = " ".join(parts[3:]) if len(parts) > 3 else ""
        res = _post("labs", {"lab_id": lab_id, "name": name, "notes": notes})
        bot.sendMessage(chat_id, "OK" if res.get("ok") else f"Error: {res.get('error','unknown')}")
        return

    if cmd == "/remove_lab":
        if len(parts) != 2:
            bot.sendMessage(chat_id, "Usage: /remove_lab <lab_id>")
            return
        try:
            r = requests.delete(f"{REGISTRY_API.rstrip('/')}/lab/{parts[1]}", timeout=5)
            res = r.json()
        except Exception:
            res = {"error": "registry unreachable"}
        bot.sendMessage(chat_id, "OK" if res.get("ok") else f"Error: {res.get('error','unknown')}")
        return

    if cmd == "/add_sensor":
        if len(parts) != 4:
            bot.sendMessage(chat_id, "Usage: /add_sensor <lab_id> <sensor_id> <type>")
            return
        res = _post("sensors", {"lab_id": parts[1], "sensor_id": parts[2], "type": parts[3]})
        bot.sendMessage(chat_id, "OK" if res.get("ok") else f"Error: {res.get('error','unknown')}")
        return

    if cmd == "/remove_sensor":
        if len(parts) != 2:
            bot.sendMessage(chat_id, "Usage: /remove_sensor <sensor_id>")
            return
        try:
            r = requests.delete(f"{REGISTRY_API.rstrip('/')}/sensor/{parts[1]}", timeout=5)
            res = r.json()
        except Exception:
            res = {"error": "registry unreachable"}
        bot.sendMessage(chat_id, "OK" if res.get("ok") else f"Error: {res.get('error','unknown')}")
        return

    if cmd == "/add_actuator":
        if len(parts) != 4:
            bot.sendMessage(chat_id, "Usage: /add_actuator <lab_id> <actuator_id> <type>")
            return
        res = _post("actuators", {"lab_id": parts[1], "actuator_id": parts[2], "type": parts[3]})
        bot.sendMessage(chat_id, "OK" if res.get("ok") else f"Error: {res.get('error','unknown')}")
        return

    if cmd == "/remove_actuator":
        if len(parts) != 2:
            bot.sendMessage(chat_id, "Usage: /remove_actuator <actuator_id>")
            return
        try:
            r = requests.delete(f"{REGISTRY_API.rstrip('/')}/actuator/{parts[1]}", timeout=5)
            res = r.json()
        except Exception:
            res = {"error": "registry unreachable"}
        bot.sendMessage(chat_id, "OK" if res.get("ok") else f"Error: {res.get('error','unknown')}")
        return

    bot.sendMessage(chat_id, "Unknown command. Use /help")


if __name__ == "__main__":
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN not set; exiting.")
        exit(1)
    bot = telepot.Bot(TOKEN)
    MessageLoop(bot, handle).run_as_thread()
    import threading
    t = threading.Thread(target=poll_alerts, args=(bot,), daemon=True)
    t.start()
    print("Bot running. Press Ctrl+C to exit.")
    while True:
        time.sleep(10)
