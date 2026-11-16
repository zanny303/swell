# SWELL provider setup — one provider field set

Use Connections → SWELL AI provider. One active provider is selected at a time.

| Provider | Base URL | Model discovery |
|---|---|---|
| Anthropic | `https://api.anthropic.com` | Load available models |
| OpenAI | `https://api.openai.com/v1` | Load available models |
| Meta Model API | `https://api.meta.ai/v1` | Load available models |
| Ollama local | `http://127.0.0.1:11434/v1` | Load available models |
| Custom compatible | your HTTPS `/v1` base URL | if the endpoint implements `/models` |

Save the provider and key first, then click Load available models. Select the exact model ID returned for your account. Then click Save settings and Test AI generation.

Meta Model API documents bearer-token authentication and both `/v1/chat/completions` and `/v1/models`. Ollama's local OpenAI-compatible endpoint does not require a key. A custom endpoint must follow the OpenAI Chat Completions request/response schema.

If you do not want any external generative AI, choose Evidence-only. The science pipeline, deterministic scenario parser, BM25 research retrieval and stakeholder decision ledger remain available.

Do not paste API keys into browser developer tools, chat messages, GitHub, screenshots, or source files. Keys are saved in the local `.env` file, which is ignored by Git.
