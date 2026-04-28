# Architecture — WhatsApp AI Triage Bot

## Overview

The system is built on a self-hosted n8n instance that receives webhooks from Evolution API and orchestrates the AI triage loop. All components run as Docker containers on a single VPS behind Traefik.

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│  Patient's Phone                                                │
│  WhatsApp App                                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │  WhatsApp protocol
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Evolution API v2  (Docker container)                           │
│  - Maintains WhatsApp Web session                               │
│  - Normalizes messages to JSON                                  │
│  - Fires webhook on messages.upsert event                       │
└────────────────────────┬────────────────────────────────────────┘
                         │  POST /webhook/whatsapp-triage
                         │  (via Traefik TLS termination)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  n8n Workflow                                                   │
│                                                                 │
│  1. WEBHOOK TRIGGER                                             │
│     Receives raw Evolution API payload                          │
│                                                                 │
│  2. fromMe GUARD (IF node)                                      │
│     Drops messages where key.fromMe === true                    │
│     Prevents the bot from responding to its own outbound msgs   │
│                                                                 │
│  3. REDIS BUFFER + DEBOUNCE                                     │
│     - Appends message text to a Redis list keyed by phone #     │
│     - Sets/refreshes a 3-second expiry key                      │
│     - A secondary poller checks if the expiry key is gone;      │
│       if so, flushes the list and proceeds                      │
│     - Effect: 3–5 rapid messages are collapsed into one block   │
│                                                                 │
│  4. WAIT NODE (3s)                                              │
│     Hard pause that gives Redis debounce time to settle         │
│                                                                 │
│  5. IF CHECK (debounce gate)                                    │
│     Confirms this execution is the "last one standing"          │
│     for this phone number before continuing                     │
│                                                                 │
│  6. AI AGENT (Gemini)                                           │
│     - Receives aggregated message(s) + session history          │
│     - System prompt enforces triage-only behavior               │
│     - Returns structured or conversational reply                │
│     - Stores updated conversation state back to Redis           │
│                                                                 │
│  7. EVOLUTION API — SEND MESSAGE                                │
│     HTTP node posts reply text to Evolution API                 │
│     /message/sendText/:instance endpoint                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Patient's Phone                                                │
│  Receives bot reply via WhatsApp                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Infrastructure Layout

```
VPS (Ubuntu 24.04)
│
├── Traefik (container)
│   ├── Port 80/443 exposed to internet
│   ├── Handles Let's Encrypt TLS automatically
│   └── Routes by hostname label on sibling containers
│
├── Evolution API (container)
│   ├── Internal port 8080
│   ├── Traefik label: evolution.yourdomain.com
│   └── Persistent volume: ./evolution_data
│
├── n8n (container)
│   ├── Internal port 5678
│   ├── Traefik label: n8n.yourdomain.com
│   └── Persistent volume: ./n8n_data
│
├── Redis (container)
│   ├── Internal port 6379 (not exposed externally)
│   └── Used by both Evolution API and n8n workflow
│
└── PostgreSQL (container)
    ├── Internal port 5432 (not exposed externally)
    └── n8n workflow and execution storage
```

---

## Data Flow — State Management

Each patient conversation is keyed by their WhatsApp phone number (JID).

| Key pattern | Store | TTL | Purpose |
|---|---|---|---|
| `debounce:<jid>` | Redis string | 3s | Debounce lock — presence means "still typing" |
| `buffer:<jid>` | Redis list | 30s | Accumulated raw message texts |
| `session:<jid>` | Redis string (JSON) | 24h | AI conversation history array |

When the debounce key expires, the buffer is flushed, all accumulated text is concatenated, and the AI receives the full context as a single turn.

---

## Escalation Path

When the AI detects an out-of-scope query (prices, clinical questions, complaints):

1. Gemini returns a structured flag in its response JSON
2. n8n reads the flag and sends the holding message: _"Um momento que já te respondo!"_
3. An n8n notification node alerts the receptionist (e.g., via a separate WhatsApp group or email)
4. The session is marked `escalated` in Redis — subsequent messages bypass the AI and queue for human

---

## Security Notes

- Evolution API Manager UI is protected by API key authentication
- n8n webhook endpoint validates the Evolution API signature header
- No patient data is stored beyond the 24-hour Redis TTL
- The VPS firewall (ufw) exposes only ports 22, 80, and 443
