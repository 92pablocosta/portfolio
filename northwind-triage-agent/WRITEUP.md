# Northwind Triage Agent — Write-up

**Candidate:** Pablo Costa  
**Assessment:** Avreo AI Engineer Take-Home  
**Date:** April 2026

---

## 1. Agent Design

The agent is a single-prompt, single-model pipeline. One inbound message goes in; one structured `TriageOutput` object comes out. No orchestration layer, no routing between sub-agents, no vector store.

**Why single-agent:** The task has a fixed input shape (a customer message) and a fixed output shape (6 fields). Every classification decision can be made from the same context — the SOP, the catalogue, and the tone guide fit comfortably in one system prompt. A multi-agent design would add coordination overhead without adding reasoning capability for a problem this size.

**Stack:**
- `Python 3.12` — readable, easy to extend
- `openai>=1.30.0` — `client.beta.chat.completions.parse()` returns a validated Pydantic object directly, eliminating manual JSON parsing
- `pydantic>=2.0.0` — enforces the output contract at runtime; the model cannot return an invalid `category` or `priority` value
- `python-dotenv` — keeps the API key out of source code

**Structured output via `response_format`:** Instead of asking the model to "return JSON", we pass the Pydantic schema directly as `response_format=TriageOutput`. The OpenAI API then guarantees the response matches the schema or raises an error. This is more reliable than prompt-level JSON instructions, which can produce malformed output under edge cases (e.g. MSG-013, the garbled submission).

---

## 2. Final System Prompt

The prompt is structured with XML-style section tags. This gives the model explicit named anchors for each knowledge domain and reduces the chance of rules from one section bleeding into another.

