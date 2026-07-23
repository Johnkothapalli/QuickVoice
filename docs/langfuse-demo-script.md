# Langfuse Demo Script

Use this outline for a short 3-5 minute assignment video.

## 1. Show The Fork

Open:

```text
https://github.com/Johnkothapalli/QuickVoice/tree/langfuse-integration
```

Say:

```text
I forked QuickVoice and created a langfuse-integration branch for the assignment.
```

## 2. Show The Integration Files

Open these files:

```text
apps/ai/handlers/langfuse_handler.py
apps/ai/main.py
apps/ai/handlers/transcript_collector.py
apps/ai/scripts/langfuse_trace_smoke.py
docs/langfuse-integration.md
```

Say:

```text
The integration is in the LiveKit AI worker. Each voice session creates a Langfuse trace with call metadata, model configuration, transcript turn observations, and completion/evaluation observations.
```

## 3. Show Environment Configuration

Open `apps/ai/.env.dev` or explain the variables:

```sh
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_CAPTURE_TRANSCRIPTS=true
```

Say:

```text
Langfuse is optional. If keys are missing or LANGFUSE_ENABLED is false, QuickVoice continues running without tracing. Transcript content is redacted by default and zero-PII retention always redacts it.
```

## 4. Run The Smoke Trace

Run:

```sh
python apps/ai/scripts/langfuse_trace_smoke.py
```

Expected output:

```text
Sent Langfuse smoke trace.
Trace name: quickvoice.voice_session
Call ID: langfuse-smoke-...
```

Say:

```text
This smoke script uses the same LangfuseCallTracer helper used by the real voice worker, so it verifies ingestion without needing a live phone call during the demo.
```

## 5. Show Langfuse Dashboard

Open Langfuse and filter/search for:

```text
quickvoice.voice_session
```

or the printed:

```text
langfuse-smoke-...
```

Show:

```text
callId
agentId
provider/model metadata
transcript.user and transcript.agent observations
evaluation.call_completed
evaluation.transcript_turn_count
```

## 6. Close

Say:

```text
This demonstrates Langfuse tracing and evaluation hooks added to QuickVoice's AI voice runtime, with safe defaults and a local verification path.
```
