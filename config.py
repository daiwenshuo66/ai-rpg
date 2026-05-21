import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.environ.get("API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://api.deepseek.com")

PARSER_MODEL = os.environ.get("PARSER_MODEL", "deepseek-chat")
NARRATOR_MODEL = os.environ.get("NARRATOR_MODEL", "deepseek-chat")

DEBUG = os.environ.get("DEBUG", "0") == "1"