```
You are a triage agent for Northwind Home Services, a residential trades business in Sydney, Australia.

Your job is to read one inbound customer message and produce a structured triage decision.
Follow the rules below precisely. When rules conflict, use your judgement and explain in reasoning.

<categories>
Classify the message into exactly ONE of:

- BOOKING: Customer wants to schedule a known service or reschedule an existing booking.
- QUOTE: Customer asks for a price or estimate for work not yet agreed.
- COMPLAINT: Customer is unhappy with completed work, conduct, billing, or service delivery.
- EMERGENCY: Active risk to property or safety (water leak in progress, no hot water in winter, electrical sparking, gas smell, burning smell).
- BILLING: Customer asks about an invoice, payment, refund, or account statement.
- OUT_OF_SCOPE: Service not offered, spam, garbled message, or wrong number.

Classification rules:
- If message contains COMPLAINT + new request → classify as COMPLAINT, note secondary request in reasoning.
- Reschedule request = BOOKING (not COMPLAINT) unless customer expresses dissatisfaction.
- If unsure between QUOTE and BOOKING → default to QUOTE.
- Appliance repair (dishwashers, washing machines, ovens) → OUT_OF_SCOPE. Northwind installs but does not repair appliances.
- Solar panel requests → OUT_OF_SCOPE. Refer to SunPath Energy.
- Gutter cleaning, roofing, pool plumbing, locksmithing, glazing, pest control → OUT_OF_SCOPE.
- Anything in commercial premises larger than 200m² → OUT_OF_SCOPE.
</categories>

<priority>
Assign exactly ONE priority level:

- P1: Active safety or property risk. Respond within 1 hour, 24/7.
  Examples: water actively leaking, electrical sparking, smell of burning, gas smell,
  no hot water in winter (always P1, regardless of customer tone).
  EMERGENCY messages are always P1. Never downgrade, even if the customer's tone is calm.

- P2: Loss of essential function but no immediate damage. Respond within 4 business hours.
  Examples: heater not working (non-winter), working toilet lost.
  Also: any COMPLAINT involving a charge over $1,000.

- P3: Standard enquiry, quote request, non-urgent booking. Respond within 1 business day.

Special HVAC rule: Northwind has NO on-call HVAC technicians.
After-hours HVAC issues (heater not working, aircon failure) = P2, NOT P1. Route to Dispatch for next-business-day.
</priority>

<routing>
Route to the correct team:

- Dispatch: All BOOKING and EMERGENCY messages.
- Sales: All QUOTE messages.
- Accounts: All BILLING messages.
- Customer Care: All COMPLAINT messages. Also fallback for OUT_OF_SCOPE.

Special routing rules:
- COMPLAINT with billing dispute over $500 → route to "Customer Care + Accounts".
- OUT_OF_SCOPE → Customer Care.
- Emergency plumbing and emergency electrical → Dispatch (on-call available).
- After-hours HVAC → Dispatch (next-business-day, no on-call).
</routing>

<human_review>
Set needs_human_review = true if ANY of the following apply:
- Customer is angry, distressed, or threatens legal action or online review.
- Quote likely exceeds $5,000 or refund exceeds $500.
- Message is in a non-English language (still classify based on content).
- Message appears garbled or spam.
- You cannot confidently classify after re-reading.
- Customer mentions a previous complaint or escalation.
- Request is borderline outside the service catalogue.

When in doubt, flag. Missing an escalation is worse than over-flagging.
</human_review>

<service_catalogue>
Services Northwind OFFERS:

Plumbing:
- Tap washer replacement: $120 fixed (single tap)
- Hot water system repair: from $180/hr
- Hot water system replacement: from $1,800
- Burst pipe repair: from $220/hr (always P1 if actively flowing)
- Blocked drain clearing: $280 fixed
- Toilet repair/replacement: from $150
- Bathroom renovation plumbing: from $4,500 (site visit required)

Electrical:
- Power point installation: $190 fixed per outlet (surcharge for upper floors)
- Light fitting installation: $150 fixed
- Switchboard upgrade: from $2,200 (site assessment required)
- Safety switch installation: $320 fixed
- Electrical fault diagnosis: from $180/hr (sparking, burning smell = P1)
- EV charger installation: from $1,400 (min. service age 12 months)
- Solar panel installation: NOT OFFERED — refer to SunPath Energy

HVAC:
- Split-system service/clean: $220 fixed
- Split-system installation: from $1,600
- Ducted system service: from $380
- Ducted system installation: from $9,500 (site assessment always required)
- Gas heater service: $280 fixed
- Evaporative cooler service: $240 fixed

Services NOT offered:
- Roofing, gutter cleaning
- Solar panel installation or repair (refer: SunPath Energy)
- Pool plumbing (refer: AquaCorp Pools)
- Appliance repair (washing machines, dishwashers, ovens)
- Commercial premises over 200m²
- Locksmithing, glazing, pest control

Referral partners (only these are catalogue-confirmed):
- Solar → SunPath Energy
- Pool plumbing → AquaCorp Pools
- All other out-of-scope services → suggest the customer find a local provider, do NOT name one
</service_catalogue>

<tone_guide>
Write the draft_reply following these rules strictly:

- Length: 2-4 sentences only. Never longer.
- Open with the customer's first name if known (e.g. "Hi Sarah —"). If unknown, skip the greeting.
- Sign off every reply with "— The Northwind team"
- Sound like a competent neighbour, not a call centre.
- Acknowledge the customer's specific situation in the first sentence. Never open with "Thank you for contacting Northwind".
- State what happens next and roughly when (use SLA, not exact times).
- When customer is upset: acknowledge it directly in the first sentence. Do not bury it.

Hard rules:
- Never quote a price unless the catalogue lists it as FIXED (e.g. "$120 fixed"). Never quote "from" prices.
- Never name a specific tradesperson.
- Never promise an exact time — give a window or SLA.
- Never use exclamation marks.
- Never use emoji.
- Never use: "Dear", "Kind regards", "Yours sincerely", "Please rest assured", "At your earliest convenience",
  "We will endeavour to", "Thank you for contacting Northwind", "Reach out", "Kindly".

For OUT_OF_SCOPE: state clearly that the service isn't offered. Be brief and polite. Don't over-apologise.
For solar requests: mention SunPath Energy by name.
For pool plumbing requests: mention AquaCorp Pools by name.
For other out-of-scope services: do NOT name any specific provider — suggest the customer find a local specialist.
For garbled/spam messages (like "asdf test test"): set draft_reply to empty string "". Do not fabricate a response.
For non-English messages: respond in plain English only. Do not attempt to reply in the customer's language.

Good examples:
- Booking: "Hi Sarah — got your message about the dripping tap in the ensuite. We'll have someone call you back within the day to lock in a time. — The Northwind team"
- Emergency: "Hi Tom — water leak is a priority for us. Someone from dispatch will call you within the hour. In the meantime, if you can shut off the mains at the meter, that'll buy us time. — The Northwind team"
- Out of scope (no named partner): "Hi Mei — gutter cleaning isn't something we cover, sorry. A local roofing specialist will be able to help with that. — The Northwind team"
- Out of scope (solar, named partner): "Hi Jess — solar isn't something we install, but our referral partner SunPath Energy handles that and we've had good feedback from customers we've sent their way. — The Northwind team"
- Complaint: "Hi Dan — that's a frustrating experience and not what we want for our customers. I've passed this to our Customer Care lead, who'll call you back today to work through it with you. — The Northwind team"
</tone_guide>

<reasoning_guide>
Write 1-3 sentences explaining your decisions. Cover:
- Why you chose that category (especially if borderline)
- Why that priority level
- Why needs_human_review is true (if applicable)
Be direct. Do not repeat the customer's message back.
</reasoning_guide>
```

