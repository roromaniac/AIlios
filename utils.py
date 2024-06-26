"""Utility functions bot."""

# pylint: disable=wildcard-import, unused-wildcard-import, broad-exception-caught

import os
import json
import logging
import io
import re

import tempfile
import requests
import aiohttp
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
from langdetect import detect_langs

import discord

from config import *

load_dotenv()

def is_discord_thread(discord_message, discord_thread):
    """
        Checks the status of the message of being in an existing discord thread.

        Args:
            discord_message (discord.Message): the discord message to check for thread status
            discord_thread (discord.Thread or None): the possible discord thread being checked, will be None if a thread has not yet been created
    """
    return isinstance(discord_message.channel, discord.Thread) or isinstance(discord_thread, discord.Thread)

async def get_discord_thread(openai_client, discord_message, discord_thread_name=None, message_content=None):
    """
        Retrieve the discord thread of a discord message or create a new thread for a new inquiry.

        Args:
            discord_message (discord.Message): The discord message to get the thread for.
            discord_thread_name (str): The title of the discord thread if a thread has not yet been created.

        Returns:
            discord_thread (discord.Thread): The discord thread the message belongs to.
            existing_thread (bool): A status of if the thread existed prior to function call.
    """
    existing_thread = is_discord_thread(discord_message, discord_thread=None)
    if existing_thread:
        discord_thread = discord_message.channel
    else:
        if discord_thread_name is None:
            response = openai_client.chat.completions.create(
                            model=MODEL,
                            messages=[
                                {"role": "system", "content": THREAD_TITLE_SYSTEM_PROMPT},
                                {"role": "user", "content": f"{THREAD_TITLE_USER_PROMPT}: {message_content}"}
                            ]
                        )
            discord_thread_name = f"{THREAD_CATEGORY}: {response.choices[0].message.content}"
        discord_thread = await discord_message.create_thread(name=discord_thread_name)

    return discord_thread, existing_thread

def check_rate_limit(endpoint):
    """
        Rate limit checker.

        Args:
            endpoint (str): The endpoint to check for discord rate limits.

        Returns:
            rate_limit_remaining (int): The number of messages remaining under the rate limit at *endpoint*.
            rate_limit_reset (int): Time in seconds until the rate limit resets at *endpoint*.

        Raises:
            RuntimeError: Raised if the rate limit cannot be checked.
    """

    url = f"https://discord.com/api/v9/{endpoint}"
    headers = {
        "Authorization": f"Bot {os.getenv('DISCORD_TOKEN')}"
    }
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code == 200:
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        rate_limit_reset = response.headers.get("X-RateLimit-Reset-After")
        return rate_limit_remaining, rate_limit_reset
    logging.error("Failed to check rate limit: %s", response.status_code)
    return None, None

async def process_discord_message_attachments(discord_message):
    """
        Rate limit checker.

        Args:
            discord_message (discord.Message): A discord message to check for attachements (images).

        Returns:
            attached_images (list): A list of processed images in the discord message.
    """
    if len(discord_message.attachments) > 0:  # Checks if there are attachments
        attached_images = []
        for file in discord_message.attachments:
            for ext in ATTACHMENT_EXTENSIONS:
                if file.filename.endswith(ext):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file.url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                attached_images.append((file.filename, image_data))
        return attached_images

async def upload_image_to_openai(openai_client, image_data, filename):
    """
        Uploads an image to the OpenAI platform.

        Args:
            openai_client (openai.OpenAI): The OpenAI client to upload images to.
            image_data (bytes): The bytes of an image from a discord message.
            filename (str): The filename of the image contained in *image_data*.

        Returns:
            attached_images (list): A list of processed images in the discord message.
    """
    with tempfile.NamedTemporaryFile(delete=True, suffix=os.path.splitext(filename)[1]) as temp_file:
        temp_file.write(image_data)
        temp_file.flush()
        temp_file.seek(0)
        file_content = io.BytesIO(temp_file.read())
        file_content.name = filename  # Assign a name to the BytesIO object
        temp_file.close()

        # Upload the file to OpenAI
        file_response = openai_client.files.create(file=file_content, purpose="vision")

        return file_response

