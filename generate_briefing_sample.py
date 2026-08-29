import json
import logging
from voice_briefing import VoiceBriefingEngine
from self_learning_engine import SelfLearningEngine
from config import DATABASE_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    vb = VoiceBriefingEngine()
    sle = SelfLearningEngine()
    prof = sle.get_or_create_profile("felipe_donato")

    with open(DATABASE_FILE, "r", encoding="utf-8") as f:
        meetings = json.load(f)

    # Process all meetings in DB to generate audio briefings
    for m in meetings:
        file_id = m.get("file_id")
        intel = m.get("intelligence", {})
        logging.info(f"Generating audio briefing for: {intel.get('meeting_title')} ({file_id})...")
        audio_path = vb.create_audio_briefing(file_id, intel, prof)
        if audio_path:
            m["briefing_audio_path"] = str(audio_path)
            logging.info(f"Audio briefing attached: {audio_path}")

    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(meetings, f, indent=2, ensure_ascii=False)

    print("🎉 All audio briefings generated successfully!")

if __name__ == "__main__":
    main()
