import sys
import logging
from modules.executive_voice_os.engine import ExecutiveVoiceOS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PRESIGNED_URL = "https://plaud-bucket.s3-accelerate.amazonaws.com/audiofiles/812b22e3fd08635d2f6b5829ae163641.mp3?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIAQTHZ6MSFC64TXWMI%2F20260828%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20260828T162014Z&X-Amz-Expires=86400&X-Amz-Security-Token=IQoJb3JpZ2luX2VjEIb%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLXdlc3QtMiJIMEYCIQD0XV4vepycjPd7cNWQ6vWXbs4O7umO45319s%2F7GFM8NwIhAOItxnIOxwsRVVAorM9Qv0w7xR16s1TQ%2B9oHCNVAVkOiKvoECE8QABoMMDQxMzI2MzcxOTc4Igz42iY90D%2F5b9a63RAq1wSjnnjWGAKLIj6L3oL06fb1dThVBhYkwHczahPALTRJm04kAwoyeqSEI%2FUqWA5m1sh61wsmThukMCb6aKl0lw4BArqRoPbkUwYFf9mQx8P3EW%2B%2BIRohQoo7eAhAPZKuimU%2FuxW04Zkd7n5L90enw%2B5CcC1OoeMEOxYdq%2Fdfv0iw3V9z4VPKY%2FE4d5TksUCpoBzb%2BURVYBCCIU28izR7QsnN6t3BCv9lekFZ6%2B3Bf6TXSEvYYh4MpJi%2B2R65qF%2Ff0U0GBZBjcuOuc4rCp%2FPEy7EoEnGQqgrRY1OzO%2FgAnZzcr%2Bsq%2FLQvBqkGerpk7g8HBAyXzc2bCa%2BZu10CNnEO1ALf974cbqq9mEokJbCJBs7yaOLgh1lvaUUQXV%2FrlFrHzqVL%2F4amDCZtmTDz5%2FcKl4t45d3nF36u1JNE62%2BRqeQboYuKWfAXi%2FkvI5zHAjh%2FLnnwERn39jkBb79x2vOVsDSxNTqAg5qj29k0XtSiLi%2BPmTSGt2VLGAiETaTMiXRRbsyZwWSy1vAA4G0R0TLjoWFPnvjz5ws88Xb%2BDzdTKn6Bp3eG6UBCyFRVXxRVkZjC2Yjz5RUU0BLj2TIBZ7plKYR8BX%2FRd0ViZJfJ3p9aR9%2Fkv4A5Cdx7o7JBw6GILRRTzwVY072vWL6U66EMrmGjWdHKLBSRaJnVsLvmLxEBLBUpDzXTOAk%2BYpw7Wb%2FcJUgzPYjzN9LupmKt6wahv8tfl8MEvuyfUSeZEQz6iu0uODO5MPzFsJeC5kwe6AJKmj22ja6S6uwkbtdI6osiEcnjM8ib602wNvexajDjq8bUBjqXAR5gPnMtEuR38IpprImdfg5XcZdGuMD%2F2YKmsRMbhR%2F%2BmGfdzJSF8vBAAyKNNoK7z5ePBi9FLPmaR3XtlZ%2FyfVYp92el6GPM%2FE6ErygtwPMZI7MJwM5PNVU4YeLJPHfYI0K8askVCT5dAvsRqVVLtyoQJHlVzU5yi6C6infw8jUZCeM%2BEwyy7qvZMUFuDE55JRGGRX%2F%2F7mQ%3D&X-Amz-SignedHeaders=host&X-Amz-Signature=a701ac07c14bfa12236b59da595014ca4f2864a3cff6a665254d323043c20449"
FILE_ID = "812b22e3fd08635d2f6b5829ae163641"
FILE_META = {
    "name": "2026-08-28 12:25:13",
    "created_at": "2026-08-28 12:25:13",
    "duration": 3126
}

def main():
    engine = ExecutiveVoiceOS()
    prompt_hint = "Felipe Donato, Zendesk, vendas, pipeline, clientes, parceiros, reuniões de negócios"
    res = engine.process_plaud_recording(PRESIGNED_URL, FILE_ID, FILE_META, prompt_hint=prompt_hint)
    print("🎉 SUCESSO! Resultado:", res["document_path"])

if __name__ == "__main__":
    main()
