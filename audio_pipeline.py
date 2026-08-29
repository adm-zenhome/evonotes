import os
import json
import subprocess
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any
from openai import OpenAI
from config import CACHE_DIR, OPENAI_API_KEY, CHUNK_DURATION_SECONDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class AudioPipeline:
    """High-speed parallel chunked transcription engine using ffmpeg and Whisper."""

    def __init__(self, api_key: str = OPENAI_API_KEY):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)

    def optimize_audio(self, input_path: Path, output_path: Path) -> Path:
        """Converts raw audio to optimized 16kHz mono 32kbps MP3."""
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
            str(output_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_path

    def segment_audio(self, compressed_path: Path, chunk_dir: Path) -> List[Path]:
        """Splits compressed audio into 10-minute segments."""
        chunk_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-i", str(compressed_path),
            "-f", "segment", "-segment_time", str(CHUNK_DURATION_SECONDS),
            "-c", "copy", str(chunk_dir / "chunk_%03d.mp3")
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        chunks = sorted(list(chunk_dir.glob("chunk_*.mp3")))
        return chunks

    def transcribe_chunk(self, args) -> tuple:
        idx, chunk_file, prompt = args
        logging.info(f"Transcribing chunk {idx} ({chunk_file.name})...")
        with open(chunk_file, "rb") as f:
            resp = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                prompt=prompt or "Felipe Donato, Zendesk, BCR, Salesforce, VTEX, ZCC, clientes, reuniões de vendas",
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        data = resp.to_dict() if hasattr(resp, "to_dict") else resp.model_dump()
        return idx, data

    def process(self, audio_path: Path, file_id: str, prompt: str = None) -> Dict[str, Any]:
        """Runs the complete parallel transcription pipeline."""
        work_dir = CACHE_DIR / file_id
        work_dir.mkdir(parents=True, exist_ok=True)

        compressed_audio = work_dir / "compressed.mp3"
        chunks_dir = work_dir / "chunks"

        logging.info(f"Optimizing audio: {audio_path.name}...")
        self.optimize_audio(audio_path, compressed_audio)

        logging.info("Segmenting audio into parallel chunks...")
        chunks = self.segment_audio(compressed_audio, chunks_dir)
        logging.info(f"Created {len(chunks)} chunks for parallel processing.")

        tasks = [(i, chunk, prompt) for i, chunk in enumerate(chunks)]
        with ThreadPoolExecutor(max_workers=min(len(chunks), 8)) as executor:
            results = list(executor.map(self.transcribe_chunk, tasks))

        results.sort(key=lambda x: x[0])

        full_text = []
        all_segments = []

        for idx, res in results:
            offset = idx * CHUNK_DURATION_SECONDS
            full_text.append(res.get("text", ""))
            for seg in res.get("segments", []):
                seg_dict = dict(seg) if not isinstance(seg, dict) else seg
                seg_dict["start"] += offset
                seg_dict["end"] += offset
                all_segments.append(seg_dict)

        transcript_data = {
            "file_id": file_id,
            "text": "\n\n".join(full_text),
            "segments": all_segments,
            "duration": all_segments[-1]["end"] if all_segments else 0.0
        }

        output_json = work_dir / "transcript.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)

        logging.info(f"Transcription complete: {len(transcript_data['text'])} chars.")
        return transcript_data

if __name__ == "__main__":
    pipeline = AudioPipeline()
    print("AudioPipeline ready.")
