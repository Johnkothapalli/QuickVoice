from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from utils.logger import logger, redact_sensitive


TRUE_VALUES = {"1", "true", "yes", "on"}
SUCCESS_STATUSES = {"COMPLETED", "PREVIEW_COMPLETED", "SMOKE_COMPLETED"}


def langfuse_enabled() -> bool:
    if str(os.getenv("LANGFUSE_ENABLED", "true")).strip().lower() not in TRUE_VALUES:
        return False
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


class LangfuseCallTracer:
    def __init__(
        self,
        *,
        config: dict[str, Any],
        call_context: dict[str, Any],
        room_name: str,
        started_at: datetime,
        client: Any | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._config = config
        self._call_context = call_context
        self._room_name = room_name
        self._started_at = started_at
        self._client = client
        self._trace = None
        self._enabled = langfuse_enabled() if enabled is None else enabled
        self._completed = False
        self._capture_transcripts = self._should_capture_transcripts(config)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        if not self._enabled:
            return
        try:
            client = self._get_client()
            if client is None:
                self._enabled = False
                return
            self._trace = client.start_observation(
                name="quickvoice.voice_session",
                as_type="span",
                input={
                    "roomName": self._room_name,
                    "direction": self._call_context.get("direction"),
                    "agentId": self._agent_id(),
                    "callId": self._call_id(),
                },
                metadata=self._metadata(),
            )
            logger.info("[LANGFUSE] started trace for call {}", redact_sensitive(self._call_id()))
        except Exception as error:
            self._enabled = False
            logger.warning("[LANGFUSE] disabled after startup error: {}", redact_sensitive(str(error)))

    def on_transcript_item(self, item: dict[str, Any]) -> None:
        if not self._trace:
            return
        role = str(item.get("role") or "")
        if role not in {"user", "agent"}:
            return
        content = str(item.get("content") or item.get("message") or "").strip()
        try:
            event = self._trace.start_observation(
                name=f"transcript.{role}",
                as_type="span",
                input={
                    "role": role,
                    "content": content if self._capture_transcripts else "[redacted]",
                },
                metadata={
                    "messageId": str(item.get("id") or item.get("messageId") or ""),
                    "captured": self._capture_transcripts,
                },
                level="DEBUG",
            )
            event.end()
        except Exception as error:
            logger.debug("[LANGFUSE] transcript event skipped: {}", redact_sensitive(str(error)))

    def finalize(
        self,
        *,
        ended_at: datetime | None = None,
        transcript: list[dict[str, Any]] | None = None,
        status: str = "COMPLETED",
        error: str | None = None,
        flush: bool = True,
    ) -> None:
        if not self._trace or self._completed:
            return
        self._completed = True
        ended_at = ended_at or datetime.now(timezone.utc)
        duration_seconds = max(0, int((ended_at - self._started_at).total_seconds()))
        transcript_count = len(transcript or [])
        try:
            self._trace.update(
                output={
                    "status": status,
                    "durationSeconds": duration_seconds,
                    "transcriptCount": transcript_count,
                    **({"error": error} if error else {}),
                },
                metadata={
                    **self._metadata(),
                    "status": status,
                    "durationSeconds": duration_seconds,
                    "transcriptCount": transcript_count,
                    "langfuseTranscriptCapture": self._capture_transcripts,
                },
            )
            self._record_evaluation_event(
                "call_completed",
                {"value": status in SUCCESS_STATUSES, "status": status},
            )
            self._record_evaluation_event(
                "transcript_turn_count",
                {"value": transcript_count},
            )
            self._trace.end()
            if flush:
                self.flush()
            logger.info("[LANGFUSE] finalized trace for call {}", redact_sensitive(self._call_id()))
        except Exception as trace_error:
            logger.warning("[LANGFUSE] finalize skipped: {}", redact_sensitive(str(trace_error)))

    def flush(self) -> None:
        try:
            client = self._get_client()
            if client is not None:
                client.flush()
        except Exception as error:
            logger.debug("[LANGFUSE] flush skipped: {}", redact_sensitive(str(error)))

    def _record_evaluation_event(self, name: str, value: dict[str, Any]) -> None:
        if not self._trace:
            return
        event = self._trace.start_observation(
            name=f"evaluation.{name}",
            as_type="evaluator",
            input=value,
        )
        event.end()

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from langfuse import get_client

            self._client = get_client()
            return self._client
        except Exception as error:
            logger.warning("[LANGFUSE] client unavailable: {}", redact_sensitive(str(error)))
            return None

    def _metadata(self) -> dict[str, Any]:
        voice_config = self._config.get("voice_config") if isinstance(self._config.get("voice_config"), dict) else {}
        llm_config = voice_config.get("llm") if isinstance(voice_config.get("llm"), dict) else {}
        stt_config = voice_config.get("stt") if isinstance(voice_config.get("stt"), dict) else {}
        tts_config = voice_config.get("tts") if isinstance(voice_config.get("tts"), dict) else {}
        return {
            "service": "quickvoice-ai",
            "roomName": self._room_name,
            "callId": self._call_id(),
            "agentId": self._agent_id(),
            "organizationId": self._config.get("organization_id"),
            "userId": self._config.get("user_id"),
            "direction": self._call_context.get("direction"),
            "provider": self._call_context.get("provider") or self._config.get("provider"),
            "previewMode": self._call_context.get("metadata", {}).get("mode") == "preview",
            "ragEnabled": bool(self._config.get("use_rag")),
            "ivrNavigationEnabled": bool(self._config.get("ivr_navigation_enabled")),
            "llmProvider": llm_config.get("provider") or self._config.get("llm_provider"),
            "llmModel": llm_config.get("model") or self._config.get("llm_model"),
            "sttProvider": stt_config.get("provider"),
            "sttModel": stt_config.get("model") or self._config.get("stt_model"),
            "ttsProvider": tts_config.get("provider"),
            "ttsModel": tts_config.get("model") or self._config.get("tts_model"),
            "ttsVoice": tts_config.get("voice") or self._config.get("voice"),
        }

    def _call_id(self) -> str:
        return str(self._call_context.get("call_id") or self._room_name)

    def _agent_id(self) -> str:
        return str(self._call_context.get("agent_id") or self._config.get("agent_id") or "")

    @staticmethod
    def _should_capture_transcripts(config: dict[str, Any]) -> bool:
        if bool(config.get("zero_pii_retention")):
            return False
        return str(os.getenv("LANGFUSE_CAPTURE_TRANSCRIPTS", "false")).strip().lower() in TRUE_VALUES


class NoopLangfuseCallTracer:
    enabled = False

    def start(self) -> None:
        return

    def on_transcript_item(self, item: dict[str, Any]) -> None:
        return

    def finalize(self, **kwargs) -> None:
        return

    def flush(self) -> None:
        return
