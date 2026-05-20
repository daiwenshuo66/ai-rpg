import os

API_KEY = os.environ.get("API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://api.deepseek.com")

PARSER_MODEL = os.environ.get("PARSER_MODEL", "deepseek-chat")
NARRATOR_MODEL = os.environ.get("NARRATOR_MODEL", "deepseek-chat")
