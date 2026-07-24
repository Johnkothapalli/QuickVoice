import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from handlers.langfuse_handler import LangfuseCallTracer, langfuse_enabled


class FakeObservation:
    def __init__(self, name):
        self.name = name
        self.children = []
        self.updates = []
        self.scores = []
        self.ended = False

    def start_observation(self, name, **kwargs):
        child = FakeObservation(name)
        child.kwargs = kwargs
        self.children.append(child)
        return child

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self

    def end(self):
        self.ended = True
        return self

    def score_trace(self, **kwargs):
        self.scores.append(kwargs)


class FakeClient:
    def __init__(self):
        self.root = None
        self.flushed = False

    def start_observation(self, name, **kwargs):
        self.root = FakeObservation(name)
        self.root.kwargs = kwargs
        return self.root

    def flush(self):
        self.flushed = True


class LangfuseHandlerTests(unittest.TestCase):
    def test_langfuse_enabled_requires_keys_and_enabled_flag(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(langfuse_enabled())
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_ENABLED": "true",
                "LANGFUSE_PUBLIC_KEY": "pk",
                "LANGFUSE_SECRET_KEY": "sk",
            },
            clear=True,
        ):
            self.assertTrue(langfuse_enabled())
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_ENABLED": "false",
                "LANGFUSE_PUBLIC_KEY": "pk",
                "LANGFUSE_SECRET_KEY": "sk",
            },
            clear=True,
        ):
            self.assertFalse(langfuse_enabled())

    def test_call_tracer_records_redacted_transcript_events_and_completion(self):
        client = FakeClient()
        started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        tracer = LangfuseCallTracer(
            config={
                "agent_id": "agent-1",
                "organization_id": "org-1",
                "voice_config": {
                    "llm": {"provider": "bedrock", "model": "claude"},
                    "stt": {"provider": "deepgram", "model": "nova-3"},
                    "tts": {"provider": "elevenlabs", "model": "flash", "voice": "voice-1"},
                },
            },
            call_context={"call_id": "call-1", "direction": "inbound"},
            room_name="room-1",
            started_at=started_at,
            client=client,
            enabled=True,
        )

        with patch.dict(os.environ, {"LANGFUSE_CAPTURE_TRANSCRIPTS": "false"}, clear=False):
            tracer.start()
            tracer.on_transcript_item({"id": "msg-1", "role": "user", "content": "private text"})
            tracer.finalize(
                ended_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
                transcript=[{"role": "user", "content": "private text"}],
                status="SMOKE_COMPLETED",
            )

        self.assertEqual(client.root.name, "quickvoice.voice_session")
        self.assertEqual(client.root.children[0].name, "transcript.user")
        self.assertEqual(client.root.children[0].kwargs["input"]["content"], "[redacted]")
        self.assertTrue(client.root.ended)
        self.assertTrue(client.flushed)
        self.assertEqual(client.root.updates[-1]["output"]["durationSeconds"], 5)
        self.assertEqual(client.root.updates[-1]["output"]["transcriptCount"], 1)
        call_completed = next(
            child for child in client.root.children if child.name == "evaluation.call_completed"
        )
        self.assertEqual(call_completed.kwargs["input"], {"value": True, "status": "SMOKE_COMPLETED"})
        self.assertEqual(
            client.root.scores,
            [
                {
                    "name": "call_completed",
                    "value": 1.0,
                    "data_type": "BOOLEAN",
                    "comment": "Final call status: SMOKE_COMPLETED",
                },
                {
                    "name": "transcript_turn_count",
                    "value": 1.0,
                    "data_type": "NUMERIC",
                    "comment": None,
                },
            ],
        )

    def test_zero_pii_retention_redacts_content_but_preserves_turn_count(self):
        client = FakeClient()
        tracer = LangfuseCallTracer(
            config={"agent_id": "agent-1", "zero_pii_retention": True},
            call_context={"call_id": "call-1"},
            room_name="room-1",
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            client=client,
            enabled=True,
        )

        with patch.dict(os.environ, {"LANGFUSE_CAPTURE_TRANSCRIPTS": "true"}, clear=False):
            tracer.start()
            tracer.on_transcript_item({"role": "user", "content": "private text"})
            tracer.finalize(
                transcript=[
                    {"role": "user", "content": "private text"},
                    {"role": "agent", "content": "private reply"},
                ]
            )

        self.assertEqual(client.root.children[0].kwargs["input"]["content"], "[redacted]")
        self.assertEqual(client.root.updates[-1]["output"]["transcriptCount"], 2)
        turn_count = next(
            score for score in client.root.scores if score["name"] == "transcript_turn_count"
        )
        self.assertEqual(turn_count["value"], 2.0)


if __name__ == "__main__":
    unittest.main()
