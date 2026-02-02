import json
import math
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ---------------- CONFIG ----------------
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

BASE_UPLOAD = Path("uploads")
AUDIO_DIR = BASE_UPLOAD / "recordings"
TEXTGRID_DIR = BASE_UPLOAD / "textgrids"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TEXTGRID_DIR.mkdir(parents=True, exist_ok=True)

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

def detect_encoding(file_path):
    for enc in ['utf-8-sig', 'utf-16', 'utf-8', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                f.read(100)
            return enc
        except:
            continue
    return 'utf-8'

# ---------------- CORE ----------------
def parse_textgrid_to_grids(textgrid_path, audio_id):
    tg_text = None
    for enc in ['utf-8-sig', 'utf-16', 'utf-8', 'latin-1']:
        try:
            with open(textgrid_path, 'r', encoding=enc) as f:
                tg_text = f.read()
            break
        except:
            continue

    if tg_text is None:
        enc = detect_encoding(textgrid_path)
        with open(textgrid_path, 'r', encoding=enc) as f:
            tg_text = f.read()

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
            "owner": "username",
            "status": "FINISHED",
            "created_at": datetime.utcnow().isoformat() + "Z"
        },
        "grids": grids
    }

# ---------------- ROUTES ----------------
@app.route('/')
def frontend():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload_single():
    audio = request.files.get("audio")
    textgrid = request.files.get("textgrid")

    if not audio or not textgrid:
        return render_template("index.html", message="Missing files")

    if not is_wav(audio.filename) or not is_textgrid(textgrid.filename):
        return render_template("index.html", message="Invalid file types")

    audio_name = secure_filename(audio.filename)
    tg_name = secure_filename(textgrid.filename)

    audio_path = AUDIO_DIR / audio_name
    tg_path = TEXTGRID_DIR / tg_name

    audio.save(audio_path)
    textgrid.save(tg_path)

    audio_id = Path(audio_name).stem
    result = parse_textgrid_to_grids(tg_path, audio_id)

    with open(TEXTGRID_DIR / f"{audio_id}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return render_template("index.html", message=f"Converted {audio_name}")

@app.route('/upload-folder', methods=['POST'])
def upload_folder():
    files = request.files.getlist("folder")

    audio_map = {}
    tg_map = {}

    for f in files:
        name = secure_filename(os.path.basename(f.filename))
        stem = Path(name).stem

        if is_wav(name):
            audio_map[stem] = f
        elif is_textgrid(name):
            tg_map[stem] = f

    processed = 0

    for audio_id in audio_map.keys() & tg_map.keys():
        audio = audio_map[audio_id]
        tg = tg_map[audio_id]

        audio_path = AUDIO_DIR / secure_filename(audio.filename)
        tg_path = TEXTGRID_DIR / secure_filename(tg.filename)

        audio.save(audio_path)
        tg.save(tg_path)

        result = parse_textgrid_to_grids(tg_path, audio_id)

        with open(TEXTGRID_DIR / f"{audio_id}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        processed += 1

    return render_template(
        "index.html",
        message=f"Batch complete: {processed} file pairs converted"
    )

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# ---------------- RUN ----------------
if __name__ == '__main__':
    print("Running TextGrid Converter")
    app.run(host='0.0.0.0', port=4500, debug=True)
