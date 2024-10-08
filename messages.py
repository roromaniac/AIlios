"""Static messages for bot."""

# pylint: disable=wildcard-import, unused-wildcard-import, line-too-long

import os
from config import *
from dotenv import load_dotenv

load_dotenv(override=True)

BOT_ERROR_MESSAGE = 'The Ailios bot could not process the response. Please try again. I have pinged <@611722032198975511> informing him of the incident.'
CORRECTION_SUCCESS_MESSAGE = 'Thank you for your input on how to correct this response! I will try to use this information for future responses.'
CORRECTION_FAILURE_MESSAGE = 'I was unable to properly log your suggestion for improving this response. Please try again.'
EXISTING_THREAD_HEADER = 'Trying to generate a helpful response...'
IMAGE_TOO_LARGE_MESSAGE = "The image %s was too large and therefore not considered by AI-lios. If you wish to include it, please reduce it's size to under 512x512."
KNOWLEDGE_UPDATE_FAILED_MESSAGE = "Updating the knowledge files had a fatal error. <@611722032198975511> has now been pinged and he will fix it."
KNOWLEDGE_UPDATED_NEEDED_MESSAGE = "We need to update the knowledge files given it is the start of a new month. Please try your inquiry again in about 15 minutes."
KNOWLEDGE_UPDATE_SUCCESS_MESSAGE = "We have successfully updated knowledge files! Please try again with your inquiry. :)"
LAST_UPDATE_MESSAGE = f"The last time the knowledge files were updated was: {os.environ["LAST_KNOWLEDGE_FILE_UPDATE"]}"
MAX_ATTACHMENTS_MESSAGE = f"Currently, AI-lios only supports {MAX_ATTACHMENTS_ALLOWED} attachments to bot queries. Only {MAX_ATTACHMENTS_ALLOWED} will be processed. To ensure your entire inquiry is process, please stay within the attachment limit."
MAX_MESSAGES_REACHED_MESSAGE = "You have reached the maximum number of messages for a single thread with AI-lios. To continue further interactions, please create a new inquiry in a new thread."
NEW_THREAD_HEADER = "I will try to help you with your inquiry. Friendly reminder that I am just a bot and my responses are not guaranteed to work. Please consult #help for a higher guarantee of resolution should my response not help."
OPENAI_RATE_LIMIT_MESSAGE = "The OpenAI rate limit for the KH2FMRandoHelpBot has been met. Tokens per min (TPM): Limit %(limit)d, Used %(used)d, Requested %(requested)d. Please try again in %(seconds_to_reset).2f seconds."
PERMISSION_DENIED_MESSAGE = "You do not have the permission to perform this operation."
REVIEW_FAILURE_MESSAGE = "To leave a review for AI-lios, please ensure you are the help message author and ONLY provide a value between 1 (indicating inappropriate/inaccurate response) and 10 (perfect response)."
REVIEW_SUCCESS_MESSAGE = "Thanks for reviewing AI-lios! Your review will help us focus on creating better responses in the future."
SEPARATOR = '===================================================================='
THREAD_TITLE_ERROR_MESSAGE = "FATAL ERROR OCCURRED"
TOO_LONG_DISCORD_MESSAGE_ERROR_MESSAGE = f"Your message exceeds the discord API limit of {MAX_CHARS_DISCORD} characters. Please shorten your message to be below the character limit."
TOO_LONG_OPENAI_RESPONSE_ERROR_MESSAGE = f"OpenAI's response somehow exceeded {MAX_CHARS_OPENAI_RESPONSE} characters. This can happen on rare occurrences. Try simplifying your query."
THREAD_CATEGORY = "Discussion"
THREAD_TITLE_SYSTEM_PROMPT = "You are a summarizer that adequately summarizes a help inquiry in 8 words or less in order to create good thread titles."
THREAD_TITLE_USER_PROMPT = "Please create a thread title based on the following inquiry."