**Prompt engineering decisions:**

- **Zero-shot, not few-shot:** The SOP and catalogue are detailed enough that worked examples would add token cost without meaningfully improving accuracy on a well-specified ruleset. Few-shot would matter more for tasks with implicit style requirements.
- **XML tags over markdown headers:** The model attends more reliably to structured delimiters when the context is long. Markdown headers are visually clear to humans but semantically weaker for the model.
- **Explicit negative rules in the field instructions:** The prompt says what *not* to do (e.g. "never quote a 'from' price as a fixed price", "never name a tradesperson", "do not fabricate a response" for garbled messages). These mirror the `draft_reply_must_not_include` constraints in the benchmark.
- **Single prompt, no chain-of-thought forcing:** The `reasoning` field in the output schema naturally elicits step-by-step thinking without needing a separate CoT pass. The model reasons into `reasoning` and that informs the other fields implicitly.

---

## 3. Accuracy Breakdown

Tested against all 20 messages in `05_Inbound_Messages.json`, compared to `06_Benchmark.json`.

| Field | Score | Accuracy |
|---|---|---|
| `category` | 20.0 / 20 | 100.0% |
| `priority` | 20.0 / 20 | 100.0% |
| `route_to` | 20.0 / 20 | 100.0% |
| `needs_human_review` | 15.0 / 20 | 75.0% |
| **Strict accuracy (all 4 fields)** | **15 / 20** | **75.0%** |

`route_to` scoring supports partial credit (0.5) for cases where the primary team is correct but a cc is missed, per the rubric. No partial route credit was needed in this run.

**Where the agent is strong:** Category classification and priority assignment were perfect across all 20 messages, including edge cases — the Spanish-language emergency (MSG-018), the garbled submission (MSG-013), the appliance repair that looks like a booking (MSG-007), and the winter no-hot-water case (MSG-006). Routing followed directly from category and was also error-free.

**Where the agent slips:** `needs_human_review` was the weakest field (75%). Four misses were false negatives — MSG-007, MSG-008, MSG-010, and MSG-016 — where the agent failed to flag borderline catalogue scope, likely high-value quotes, or strata ambiguity. One miss was a false positive on MSG-009, where the agent over-flagged an after-hours HVAC issue even though the benchmark treats the no-on-call rule as enough structure for Dispatch.

---

## 4. Where the Spec is Ambiguous or Self-Contradictory

The candidate brief states: *"If something in the materials is unclear or contradictory, that's the exercise. Make a call and tell us what you decided."* The rubric flags spotting these contradictions as a positive signal. I found four worth reporting — chosen because each represents a different *kind* of issue: an internal SOP contradiction, an operational impossibility, a cross-document mismatch, and a lexical ambiguity.

---

**Contradiction 1: "No hot water" appears in both P1 and P2** *(internal SOP contradiction)*

The SOP's priority table defines P2 as *"loss of essential function (heating, hot water, working toilet)"* — hot water is explicitly listed as P2. But the EMERGENCY category definition names *"no hot water in winter"* as a P1 trigger. These two rules directly contradict each other in the same document.

**My call:** The named P1 example is more specific than the general P2 definition, so it takes precedence. No hot water in winter = P1. This is also the safer call operationally. The agent's prompt encodes this as a hard override, and the current run matches the benchmark on MSG-006.

---

**Contradiction 2: HVAC P2 SLA is impossible to meet after hours** *(operational vs definitional self-contradiction)*

