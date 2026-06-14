import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


GROQ_API_KEY: str | None = os.environ.get("GROQ_API_KEY")
LLM_MODEL: str = os.environ.get("LLM_MODEL", "mixtral-8x7b-32768")
VERIFICATION_TIMEOUT_MS: int = int(os.environ.get("VERIFICATION_TIMEOUT_MS", "5000"))

POLICY_ROUTES: dict[str, str] = {
    "confirm_sale": "tahoe",
    "delete_file": "deletion",
}
