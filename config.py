import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

VERIFICATION_TIMEOUT_MS: int = int(os.environ.get("VERIFICATION_TIMEOUT_MS", "5000"))
