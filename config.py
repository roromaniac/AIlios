"""Configuration variables for bot."""
import json

ATTACHMENT_EXTENSIONS = ['.jpg','.png','.jpeg']
CHANNEL_NAME = "ailios"
CONVERSATION_FILE = "conversation_logging.json"
CORRECTION_COMMAND = "/correct"
DATE_FORMAT = "%Y-%m-%d"
DEFAULT_LANGUAGE = "en"
DYNAMIC_CHANNEL_IDS = {
    "announcements": {"id": 712837747685195902, "batch_by_date": False},
    "help": {"id": 721205500556869642, "batch_by_date": True},
    "openkh-gameplay-mods": {"id": 975234023926399027, "batch_by_date": False},
    "openkh-visual-mods": {"id": 975232621288247346, "batch_by_date": False},
    "openkh-audio-mods": {"id": 975233883157188618, "batch_by_date": False},
    "other-mods": {"id": 986283734321987665, "batch_by_date": False},
    "lua-scripts": {"id": 893409929992495104, "batch_by_date": False},
    "tracker-discussion": {"id": 737657166902591649, "batch_by_date": True},
    "generator-discussion": {"id": 1086478482046996652, "batch_by_date": True},
}
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
MODEL = "gpt-4o-mini"
OPENAI_ASSISTANT_ID = 'asst_soKOR1ZJHiAIzWz3AE7h0LwC'
OPENAI_VECTOR_STORE_ID = 'vs_D3p8uQk6xApU4OFc3yC2yXE7'
with open("openai_pricing.json", "r", encoding="utf-8") as f:
    OPENAI_PRICING = json.load(f)
REVIEW_COMMAND = "/rate"
STORAGE_SPACE = 10.0 # in GiB
