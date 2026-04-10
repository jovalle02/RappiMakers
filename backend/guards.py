"""Input validation guardrails for the chat endpoint. No external dependencies."""

import re
import logging

logger = logging.getLogger("rappi")

MAX_MESSAGE_LENGTH = 2000
MAX_CONVERSATION_MESSAGES = 50

# --- Prompt injection patterns ---

_INJECTION_PATTERNS = re.compile(
    r"|".join([
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"you\s+are\s+now\s+(a|an|the)\b",
        r"new\s+(instructions|role|persona)\s*:",
        r"forget\s+(everything|all|your)\s+(you|instructions|rules)",
        r"(reveal|show|print|output|repeat)\s+(your|the)\s+(system\s+prompt|instructions|rules)",
        r"what\s+(is|are)\s+your\s+(system\s+prompt|instructions|rules)",
        r"act\s+as\s+(if|though)\s+you\s+(have\s+)?no\s+(restrictions|rules)",
        r"\bDAN\b.*\bjailbreak\b",
    ]),
    re.IGNORECASE,
)

# --- Off-topic patterns ---

_OFF_TOPIC_PATTERNS = re.compile(
    r"|".join([
        r"^(write|compose|create)\s+(me\s+)?(a\s+)?(poem|song|story|essay|letter)",
        r"^(code|build|implement|program)\s+(me\s+)?(a\s+)?(website|app|game|script)",
        r"^(help\s+me\s+with|do)\s+my\s+homework",
        r"^(give\s+me\s+)?(personal|relationship|life)\s+advice",
        r"^(translate|convert)\s+.{0,20}\s+(to|into)\s+(spanish|french|german|chinese)",
    ]),
    re.IGNORECASE,
)


def validate_user_input(messages: list[dict]) -> tuple[bool, str | None]:
    """Validate chat input. Returns (ok, error_message)."""
    if not messages:
        return False, "No messages provided."

    last_msg = messages[-1].get("content", "")

    # Length checks
    if len(last_msg) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long (max {MAX_MESSAGE_LENGTH} characters)."

    if len(messages) > MAX_CONVERSATION_MESSAGES:
        return False, f"Conversation too long (max {MAX_CONVERSATION_MESSAGES} messages). Please start a new conversation."

    # Prompt injection check
    if _INJECTION_PATTERNS.search(last_msg):
        logger.warning(f"Prompt injection blocked: {last_msg[:100]}")
        return False, "Message blocked by safety filter."

    # Off-topic check
    if _OFF_TOPIC_PATTERNS.search(last_msg.strip()):
        return False, "off_topic"

    return True, None
