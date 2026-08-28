import json
import logging
from pathlib import Path
from .intelligence_engine import IntelligenceEngine
from .output_manager import OutputManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def seed():
    engine = IntelligenceEngine()
    out_mgr = OutputManager()

    # 1. Process BCR + Blue3 Call
    transcript_call2 = "/Users/felipe/.gemini/antigravity/brain/a8e25b52-7e03-4291-a700-14a1b1370af1/scratch/transcript_plain.txt"
    if Path(transcript_call2).exists():
        logging.info("Processing Call 2 (BCR + Blue3)...")
        with open(transcript_call2, "r", encoding="utf-8") as f:
            text2 = f.read()

        meta2 = {
            "name": "2026-08-28 10:07:51 — Pipeline ZCC com BCR & Demo Blue3",
            "created_at": "2026-08-28 10:07:51",
            "duration": 2461
        }
        intel2 = engine.analyze(text2, metadata=meta2)
        out_mgr.save_meeting("35321aa7eca9033f91bd5de7bd9f2951", intel2, meta2, raw_transcript=text2)
        logging.info("Call 2 saved.")

    # 2. Process Morning Session
    transcript_call1 = "/Users/felipe/.gemini/antigravity/brain/a8e25b52-7e03-4291-a700-14a1b1370af1/scratch/transcript_0927.json"
    if Path(transcript_call1).exists():
        logging.info("Processing Call 1 (Mentoria Matinal)...")
        with open(transcript_call1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
            text1 = data1.get("text", "")

        meta1 = {
            "name": "2026-08-28 09:27:49 — Sessão Matinal: Quebra de Ciclos & Alavancagem",
            "created_at": "2026-08-28 09:27:49",
            "duration": 1771
        }
        intel1 = engine.analyze(text1, metadata=meta1)
        out_mgr.save_meeting("fbe95d6daf6e44054d840052b276f3a2", intel1, meta1, raw_transcript=text1)
        logging.info("Call 1 saved.")

    print("🎉 Database successfully seeded with today's meetings!")

if __name__ == "__main__":
    seed()