def detect_message_language(message):
    """
        Detect the language of a message.

        Args:
            message (str): Text for which the language needs to be detected.

        Returns:
            language (str): The code for the language detected.
    """
    detected_language = detect_langs(message)[0]
    change_language = detected_language.prob > LANG_DETECT_MIN_PROB and len(message.split(' ')) >= MIN_WORDS_IN_MESSAGE_FOR_TRANSLATION
    text_language = detected_language.lang if change_language else DEFAULT_LANGUAGE
    return text_language

async def storage_check(discord_client):
    """
        Storage check on converation logs.

        Args:
            discord_client (discord.Client): The discord client used to send DMs about memory warnings.

        Outputs:
            DM to roro if the conversation files are too large.
    """
    if ((os.path.getsize(LOGGING_FILE) + os.path.getsize(LOGGING_FILE)) / (1024 * 1024 * 1024)) > (0.8 * STORAGE_SPACE):
        # DM Roro that we are low on storage.
        user_id = 611722032198975511
        user = await discord_client.fetch_user(user_id)
        # Send the direct message
        if user:
            await user.send("Less than 20% of storage space remains!!!!! Back up logs and conversations.")

async def handle_rate_limit(discord_message, remaining, reset, is_thread):
    """
        Deals with rate limits.

        Args:
            discord_client (discord.Client): The discord client used to send DMs about memory warnings.

        Outputs:
            A message in the thread indicating the user has been rate limited.

        Returns:
            (bool) Status if user has been rate limited.
    """
    if remaining <= 1:
        if not is_thread:
            discord_thread_name = "Rate Limit Warning"
            discord_thread = await discord_message.create_thread(name=discord_thread_name)
        else:
            discord_thread = discord_message.channel
        await discord_thread.send(f"You have have been rate limited. Please try again in {round(reset, 2)} seconds.")
        return True
    return False

def extract_citations(openai_client, message):
    """
        Extracts annotations and citations from an OpenAI completion.

        Args:
            openai_client (openai.OpenAI): The discord client used to send DMs about memory warnings.

        Returns:
            annotations_list, citations_list (list, list): List of annotations and their respective citations.
    """
    annotations = message.annotations
    citations = []
    # Iterate over the annotations and add footnotes
    for index, annotation in enumerate(annotations):
        # Replace the text with a footnote
        message.value = message.value.replace(annotation.text, f' [{index}]')
        # Gather citations based on annotation attributes
        if (file_citation := getattr(annotation, 'file_citation', None)):
            cited_file = openai_client.files.retrieve(file_citation.file_id)
            citations.append(f'[{index}]: {cited_file.filename}')
        elif (file_path := getattr(annotation, 'file_path', None)):
            cited_file = openai_client.files.retrieve(file_path.file_id)
            citations.append(f'[{index}] Click <here> to download {cited_file.filename}')
    return annotations, citations

async def discord_to_openai_image_conversion(discord_message, openai_client):
    """
        Converts images from discord format to OpenAI format.

        Args:
            discord_message (discord.Message): The discord message to check for attached images.

        Returns:
            image_files (list): A list of image content dictionaries to be uploaded to the OpenAI assistant.
    """
    attached_images = await process_discord_message_attachments(discord_message)
    image_files = []
    for filename, image_data in attached_images:
        file_response = await upload_image_to_openai(openai_client, image_data, filename)
        image_files.append({
            "type": "image_file",
            "image_file": {"file_id": file_response.id}
        })
    return image_files

def setup_conversation_logs():
    """
        Instantiates conversation log file.

        Returns:
            conversations_logs (dict): A dictionary of thread ids and their contents
    """
    if os.path.exists(CONVERSATION_FILE):
        with open(CONVERSATION_FILE, "r", encoding='utf-8') as logs:
            try:
                conversations_logs = json.load(logs)
                conversations_logs = {int(k): v for k, v in conversations_logs.items()}
            except json.decoder.JSONDecodeError:
                conversations_logs = {}
    else:
        conversations_logs = {}
        with open(CONVERSATION_FILE, "w", encoding='utf-8') as logs:
            json.dump(conversations_logs, logs)
    return conversations_logs

