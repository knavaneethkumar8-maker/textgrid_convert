import json
import math
import requests
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ---------------- CONFIG ----------------
backendOrigin = "https://api.xn--l2bot2c0c.com/api/textgrid/full-upload"
localBackend = "http://127.0.0.1:3500/api/textgrid/full-upload"

NODE_UPLOAD_URL = backendOrigin

GRID_MS = 216

TIER_NAME_MAP = {
    "आकाश": "akash",
    "अग्नि": "agni",
    "वायु": "vayu",
    "जल": "jal",
    "पृथ्वी": "prithvi"
}

TIER_DEFS = [
    {"key": "akash",   "name": "आकाश",   "step": 216},
    {"key": "agni",    "name": "अग्नि",    "step": 108},
    {"key": "vayu",    "name": "वायु",    "step": 54},
    {"key": "jal",     "name": "जल",     "step": 27},
    {"key": "prithvi", "name": "पृथ्वी", "step": 9}
]

# ---------------- HELPERS ----------------
def is_wav(name):
    return name.lower().endswith(".wav")

def is_textgrid(name):
    return name.lower().endswith(".textgrid")

def read_textgrid(textgrid_path):
    for enc in ['utf-8-sig', 'utf-16', 'utf-8', 'latin-1']:
        try:
            with open(textgrid_path, 'r', encoding=enc) as f:
                return f.read()
        except:
            continue
    raise RuntimeError("Unable to decode TextGrid")

def send_to_nodejs(wav_path, tg_path, json_path):
    files = {
        "audio": open(wav_path, "rb"),
        "textgrid": open(tg_path, "rb"),
        "json": open(json_path, "rb")
    }

    try:
        r = requests.post(NODE_UPLOAD_URL, files=files, timeout=120)
        return r.status_code, r.text
    except Exception as e:
        return 500, str(e)
    finally:
        for f in files.values():
            f.close()

# ---------------- CORE ----------------
def parse_textgrid_to_grids(textgrid_path, audio_id):
    tg_text = read_textgrid(textgrid_path)

    lines = [l.strip() for l in tg_text.splitlines()]
    i = 0

    def next_line():
        nonlocal i
        if i >= len(lines):
            return ""
        line = lines[i]
        i += 1
        return line

    tiers = {}

    while i < len(lines):
        if not next_line().startswith("item ["):
            continue

        tier_class = ""
        tier_name = ""
        tier_key = None
        intervals = []

        while i < len(lines):
            l = next_line()
            if not l:
                continue

            if l.startswith("class"):
                tier_class = l.split("=")[1].replace('"', '').strip()

            elif l.startswith("name"):
                tier_name = l.split("=")[1].replace('"', '').strip()
                tier_key = TIER_NAME_MAP.get(tier_name)

            elif l.startswith("intervals ["):
                xmin = xmax = 0
                text = ""
                while i < len(lines):
                    il = next_line()
                    if il.startswith("xmin"):
                        xmin = float(il.split("=")[1])
                    elif il.startswith("xmax"):
                        xmax = float(il.split("=")[1])
                    elif il.startswith("text"):
                        text = il.split("=")[1].replace('"', '')
                        break

                intervals.append({
                    "start_ms": round(xmin * 1000),
                    "end_ms": round(xmax * 1000),
                    "text": text
                })

            elif l.startswith("item ["):
                i -= 1
                break

        if tier_class == "IntervalTier" and tier_key:
            tiers[tier_key] = intervals

    def text_at(intervals, s, e):
        mid = (s + e) / 2
        for it in intervals:
            if it["start_ms"] <= mid < it["end_ms"]:
                return it["text"].strip()
        return ""

    all_intervals = [i for v in tiers.values() for i in v]
    max_end = max([i["end_ms"] for i in all_intervals], default=0)
    grid_count = math.ceil(max_end / GRID_MS)

    grids = []

    for g in range(grid_count):
        cell_index = 1
        gs, ge = g * GRID_MS, (g + 1) * GRID_MS

        grid = {
            "id": f"{audio_id}_{g}",
            "index": g,
            "start_ms": gs,
            "end_ms": ge,
            "status": "LOCKED",
            "is_locked": True,
            "metadata": {},
            "tiers": {}
        }

        for t_idx, t in enumerate(TIER_DEFS):
            cells = []
            for c in range(GRID_MS // t["step"]):
                s = gs + c * t["step"]
                e = s + t["step"]
                cells.append({
                    "id": f"{audio_id}_{g}_{cell_index}",
                    "index": cell_index,
                    "start_ms": s,
                    "end_ms": e,
                    "text": text_at(tiers.get(t["key"], []), s, e),
                    "conf": 0,
                    "status": "LOCKED",
                    "is_locked": True,
                    "metadata": {}
                })
                cell_index += 1

            grid["tiers"][t["key"]] = {
                "name": t["name"],
                "index": t_idx,
                "start_ms": gs,
                "end_ms": ge,
                "cells": cells
            }

        grids.append(grid)

    return {
        "metadata": {
            "file_name": f"{audio_id}.json",
            "file_id": f"DATASETS-{audio_id}",
            "owner": "ml",
            "status": "PENDING",
            "created_at": datetime.utcnow().isoformat() + "Z"
        },
        "grids": grids
    }

# ---------------- ROUTES ----------------
@app.route('/')
def frontend():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload():
    audio = request.files.get("audio")
    textgrid = request.files.get("textgrid")

    if not audio or not textgrid:
        return render_template("index.html", message="Missing files", is_error=True)

    if not is_wav(audio.filename) or not is_textgrid(textgrid.filename):
        return render_template("index.html", message="Invalid file types", is_error=True)

    audio_name = secure_filename(audio.filename)
    audio_id = audio_name

    try:
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            wav_path = tmp / audio_name
            tg_path = tmp / secure_filename(textgrid.filename)
            json_path = tmp / f"{audio_id}.json"

            audio.save(wav_path)
            textgrid.save(tg_path)

            result = parse_textgrid_to_grids(tg_path, audio_id)

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            status, resp = send_to_nodejs(wav_path, tg_path, json_path)

        if status != 200:
            return render_template("index.html", message=f"Node upload failed: {resp}", is_error=True)

        return render_template("index.html", message=f"Converted + Stored: {audio_name}", is_error=False)

    except Exception as e:
        return render_template("index.html", message=str(e), is_error=True)

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# ---------------- RUN ----------------
if __name__ == '__main__':
    print("Running TextGrid Converter → NodeJS Storage Bridge")
    app.run(host='0.0.0.0', port=8010, debug=True)
