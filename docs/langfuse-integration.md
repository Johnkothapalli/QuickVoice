# Langfuse Integration

QuickVoice can emit Langfuse traces from the `apps/ai` LiveKit voice runtime. Each voice session creates a `quickvoice.voice_session` trace span with call metadata, model/provider selections, transcript turn events, and end-of-call evaluation events.

## Enable Locally

Add Langfuse credentials to `apps/ai/.env.dev`:

```sh
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_CAPTURE_TRANSCRIPTS=false
```

Use `https://us.cloud.langfuse.com`, `https://jp.cloud.langfuse.com`, or a self-hosted URL if your Langfuse project is not in the default EU cloud region.

`LANGFUSE_CAPTURE_TRANSCRIPTS` defaults to `false` so transcript event content is redacted while turn counts and roles remain observable. Agent configurations with `zero_pii_retention` always redact transcript content regardless of this flag.

## What Is Traced

- call/session start with `callId`, `agentId`, `roomName`, direction, provider, and organization/user IDs
- configured STT, LLM, and TTS providers/models
- transcript turn events for user and agent messages
- end status, duration, transcript turn count, and evaluation events

## Demo Flow

1. Start QuickVoice with the AI worker and API configured.
2. Start a preview or LiveKit voice session from the console/API.
3. Speak or send a few transcript turns.
4. End the session.
5. Open Langfuse and filter traces by `quickvoice.voice_session` or the `callId` shown in QuickVoice logs.

If LiveKit credentials are not available yet, run the local smoke script to verify Langfuse ingestion with the same tracing helper used by the worker:

```sh
cd apps/ai
python scripts/langfuse_trace_smoke.py
```

Then open Langfuse and filter for `quickvoice.voice_session` or the printed `langfuse-smoke-*` call ID.
