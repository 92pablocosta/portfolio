# Conversation Flow — Patient Triage

## Design Principles

- **One question at a time**: the bot never asks multiple questions in a single message — this reduces abandonment on mobile
- **No clinical scope**: the bot is explicitly prohibited from discussing procedures, prices, diagnoses, or wait times
- **Graceful fallback**: any message that falls outside the triage script triggers a human escalation
- **After-hours continuity**: triage completes regardless of business hours; the clinic follows up the next business day

---

## Triage State Machine

```
[START] — first message from a new patient
    │
    ▼
[GREETING]
  Bot: "Hello! Welcome to [Clinic Name]. I'm here to help you
       schedule an appointment. May I have your name?"
    │
    ▼
[COLLECT_NAME]
  Patient provides name
  Bot: "Nice to meet you, {Name}! Is this a routine checkup
       or do you have a specific concern you'd like to address?"
    │
    ├─► [ROUTINE]
    │     Bot: "Got it. Do you have a preference for Dr. Luiz
    │          or Dra. Bianca?"
    │
    └─► [SPECIFIC_CONCERN]
          Bot: "Understood. Do you have a preference for
               Dr. Luiz or Dra. Bianca?"
    │
    ▼
[COLLECT_DENTIST]
  Patient selects dentist (or states no preference)
  Bot: "Perfect. What day or time works best for you?
       Feel free to mention a few options."
    │
    ▼
[COLLECT_AVAILABILITY]
  Patient provides preferred day/time
    │
    ▼
[CONFIRM_TRIAGE]
  Bot: "Great — here's what I have:
        - Name: {Name}
        - Visit type: {routine / specific concern}
        - Dentist preference: {Dr. Luiz / Dra. Bianca / No preference}
        - Preferred time: {day/time}

       Our team will confirm your appointment shortly.
       Is there anything else I can note for them?"
    │
    ├─► [ADDITIONAL_NOTE] — appended to lead record
    │
    └─► [DONE] — lead record written, conversation closed
```

---

## After-Hours Behavior

The bot does **not** gate on business hours — triage runs 24/7.

When a patient completes triage outside business hours:

```
Bot: "Thank you, {Name}. Your request has been noted.
     Our receptionist will reach out to confirm your
     appointment during business hours. Have a great day!"
```

The lead record is flagged `after_hours: true` so the receptionist knows to prioritize follow-up the next morning.

---

## Escalation Triggers

The following inputs cause immediate human escalation:

| Trigger | Example patient message |
|---|---|
| Price inquiry | "How much does a cleaning cost?" |
| Procedure question | "Do you do implants? What's involved?" |
| Clinical / symptom question | "I have a broken tooth, is it an emergency?" |
| Complaint or dispute | "I was overcharged last visit" |
| Explicit human request | "Can I speak to someone?" |

**Escalation response (sent immediately):**

> "Um momento que já te respondo!"
> *(Portuguese: "One moment, I'll get back to you!")*

After sending this message, the bot:
1. Marks the session as `escalated` in Redis
2. Sends a notification to the receptionist with the patient's JID and the triggering message
3. Stops responding — all further messages from this JID are silently queued for the human

---

## Hard Constraints (enforced via system prompt)

The AI is instructed **never** to:

- Quote prices for any procedure
- Describe or explain dental procedures in clinical terms
- Suggest a diagnosis or assess urgency of symptoms
- Confirm, deny, or speculate about appointment slot availability
- Identify the clinic by its real name in any reply (placeholder used in this portfolio)

These constraints exist because unvetted information from an AI in a medical-adjacent context creates liability. The bot's only job is to collect structured scheduling intent.

---

## Sample Dialogue

```
Patient:  oi, quero marcar uma consulta

Bot:      Hello! Welcome to our clinic. I'm here to help you
          schedule an appointment. May I have your name?

Patient:  Maria

Bot:      Nice to meet you, Maria! Is this a routine checkup
          or do you have a specific concern you'd like to address?

Patient:  tenho uma dor no dente

Bot:      Understood. Do you have a preference for
          Dr. Luiz or Dra. Bianca?

Patient:  tanto faz

Bot:      No problem. What day or time works best for you?
          Feel free to mention a few options.

Patient:  semana que vem de manha, qualquer dia

Bot:      Got it. Here's what I have:
          - Name: Maria
          - Visit type: Specific concern (tooth pain)
          - Dentist preference: No preference
          - Preferred time: Next week, morning

          Our team will confirm your appointment shortly.
          Is there anything else I can note for them?

Patient:  não, obrigada

Bot:      You're welcome, Maria! We'll be in touch soon.
```

> Note: the bot responds in English in this example for portfolio clarity.
> In production, Gemini is prompted to mirror the patient's language
> (Portuguese or English) automatically.
