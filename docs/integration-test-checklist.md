# Integration Test Checklist (Phase 0)

Use this checklist to validate the full chat flow described in `PHASE_0_HOW_TO_GUIDE.md` Section 11.3 (lines 2054-2066). Run everything with Docker Compose.

## Prerequisites
- `.env` exists and includes required variables from `.env.example` (notably `DEMO_PASSWORD` and `AUTH_TOKEN_SECRET`).
- Docker images built if first run or after dependency changes: `docker-compose build`.
- Services running: `docker-compose up -d` then `docker-compose ps` shows backend/frontend are `Up`.
- Browser uses a fresh session (incognito is fine) to avoid stale cookies.

## Checklist
- [ ] Start services: `docker-compose up -d && sleep 15` (or until `docker-compose ps` reports `Up`).
- [ ] Open `http://localhost:3000` → login page loads (redirect from `/`).
- [ ] Login with password from `.env` (`DEMO_PASSWORD`) → redirect to chat with no toast errors.
- [ ] Send initial message `Hello, how are you?` → `POST /api/chat` returns a `conversationId` (check DevTools Network) and SSE stream opens.
- [ ] Streaming response appears in UI (assistant bubble grows) with no red toasts; SSE events show `message`/`tool_result`/`complete`.
- [ ] Agent responds (non-empty assistant message) even if tools are mocked.
- [ ] Browser console shows no errors or uncaught exceptions during interaction.
- [ ] Backend logs clean: monitor with `docker-compose logs -f backend` while chatting; no tracebacks.
- [ ] Conversation ID persists: subsequent SSE events and chat POSTs reuse the same id; state is maintained.
- [ ] Send a follow-up message and confirm response uses prior context (no reset).

## Record Results
- Date / tester:
- Environment (local Docker):
- Notes, issues found, and links to logs or screenshots:
