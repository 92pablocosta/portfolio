# agent/triage.py
import os
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
from agent.schema import TriageOutput
from agent.prompt import SYSTEM_PROMPT

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def triage_message(message: dict) -> TriageOutput:
    """
    Receives a raw inbound message dict and returns a structured TriageOutput.
    Raises an explicit error if the API call fails or returns unexpected data.
    """

    user_content = f"""
Channel: {message.get('channel', 'unknown')}
Received at: {message.get('received_at', 'unknown')}
Sender name: {message.get('sender_name', 'unknown')}
Subject: {message.get('subject', 'N/A')}
Body: {message.get('body', '')}
    """.strip()

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=TriageOutput,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError(f"Model returned no structured output for message {message.get('id')}")
        return parsed

    except Exception as e:
        raise RuntimeError(f"Triage failed for message {message.get('id')}: {e}")