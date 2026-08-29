import time
import json
import logging
import urllib.request
from pathlib import Path
from engine import ExecutiveVoiceOS
from config import OPENAI_API_KEY, DESKTOP_ZENDESK_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

FILE_ID = "812b22e3fd08635d2f6b5829ae163641"
DURATION_SEC = 3126

def poll_and_process():
    logging.info(f"Iniciando monitoramento autônomo para o arquivo {FILE_ID} (52 min)...")
    
    # We poll the Plaud MCP / API or wait until presigned_url is available
    engine = ExecutiveVoiceOS()
    
    # We will log progress
    logging.info("Aguardando finalização do upload Bluetooth/Wi-Fi do hardware para a nuvem da Plaud...")

if __name__ == "__main__":
    poll_and_process()
