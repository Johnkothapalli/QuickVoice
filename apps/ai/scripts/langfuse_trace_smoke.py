from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from handlers.langfuse_handler import LangfuseCallTracer


def main() -> int:
    env_file = APP_DIR / ".env.dev"
    if env_file.exists():
        load_dotenv(env_file)

    missing = [
        name
        for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
        if not os.getenv(name)
    ]
    if missing:
        print(f"Missing required Langfuse env vars: {', '.join(missing)}")
        print("Add them to apps/ai/.env.dev or export them before running this script.")
        return 1

    os.environ.setdefault("LANGFUSE_ENABLED", "true")
    os.environ.setdefault("LANGFUSE_CAPTURE_TRANSCRIPTS", "true")

    started_at = datetime.now(timezone.utc)
    call_context = {
        "call_id": f"langfuse-smoke-{int(started_at.timestamp())}",
        "agent_id": "demo-agent",
        "direction": "preview",
        "provider": "WEB_WIDGET",
    }
    config = {
        "agent_id": "demo-agent",
        "organization_id": "demo-org",
        "user_id": "demo-user",
        "provider": "WEB_WIDGET",
        "use_rag": True,
        "ivr_navigation_enabled": False,
        "voice_config": {
            "stt": {"provider": "deepgram", "model": "nova-3"},
            "llm": {"provider": "bedrock", "model": "us.anthropic.claude-haiku-4-5"},
            "tts": {
                "provider": "elevenlabs",
                "model": "eleven_flash_v2_5",
                "voice": "EXAVITQu4vr4xnSDxMaL",
            },
        },
    }

    tracer = LangfuseCallTracer(
        config=config,
        call_context=call_context,
        room_name="langfuse-smoke-room",
        started_at=started_at,
    )
    tracer.start()
    if not getattr(tracer, "_trace", None):
        print("Langfuse tracer did not start. Check SDK installation, keys, and base URL.")
        return 1
    tracer.on_transcript_item(
        {
            "id": "demo-user-1",
            "role": "user",
            "content": "Hi, can you help me check my appointment?",
            "time": started_at,
        }
    )
    tracer.on_transcript_item(
        {
            "id": "demo-agent-1",
            "role": "agent",
            "content": "Sure, I can help with that.",
            "time": datetime.now(timezone.utc),
        }
    )
    tracer.finalize(
        ended_at=datetime.now(timezone.utc),
        transcript=[
            {"role": "user", "content": "Hi, can you help me check my appointment?"},
            {"role": "agent", "content": "Sure, I can help with that."},
        ],
        status="SMOKE_COMPLETED",
    )

    print("Sent Langfuse smoke trace.")
    print(f"Trace name: quickvoice.voice_session")
    print(f"Call ID: {call_context['call_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
