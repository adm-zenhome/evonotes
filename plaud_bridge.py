import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from .config import CACHE_DIR, OPENAI_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class PlaudBridge:
    """Bridge for fetching Plaud recordings, metadata, and cloud audio files."""

    def __init__(self):
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_audio(self, presigned_url: str, file_id: str) -> Path:
        """Download raw MP3 audio from S3 presigned URL to local cache."""
        target_file = self.cache_dir / f"{file_id}.mp3"
        if target_file.exists() and target_file.stat().st_size > 1000:
            logging.info(f"Audio already cached: {target_file}")
            return target_file

        logging.info(f"Downloading audio for file_id {file_id}...")
        cmd = ["curl", "-s", "-L", "-o", str(target_file), presigned_url]
        subprocess.run(cmd, check=True)
        logging.info(f"Downloaded {target_file.stat().st_size} bytes to {target_file}")
        return target_file

    def get_local_audio_path(self, file_id: str) -> Optional[Path]:
        """Returns local audio file path if cached."""
        target_file = self.cache_dir / f"{file_id}.mp3"
        return target_file if target_file.exists() else None

if __name__ == "__main__":
    bridge = PlaudBridge()
    print("PlaudBridge initialized successfully.")