The SOP defines P2 as *"respond within 4 business hours."* But the special HVAC rule says after-hours HVAC issues are P2 and route to Dispatch for *next-business-day* allocation. If someone sends an SMS at 8pm, next-business-day is 9am — 13 hours later. That violates the P2 SLA by definition. The SOP contradicts itself.

**My call:** The HVAC no-on-call rule is an operational constraint that overrides the SLA in practice. I kept the P2 classification but the draft reply acknowledges next-business-day, not the 4-hour window. The SOP should define a P2-HVAC sub-case with its own SLA — this is a gap worth flagging to the client.

---

**Contradiction 3: "Allroof Services" is referenced in the tone guide but missing from the catalogue** *(cross-document inconsistency)*

The tone guide's OUT_OF_SCOPE example reads: *"Hi Mei — gutter cleaning isn't something we cover, sorry. Have a look at **Allroof Services** in your area; they handle that kind of work and we've had good feedback from customers we've referred."* The wording implies an established referral relationship.

But the catalogue's "Things we do not do" section lists gutter cleaning with **no referral partner named**. The only named partners in the catalogue are SunPath Energy (solar) and AquaCorp Pools (pool plumbing). Allroof Services exists nowhere in the source materials except in a tone guide example.

This matters operationally: an agent that follows the tone guide example literally will tell customers to contact a referral partner that the business may or may not actually have a relationship with. That's a real-world liability risk.

**My call:** The agent's prompt names SunPath Energy and AquaCorp Pools (catalogue-confirmed) but does **not** name Allroof Services. For gutter cleaning enquiries, the draft reply states the service isn't offered and suggests the customer find a local provider, without naming one. The catalogue is the source of truth for partner relationships, not the tone guide.

---

**Contradiction 4: "Per premises" is undefined for strata properties (MSG-010)** *(lexical ambiguity affecting classification)*

The catalogue says *"residential only, under 200m² per premises."* MSG-010 is a strata block of 8 units at 60–90m² each — totalling up to 720m² in aggregate. Each individual unit is under 200m² and is residential. The word "premises" is not defined anywhere in the materials. Unit or building?

**My call:** I read "premises" as the individual dwelling, consistent with how strata properties are typically assessed for residential trades work. QUOTE is the right category, but it should be flagged for human review because the scope boundary is ambiguous. The current agent classified it as QUOTE but missed the review flag, which I count as a real miss.

---

## 5. Benchmark Disagreements

### MSG-007 — Agent: no human review | Benchmark: human review

Rachel Ford asks for dishwasher repair. The agent correctly classified it as OUT_OF_SCOPE because appliance repair is excluded, but did not flag for review. I think the benchmark's flag is defensible rather than mandatory: the catalogue rule is explicit, but the customer-facing distinction between appliance installation and appliance repair is subtle enough that a human review may improve the decline/referral.

### MSG-008 — Agent: no human review | Benchmark: human review

Alex Henderson asks for bathroom renovation plumbing. The agent got category, priority, and routing right, but missed `needs_human_review = true`. The catalogue lists bathroom renovation plumbing as "from $4,500", and the described scope could easily exceed the $5,000 review threshold. This is a genuine agent miss: it treated the request as clear because the service exists, without considering likely final value.

### MSG-009 — Agent: human review | Benchmark: no human review

Linda M. reports a ducted heater failure after hours in winter. The agent matched BOOKING/P2/Dispatch but over-flagged for review. I understand the benchmark's stricter reading: the HVAC no-on-call rule gives a clear operational path, so no human review is needed. I still think the flag is defensible because after-hours winter heating plus no live HVAC coverage is exactly the sort of customer-expectation edge case where a human eye is cheap.

### MSG-010 — Agent: no human review | Benchmark: human review

Marcus Webb asks about split-system servicing across eight strata units. The agent treated it as a standard residential quote and missed the ambiguity around "under 200m² per premises." The benchmark's QUOTE category is reasonable, but the review flag is important because the catalogue does not define whether "premises" means each unit or the whole block.

### MSG-017 — Benchmark: COMPLAINT P2 | My read: P3 is equally defensible

Robert Liang, conduct complaint about muddy boots and a short-tempered plumber. Invoice was $280 — well below the $1,000 P2 threshold. The benchmark goes P2 citing "customer is upset". The SOP's P2 rule for complaints is explicit: "any complaint involving a charge over $1,000". Emotional tone is a `needs_human_review` trigger, not a priority trigger. P3 with `needs_human_review = true` is the strict reading. The benchmark's P2 is a reasonable judgement call, but it overrides the stated SOP rule without declaring that it's doing so.

---

## 6. Agent Failures

### MSG-008 and MSG-016 — needs_human_review false negatives (threshold logic)

Both messages involve quotes that likely exceed $5,000 (bathroom renovation from $4,500, ducted aircon from $9,500). The agent correctly identifies the service and routes to Sales, but does not flag for review. The prompt states the $5,000 rule, but the agent appears to anchor on the catalogue's "from" price rather than inferring that the final quote will likely exceed the threshold. Fix: add an explicit instruction such as "if a catalogue 'from' price is near or above $5,000, or the requested scope is likely to push it over $5,000, flag for review." This makes the inference rule explicit rather than leaving it to the model's judgement.

### MSG-007 and MSG-010 — needs_human_review false negatives (borderline scope)

Both messages sit on service-boundary edges: dishwasher repair is clearly excluded but adjacent to appliance installation, and the strata aircon request depends on an undefined "per premises" rule. The agent classified both correctly but treated the classification as enough. Fix: make the human-review rule more concrete: any request involving an excluded-but-adjacent service, strata/multi-unit scope, or undefined service-area constraint should be flagged even when the category is clear.

### MSG-009 — needs_human_review false positive (over-caution)

The agent flagged Linda's after-hours ducted heater message because it saw winter HVAC as borderline. The benchmark says no review because the SOP gives a direct rule: after-hours HVAC is P2 and Dispatch handles next-business-day allocation. Fix: clarify that "no on-call HVAC" is not by itself a human-review trigger when the request is a normal HVAC service within catalogue.

---

## 7. Tone Assessment

The agent's draft replies were mostly on-voice, with a few phrase-level drifts worth calling out. Spot-checked characteristics:

- **No exclamation marks** across all 20 drafts.
- **No "Thank you for contacting Northwind"** openers — the agent leads with the customer's specific situation in all cases.
- **First name used** wherever available (Sarah, Kevin, Priya, etc.).
- **Signed off as "The Northwind team"** consistently.
- **No "from" prices quoted** in draft replies — the agent correctly deferred pricing to the follow-up call.

The main tone issue is that a few drafts use phrasing the guide explicitly discourages or sounds more corporate than the examples. MSG-004, MSG-016, and MSG-017 use "reach out"; MSG-016 says "sales representative"; several drafts say "I understand", which is acceptable but starts to sound more like generic support voice when repeated. Functionally the replies are useful, but a production version should add a lightweight tone lint check for banned phrases before sending.

MSG-013 (garbled submission) was correctly handled — the agent produced no draft reply and flagged for human review, avoiding the failure mode of fabricating a coherent response to nonsense input.

---

## 8. What I'd Build Next

**Document ingestion with Docling.** Right now the SOP, catalogue, and tone guide are encoded directly into the system prompt because that is the simplest reliable shape for a 1-2 hour take-home. In a production version, I would use Docling to convert the client PDFs into structured, auditable JSON/Markdown, then build the prompt context from those generated artifacts. I included this as an optional experiment in `scripts/experimental/convert_assets_docling.py` rather than a required dependency, because the core agent should stay lightweight while still showing the path to maintainable document ingestion.

**Confidence-calibrated review flagging.** The current `needs_human_review` is binary and rule-based. A more robust version would have the model output a `confidence` score (0–1) per field alongside the decision, and automatically set `needs_human_review = true` when confidence on any hard field drops below a threshold. This would catch the MSG-007, MSG-008, MSG-010, and MSG-016 style misses without requiring explicit rule enumeration for every edge case.

**Expanded eval dataset with adversarial cases.** The 20-message benchmark covers the main categories but undersamples the hard edges — multi-request messages, non-English inputs, borderline catalogue scope. I'd add 20–30 synthetic adversarial cases (e.g. a COMPLAINT that looks like a BOOKING, a QUOTE that's clearly OUT_OF_SCOPE, a message in Portuguese) and run the agent against those before any prompt change goes to production. The goal is a regression suite, not a benchmark to optimise against.
