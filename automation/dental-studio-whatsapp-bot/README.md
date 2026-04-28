# WhatsApp AI Triage Bot — Dental Clinic

> AI-powered WhatsApp assistant that automates patient intake and appointment scheduling for a dental clinic, reducing receptionist workload and ensuring 24/7 responsiveness.

---

## Problem

A busy dental clinic was handling all appointment requests manually via WhatsApp. Receptionists spent significant time answering the same qualifying questions (reason for visit, preferred dentist, availability) before a booking could even be initiated — including messages arriving outside business hours that went unanswered until the next day, causing patient drop-off.

---

## Solution

An automated triage bot that engages every incoming WhatsApp message, collects structured appointment intent (name, reason, preferred dentist, preferred time), and stores a qualified lead for the receptionist to confirm and schedule — in under 2 minutes, around the clock.

Key behaviors:
- **Debounced intake**: buffers rapid consecutive messages (common on mobile) before triggering AI, avoiding fragmented conversations
- **Scoped AI**: Gemini is prompted strictly as a triage assistant — it does not quote prices, diagnose, or deviate from the intake script
- **Graceful escalation**: recognizes out-of-scope queries and hands off to a human with a holding message
- **After-hours awareness**: completes triage regardless of time, flags the lead for next-business-day follow-up

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full message flow diagram and component breakdown.

```
WhatsApp → Evolution API (webhook) → n8n workflow
                                          │
                              ┌───────────┴────────────┐
                              │  fromMe guard (filter)  │
                              └───────────┬────────────┘
                                          │
                              ┌───────────┴────────────┐
                              │  Redis buffer + 3s      │
                              │  debounce timer         │
                              └───────────┬────────────┘
                                          │
                              ┌───────────┴────────────┐
                              │  AI Agent (Gemini)      │
                              │  triage prompt          │
                              └───────────┬────────────┘
                                          │
                              ┌───────────┴────────────┐
                              │  Evolution API          │
                              │  send reply             │
                              └────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Messaging | WhatsApp (via Evolution API v2) | Channel + webhook source |
| Orchestration | n8n (self-hosted) | Workflow automation engine |
| AI | Google Gemini (via API) | Natural language triage agent |
| State / Buffer | Redis | Message debounce + session memory |
| Reverse Proxy | Traefik | TLS termination, routing |
| Containerization | Docker + Docker Compose | Service isolation and deployment |
| Infrastructure | Ubuntu 24.04 VPS | Self-hosted, cost-effective hosting |

---

## Key Technical Decisions

- **Debounce via Redis instead of n8n wait node**: WhatsApp users often send 3–5 short messages in quick succession. A simple wait node would create parallel executions. Redis lets us collapse those into a single aggregated message before the AI sees it, producing coherent context and avoiding race conditions.

- **Self-hosted Evolution API over cloud WhatsApp BSP**: For a small clinic, the cost of a verified BSP was prohibitive. Evolution API provides full WhatsApp Web session control at infrastructure cost only, while staying within the clinic's budget.

- **Gemini over GPT-4 for cost at this volume**: The clinic's message volume is low-to-medium. Gemini's pricing at this tier is significantly lower while remaining capable enough for structured triage conversations. The prompt is tightly scoped, so raw model capability is less critical than cost.

- **Strict system prompt with negative constraints**: The AI prompt explicitly lists what the bot must NOT do (quote prices, discuss procedures, make diagnoses). This is safer than relying on general model alignment — it prevents patients from extracting unvetted medical or financial information.

- **Traefik for TLS instead of nginx**: Traefik integrates natively with Docker labels and handles Let's Encrypt certificate renewal automatically, removing manual cert rotation from the operational surface.

---

## How to Run

### Prerequisites

- Docker and Docker Compose installed on a Linux VPS
- A domain name with DNS pointing to the VPS (required for Traefik TLS)
- A Google Gemini API key
- WhatsApp account to pair with Evolution API

### 1. Clone and configure

```bash
git clone <this-repo>
cd dental-studio-whatsapp-bot
cp .env.example .env
# Edit .env with your actual values
```

### 2. Start Evolution API

```bash
cd docker/evolution
docker compose up -d
```

Pair your WhatsApp instance via the Evolution API Manager UI, then note your instance name and API key.

### 3. Start n8n

```bash
cd docker/n8n
docker compose up -d
```

Access n8n at `https://<your-domain>` and import `n8n/workflow.json`.

### 4. Configure the webhook

In Evolution API, set the webhook URL to:
```
https://<your-n8n-domain>/webhook/whatsapp-triage
```

Enable the `messages.upsert` event.

### 5. Test

Send a WhatsApp message to the paired number. The bot should respond within a few seconds.

---

## Results / Impact

- **Response time**: from average 4+ hours (manual) to under 15 seconds, 24/7
- **Receptionist workload**: routine triage questions eliminated from the manual queue
- **Lead capture**: after-hours messages that previously went cold are now fully triaged and queued for follow-up
- **Scope containment**: zero incidents of the bot providing pricing or clinical information in production
