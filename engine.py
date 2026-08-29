import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from plaud_bridge import PlaudBridge
from audio_pipeline import AudioPipeline
from intelligence_engine import IntelligenceEngine
from output_manager import OutputManager
from voice_briefing import VoiceBriefingEngine
from self_learning_engine import SelfLearningEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ExecutiveVoiceOS:
    """End-to-end Executive Voice OS processing pipeline with ElevenLabs Voice & Self-Learning."""

    def __init__(self):
        self.bridge = PlaudBridge()
        self.pipeline = AudioPipeline()
        self.intelligence = IntelligenceEngine()
        self.output_mgr = OutputManager()
        self.voice_briefing = VoiceBriefingEngine()
        self.learning_engine = SelfLearningEngine()

    def process_plaud_recording(self, presigned_url: str, file_id: str, metadata: Dict[str, Any], prompt_hint: Optional[str] = None, user_id: str = "felipe_donato") -> Dict[str, Any]:
        """Processes a Plaud recording from S3 URL down to the final executive document, voice briefing and learned profile."""
        logging.info(f"Starting Executive Voice OS on recording {file_id} for user {user_id}...")

        # 1. Download / Get Cached Audio
        audio_path = self.bridge.download_audio(presigned_url, file_id)

        # 2. Parallel Whisper Transcription
        transcript_data = self.pipeline.process(audio_path, file_id, prompt=prompt_hint)
        raw_text = transcript_data.get("text", "")

        # 3. Executive Intelligence Extraction (with User Context)
        meta = {
            "file_id": file_id,
            "name": metadata.get("name", "Gravação Plaud"),
            "created_at": metadata.get("created_at", metadata.get("start_at", "")),
            "duration": metadata.get("duration", transcript_data.get("duration", 0))
        }
        intel = self.intelligence.analyze(raw_text, metadata=meta, user_id=user_id)

        # 4. Generate ElevenLabs Executive Voice Podcast Briefing
        user_profile = self.learning_engine.get_or_create_profile(user_id)
        briefing_audio_path = None
        try:
            briefing_audio_path = self.voice_briefing.create_audio_briefing(file_id, intel, user_profile)
        except Exception as e:
            logging.error(f"Error generating ElevenLabs audio briefing: {e}")

        # 5. Render Markdown & Save in ~/Desktop/Zendesk
        saved_path = self.output_mgr.save_meeting(file_id, intel, meta, raw_transcript=raw_text)

        logging.info(f"🎉 Pipeline completed successfully! Report: {saved_path}")
        return {
            "status": "SUCCESS",
            "file_id": file_id,
            "document_path": str(saved_path),
            "briefing_audio_path": str(briefing_audio_path) if briefing_audio_path else None,
            "intelligence": intel,
            "transcript_length": len(raw_text)
        }

if __name__ == "__main__":
    os_instance = ExecutiveVoiceOS()
    print("ExecutiveVoiceOS with VoiceBriefing and SelfLearning ready.")
