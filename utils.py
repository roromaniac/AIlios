# pylint: disable=wildcard-import, unused-wildcard-import

import os
import json
import logging
import io

import tempfile
import requests
import aiohttp
from dotenv import load_dotenv
from langdetect import detect_langs

from config import *

load_dotenv()

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
            for ext in IMAGE_EXTENSIONS:
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
        os.remove(temp_file.name)

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
