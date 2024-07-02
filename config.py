"""Configuration variables for bot."""
import json

ATTACHMENT_EXTENSIONS = ['.jpg','.png','.jpeg']
BOT_ERROR_MESSAGE = 'The Ailios bot could not process the response. Please try again. I have pinged <@611722032198975511> informing him of the incident.'
CHANNEL_NAME = "ailios"
CONVERSATION_FILE = "conversation_logging.json"
DEFAULT_LANGUAGE = "en"
EXISTING_THREAD_HEADER = 'Trying to generate a helpful response...'
HELP_COMMAND = "/randohelp"
IMAGE_COST_IN_DOLLARS = 0.001275
IMAGE_TOO_LARGE_MESSAGE = "The image %s was too large and therefore not considered by AI-lios. If you wish to include it, please reduce it's size to under 512x512."
LOGGING_FILE = "app.log"
LANG_DETECT_MIN_PROB = 0.6
MAX_ATTACHMENTS_ALLOWED = 2
MAX_ATTACHMENTS_MESSAGE = f"Currently, AI-lios only supports {MAX_ATTACHMENTS_ALLOWED} attachments to bot queries. Only {MAX_ATTACHMENTS_ALLOWED} will be processed. To ensure your entire inquiry is process, please stay within the attachment limit."
MAX_CHARS_DISCORD = 2000
MAX_CHARS_OPENAI_RESPONSE = 2000
MAX_COMPLETION_TOKENS = 2000
MAX_MESSAGES_ALLOWED_IN_THREAD = 3
MAX_MESSAGES_REACHED_MESSAGE = "You have reached the maximum number of messages for a single thread with AI-lios. To continue further interactions, please create a new inquiry in a new thread."
MAX_PIXEL_DIM = 512
MIN_WORDS_IN_MESSAGE_FOR_TRANSLATION = 5
MODEL = "gpt-4o"
NEW_THREAD_HEADER = "I will try to help you with your inquiry. Friendly reminder that I am just a bot and my responses are not guaranteed to work. Please consult #help for a higher guarantee of resolution should my response not help."
OPENAI_ASSISTANT = 'asst_CVyBlCLuW65qRZ3MnVlTMjv6'
with open("openai_pricing.json", "r", encoding="utf-8") as f:
    OPENAI_PRICING = json.load(f)
OPENAI_RATE_LIMIT_MESSAGE = "The OpenAI rate limit for the KH2FMRandoHelpBot has been met. Tokens per min (TPM): Limit %(limit)d, Used %(used)d, Requested %(requested)d. Please try again in %(seconds_to_reset).2f seconds."
REVIEW_COMMAND = "/review"
REVIEW_FAILURE_MESSAGE = "To leave a review for AI-lios, please ensure you are the help message author and ONLY provide a value between 1 (indicating inappropriate/inaccurate response) and 10 (perfect response)."
REVIEW_SUCCESS_MESSAGE = "Thanks for reviewing AI-lios! Your review will help us focus on creating better responses in the future."
SEPARATOR = '===================================================================='
STORAGE_SPACE = 10.0 # in GiB
THREAD_CATEGORY = "Discussion"
THREAD_TITLE_ERROR_MESSAGE = "FATAL ERROR OCCURRED"
THREAD_TITLE_SYSTEM_PROMPT = "You are a summarizer that adequately summarizes a help inquiry in 8 words or less in order to create good thread titles."
THREAD_TITLE_USER_PROMPT = "Please create a thread title based on the following inquiry"
TOO_LONG_DISCORD_MESSAGE_ERROR_MESSAGE = f"Your message exceeds the discord API limit of {MAX_CHARS_DISCORD} characters. Please shorten your message to be below the character limit."
TOO_LONG_OPENAI_RESPONSE_ERROR_MESSAGE = f"OpenAI's response somehow exceeded {MAX_CHARS_OPENAI_RESPONSE} characters. This can happen on rare occurrences. Try simplifying your query"
