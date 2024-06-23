import os
import json
import logging
import asyncio
import io

import discord
import requests
import aiohttp
import tempfile
from dotenv import load_dotenv
from langdetect import detect_langs
from deep_translator import GoogleTranslator

import openai
from openai import OpenAI

from config import *

load_dotenv()

def check_rate_limit(endpoint):
    url = f"https://discord.com/api/v9/{endpoint}"
    headers = {
        "Authorization": f"Bot {os.getenv('DISCORD_TOKEN')}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        rate_limit_reset = response.headers.get("X-RateLimit-Reset-After")
        return rate_limit_remaining, rate_limit_reset
    else:
        logging.error(f"Failed to check rate limit: {response.status_code}")
        return None, None
    
async def process_discord_message(discord_message):
    if len(discord_message.attachments) > 0:  # Checks if there are attachments
        attached_images = []
        for file in discord_message.attachments:
            for ext in IMAGE_EXTENSIONS:
                if file.filename.endswith(ext):
                    print(f"HOLY F*CK, AN IMAGE {file.filename}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file.url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                attached_images.append((file.filename, image_data))
        return attached_images
    
async def upload_image_to_openai(openai_client, image_data, filename):
    with tempfile.NamedTemporaryFile(delete=True, suffix=os.path.splitext(filename)[1]) as temp_file:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1])
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
    detected_language = detect_langs(message)[0]
    change_language = detected_language.prob > LANG_DETECT_MIN_PROB and len(message.split(' ')) >= MIN_WORDS_IN_MESSAGE_FOR_TRANSLATION
    text_language = detected_language.lang if change_language else DEFAULT_LANGUAGE
    return text_language

async def storage_check(discord_client):
    if ((os.path.getsize(LOGGING_FILE) + os.path.getsize(LOGGING_FILE)) / (1024 * 1024 * 1024)) > (0.8 * STORAGE_SPACE):
        # DM Roro that we are low on storage.
        user_id = 611722032198975511
        user = await discord_client.fetch_user(user_id)
        # Send the direct message
        if user:
            await user.send("Less than 20% of storage space remains!!!!! Back up logs and conversations.")

async def handle_rate_limit(discord_message, remaining, reset, is_thread):
    remaining = 0
    if remaining <= 1:
        if not is_thread:
            discord_thread_name = f"Rate Limit Warning"
            discord_thread = await discord_message.create_thread(name=discord_thread_name)
        await discord_thread.send(f"You have have been rate limited. Please try again in {round(float(reset), 2)} seconds.")
        return True
    return False

def extract_citations(openai_client, message):
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
    attached_images = await process_discord_message(discord_message)
    image_files = []
    for filename, image_data in attached_images:
        file_response = await upload_image_to_openai(openai_client, image_data, filename)
        image_files.append({
            "type": "image_file",
            "image_file": {"file_id": file_response.id}
        })
    return image_files