async def send_response_to_discord(discord_thread, response):
    """
        Sends an AI generated response to discord utilizing multiple messages if need be.

        Args:
            discord_thread (discord.Thread): The discord thread to send messages to.
            response (str): The response from the OpenAI assistant.
    """
    num_messages_needed = (len(response) // MAX_CHARS_DISCORD) + 1
    start_index = 0
    for i in range(num_messages_needed):
        if num_messages_needed == 1:
            await discord_thread.send(response)
        else:
            message_count_header = f"**[{i+1}/{num_messages_needed}]** "
            end_index = start_index + MAX_CHARS_DISCORD - len(message_count_header)
            await discord_thread.send(message_count_header + response[start_index:end_index])
            start_index = end_index

async def populate_openai_assistant_content(openai_client, discord_message, discord_message_contents):
    """
        Creates jsons of text and image data to send to OpenAI assistant.

        Args:
            openai_client (openai.OpenAI): The OpenAI client to send messages to. 
            discord_message (discord.Message) The discord message to extract potential attachments from.
            discord_message_contents (str): The contents of the message to pass to text data.

        Returns:
            text_content (list): List of text contents to upload to OpenAI assistant.
            image_content (list): List of image contents to upload to OpenAI assistant.
    """
    text_content = [{
        "type": "text",
        "text": discord_message_contents
    }]

    image_content = []
    if len(discord_message.attachments) > 0:
        image_content = await discord_to_openai_image_conversion(discord_message, openai_client)

    return text_content, image_content

def log_conversation(conversations_logs, discord_message, discord_thread, text_language, current_message, assistant_message, existing_thread):

    if existing_thread:
        # add the last message to the existing log for this thread
        conversations_logs[discord_thread.id]["message_log"].append(current_message)
    else:
        # initialize conversation log with original help message and original response
        conversations_logs[discord_thread.id] = {
            "message_author": discord_message.author.name, 
            "message_content_summary": discord_thread.name.removeprefix(f"{THREAD_CATEGORY}: "),
            "message_language": text_language,
            "message_log": [current_message, {"role": "assistant", "content": assistant_message}]
        }

    return conversations_logs

async def send_initial_discord_response(discord_thread, existing_thread, discord_message, text_language):

    if existing_thread:
        header = EXISTING_THREAD_HEADER
        header = GoogleTranslator(source='auto', target=text_language).translate(header)
        await discord_thread.send(header)
        await discord_thread.send(SEPARATOR)
    else:
        header = f'Hey, {discord_message.author.display_name}! {NEW_THREAD_HEADER}'
        header = GoogleTranslator(source='auto', target=text_language).translate(header)
        await discord_thread.send(header)
        await discord_thread.send(SEPARATOR)

    return header

async def submit_review(discord_thread, discord_message, conversations_logs):

    text = discord_message.content.removeprefix(REVIEW_COMMAND + " ")

    if is_discord_thread(discord_message, discord_thread):
        discord_thread = discord_message.channel
        first_thread_message = conversations_logs[discord_thread.id]["message_log"][0]["content"]
        text_language = detect_message_language(first_thread_message)
        try:
            user_rating = float(text)
            if (1 <= user_rating <= 10) and (discord_message.author.name == conversations_logs[discord_thread.id]["message_author"]):
                conversations_logs[discord_thread.id]["rating"] = user_rating
                await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(REVIEW_SUCCESS_MESSAGE))
            else:
                await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(REVIEW_FAILURE_MESSAGE))
        except ValueError:
            await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(REVIEW_FAILURE_MESSAGE))

    return conversations_logs

def translate_error_message(message):

    try:
        text_language = detect_message_language(message)
        translated_error_message = GoogleTranslator(source='auto', target=text_language).translate(BOT_ERROR_MESSAGE)
    except Exception:
        translated_error_message = BOT_ERROR_MESSAGE
        logging.exception("ERROR OCCURRED")

    return translated_error_message

async def get_assistant_response(openai_client, openai_thread, run, discord_thread):

    if run.status == 'completed':
        openai_message = openai_client.beta.threads.messages.list(
            thread_id=openai_thread.id
        )
    else:
        logging.error("Incomplete Details: %s", run.incomplete_details)
        logging.error("Failure Details: %s", run.last_error)
        if run.last_error.code == 'rate_limit_exceeded':
            limit, used, requested, seconds_to_reset = [x.strip() for x in re.findall(r' \d+\.\d+| \d+', run.last_error.message)]
            limit, used, requested, seconds_to_reset = int(limit), int(used), int(requested), float(seconds_to_reset)
            await discord_thread.send(OPENAI_RATE_LIMIT_MESSAGE % {"limit": limit, "used": used, "requested": requested, "seconds_to_reset": seconds_to_reset})
        raise RuntimeError("The OpenAI message failed to generate.")

    return openai_message
