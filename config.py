"""Configuration variables for bot."""
import json

ATTACHMENT_EXTENSIONS = ['.jpg','.png','.jpeg']
CHANNEL_NAME = "ailios"
CONVERSATION_FILE = "conversation_logging.json"
DEFAULT_LANGUAGE = "en"
HELP_COMMAND = "/randohelp"
IMAGE_COST_IN_DOLLARS = 0.001275
LOGGING_FILE = "app.log"
LANG_DETECT_MIN_PROB = 0.6
MAX_ATTACHMENTS_ALLOWED = 2
MAX_CHARS_DISCORD = 2000
MAX_CHARS_OPENAI_RESPONSE = 2000
MAX_COMPLETION_TOKENS = 2000
MAX_MESSAGES_ALLOWED_IN_THREAD = 3
MAX_PIXEL_DIM = 512
MIN_WORDS_IN_MESSAGE_FOR_TRANSLATION = 5
MODEL = "gpt-4o"
OPENAI_ASSISTANT = 'asst_CVyBlCLuW65qRZ3MnVlTMjv6'
with open("openai_pricing.json", "r", encoding="utf-8") as f:
    OPENAI_PRICING = json.load(f)
REVIEW_COMMAND = "/review"
STORAGE_SPACE = 10.0 # in GiB

