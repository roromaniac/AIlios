"""Utility functions bot."""

# pylint: disable=wildcard-import, unused-wildcard-import, broad-exception-caught

import os
import json
import logging
import io
import re
import subprocess

import datetime as dt
import tempfile
import requests
import aiohttp
from PIL import Image
from deep_translator import GoogleTranslator
from dotenv import load_dotenv, set_key
from langdetect import detect_langs

import discord

from config import *
from messages import *

load_dotenv()

def check_rate_limit(endpoint):
    """
        Rate limit checker.

        Args:
            endpoint (str): The endpoint to check for discord rate limits.

        Returns:
            rate_limit_remaining (int | None): The number of messages remaining under the rate limit at *endpoint*.
            rate_limit_reset (int | None): Time in seconds until the rate limit resets at *endpoint*.

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

async def discord_to_openai_image_conversion(discord_message, discord_thread, openai_client):
    """
        Converts images from discord format to OpenAI format.

        Args:
            discord_message (discord.Message): The discord message to check for attached images.
            discord_thread (discord.Thread): The discord thread to send warnings/errors to.
            openai_client (openai.OpenAI): The OpenAI client to upload images to.

        Returns:
            image_files (list): A list of image content dictionaries to be uploaded to the OpenAI assistant.
    """
    attached_images = await process_discord_message_attachments(discord_message, discord_thread)
    image_files = []
    for filename, image_data in attached_images:
        file_response = await upload_image_to_openai(openai_client, image_data, filename)
        image_files.append({
            "type": "image_file",
            "image_file": {"file_id": file_response.id}
        })
    return image_files

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

async def get_assistant_response(openai_client, openai_thread, run, discord_thread):
    """
        Retrieves the OpenAI assistant response from the appropriate thread.

        Args:
            openai_client (openai.OpenAI): The OpenAI client to use for response retrieval.
            openai_thread (openai.Thread): The thread used to facilitate assistant response.
            run (openai.Run): The run object containing status information about the ping to the assistant.
            discord_thread (discord.Thread): The discord thread to send messages to if rate limit issues with OpenAI happen.

        Returns:
            openai_message (openai.pagination.SyncCursorPage[Message]): The response from the assistant.

        Raises:
            RuntimeError: If the OpenAI assistant ping fails for any reason, a RuntimeError is raised.
    """
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

async def get_discord_thread(openai_client, discord_message, discord_thread_name=None, message_content=None):
    """
        Retrieve the discord thread of a discord message or create a new thread for a new inquiry.

        Args:
            openai_client: The client to use to create a short summary of the query in the thread title.
            discord_message (discord.Message): The discord message to get the thread for.
            discord_thread_name (str): The title of the discord thread if a thread has not yet been created.
            message_content: The contents of the message to pass to the openai_client to create the thread summary title.

        Outputs:
            A discord thread with a title related to the message content.

        Returns:
            discord_thread (discord.Thread): The discord thread the message belongs to.
            existing_thread (bool): A status of if the thread existed prior to function call.
    """
    existing_thread = is_discord_thread(discord_message)
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

def get_openai_run_cost(run, num_images):
    """
        Gets the cost of generating the assistant response.

        Args:
            run (openai.Run): The run object used to generate an assistant response.
            num_images (int): The number of images included in the inquiry to the assistant.

        Returns:
            input_cost (float): The cost in USD for the input tokens to the assistant.
            output_cost (float): The cost in USD for the assistant's completion.
            image_cost (float): The cost in USD for utilizing image input.
    """
    input_1k_token_cost_in_dollars = OPENAI_PRICING[run.model]["input"]
    output_1k_token_cost_in_dollars = OPENAI_PRICING[run.model]["output"]
    return input_1k_token_cost_in_dollars * (run.usage.prompt_tokens / 1000), output_1k_token_cost_in_dollars * (run.usage.completion_tokens / 1000), IMAGE_COST_IN_DOLLARS * num_images

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

def is_discord_thread(discord_message, discord_thread=None):
    """
        Checks the status of the message of being in an existing discord thread.

        Args:
            discord_message (discord.Message): the discord message to check for thread status
            discord_thread (discord.Thread or None): the possible discord thread being checked, will be None if a thread has not yet been created
    """
    return isinstance(discord_message.channel, discord.Thread) or message_has_thread(discord_message) or isinstance(discord_thread, discord.Thread)

def knowledge_file_needs_update():
    """
    Checks if the knowledge file needs to be updated based on the last update date.

    Returns:
        bool: True if the knowledge file needs to be updated, False otherwise.
    """
    
    last_update = os.getenv('LAST_KNOWLEDGE_FILE_UPDATE')
    if not last_update:
        return True  # If no last update date is set, assume update is needed

    try:
        last_update_date = dt.datetime.strptime(last_update, '%m-%d-%Y')
        today = dt.datetime.today()
        return last_update_date.month != today.month
    except ValueError:
        logging.error("Invalid date format in LAST_KNOWLEDGE_FILE_UPDATE")
        return True  # If there's an error parsing the date, assume update is needed

def log_conversation(conversations_logs, discord_message, discord_thread, text_language, role, current_message, existing_thread):
    """
        Logs a conversation.

        Args:
            conversations_logs (dict): The log of conversations indexed by discord thread id.
            discord_message (discord.Message): The current discord message object.
            discord_thread (discord.Thread): The discord thread of the current message.
            text_language (str): The language code of the message.
            role (str): The role of the message sender.
            current_message (dict): The content of the message to be logged.
            existing_thread (bool): Status of whether the thread already exists or not.

        Returns:
            conversations_logs (dict): A conversation log updated with the new user + assistant message.

        Raises:
            ValueError if role is not in ["user", "assistant"]. 
    """
    if role not in ["user", "assistant"]:
        raise ValueError("OpenAI must receive messages from either the role of user or assistant.")
    if existing_thread and discord_thread.id in conversations_logs:
        # add the last message to the existing log for this thread
        conversations_logs[discord_thread.id]["message_log"] += [{"role": role, "content": current_message}]
    else:
        # initialize conversation log with original help message and original response
        conversations_logs[discord_thread.id] = {
            "cost_in_dollars": {
                "input_cost": 0,
                "output_cost": 0,
                "image_cost": 0,
                "total_cost": 0
            },
            "message_author": discord_message.author.name, 
            "message_content_summary": discord_thread.name.removeprefix(f"{THREAD_CATEGORY}: "),
            "message_language": text_language,
            "message_log": [{"role": role, "content": current_message}],
            "rating": None,
        }

    return conversations_logs

def message_has_thread(discord_message):
    """
        Checks if the message already has a thread created.

        Args:
            discord_message (discord.Message): The message for which thread attribute is checked.
    """
    for thread in discord_message.channel.threads:
        if thread.id == discord_message.id:
            return True
    return False

async def populate_OPENAI_ASSISTANT_ID_content(openai_client, discord_message, discord_thread, discord_message_contents):
    """
        Creates jsons of text and image data to send to OpenAI assistant.

        Args:
            openai_client (openai.OpenAI): The OpenAI client to send messages to. 
            discord_message (discord.Message) The discord message to extract potential attachments from.
            discord_thread (discord.Thread): The thread to send warning/error messages to.
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
        image_content = await discord_to_openai_image_conversion(discord_message, discord_thread, openai_client)

    return text_content, image_content

async def process_discord_message_attachments(discord_message, discord_thread):
    """
        Rate limit checker.

        Args:
            discord_message (discord.Message): A discord message to check for attachements (images).
            discord_thread (discord.Thread): The discord thread to send warnings/errors to in case of error.

        Outputs:
            A message warning a user if they include too many attachments or images that are too large.
            
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
                                image = Image.open(io.BytesIO(image_data))
                                if len(attached_images) >= MAX_ATTACHMENTS_ALLOWED:
                                    await send_response_to_discord(discord_thread, MAX_ATTACHMENTS_MESSAGE)
                                    return attached_images
                                if image.width <= 512 and image.height <= 512:
                                    attached_images.append((file.filename, image_data))
                                else:
                                    await send_response_to_discord(discord_thread, IMAGE_TOO_LARGE_MESSAGE % file.filename)
        return attached_images

async def send_initial_discord_response(discord_thread, discord_message, text_language='en'):
    """
        Sends initial discord message upon new inquiry from user. 

        Args:
            discord_thread (discord.Thread | None): The discord thread where the new inquiry message is located.
            discord_message (discord.Message): The discord message associated with the new inquiry. 
            text_language (str): The language code to translate the initial message to.

        Outputs:
            An introductory message the bot sends to the user when a new inquiry is made.

        Returns:
            header (str): The initial message sent to discord to use for logging purposes.
    """
    existing_thread = is_discord_thread(discord_message, discord_thread)
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

async def send_response_to_discord(discord_thread, response):
    """
        Sends an AI generated response to discord utilizing multiple messages if need be.

        Args:
            discord_thread (discord.Thread): The discord thread to send messages to.
            response (str): The response from the OpenAI assistant.

        Outputs:
            A message with the assistant's response.
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

async def submit_correction(discord_thread, discord_message, conversations_logs):
    """
        Submits the potential instructions to fix the error in the outputted response.

        Args:
            discord_thread (discord.Thread): The discord thread for discord to send message to.
            discord_message (discord.Message): The current message object. Used to see if the reviewer is the original author.
            conversations_logs (dict): The conversation logging dictionary used to update the rating of this thread.

        Outputs:
            A message indicating whether the review was successfully submitted or not.

        Returns:
            conversations_logs (dict): The updated conversation logs.
    """

    text = discord_message.content.removeprefix(CORRECTION_COMMAND + " ")

    if is_discord_thread(discord_message, discord_thread):
        discord_thread = discord_message.channel
        first_thread_message = conversations_logs[discord_thread.id]["message_log"][0]["content"]
        text_language = detect_message_language(first_thread_message)
        try:
            correction_instruction = str(text)
            conversations_logs[discord_thread.id]["correction information"] = correction_instruction
            await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(CORRECTION_SUCCESS_MESSAGE))
        except ValueError:
            await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(CORRECTION_FAILURE_MESSAGE))

    return conversations_logs

async def submit_review(discord_thread, discord_message, conversations_logs):
    """
        Submits the review to logs and responds with the appropriate discord messages.

        Args:
            discord_thread (discord.Thread): The discord thread for discord to send message to.
            discord_message (discord.Message): The current message object. Used to see if the reviewer is the original author.
            conversations_logs (dict): The conversation logging dictionary used to update the rating of this thread.

        Outputs:
            A message indicating whether the review was successfully submitted or not.

        Returns:
            conversations_logs (dict): The updated conversation logs.
    """
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

def thread_message_counts(conversations_logs, discord_thread):
    """
        Counts the number of user messages in a thread.

        Args:
            conversations_logs (dict): The conversation log.
            discord_thread (discord.Thread): The thread for which to check number of user messages.

        Returns:
            user_messages (int): The number of user messages detected in thread.
        
        Raises:
            KeyError if the discord_thread id is not logged in the conversation logs.
    """
    try:
        message_list = conversations_logs[discord_thread.id]["message_log"]
        user_messages = sum([message["role"] == "user" for message in message_list])
    except KeyError as e:
        raise KeyError("This thread id has not been logged in the conversations.") from e

    return user_messages

def translate_error_message(language):
    """
        Translate the bot's error message to a different language.

        Args:
           language (str): The language code to serve as the translation target in GoogleTranslator.

        Returns:
            translated_error_message (str): The translated bot error message.
    """
    try:
        translated_error_message = GoogleTranslator(source='auto', target=language).translate(BOT_ERROR_MESSAGE)
    except Exception:
        translated_error_message = BOT_ERROR_MESSAGE
        logging.exception("ERROR OCCURRED")

    return translated_error_message

async def update_knowledge_files(discord_message):
    """
        Updates the relevant knowledge files and adds them to vector storage on OpenAI.

        Args:
            discord_message (discord.Message): the discord message where the update request was submitted
    """
    await discord_message.channel.send(KNOWLEDGE_UPDATED_NEEDED_MESSAGE)
    try:
        # Run gpt-crawler on kh2rando.com
        try: 
            npm_local_path = os.path.join(os.getcwd(), "knowledge-files", "gpt-crawler", "node_modules", ".bin", "npm")
            # Call npm with the start script
            subprocess.run([npm_local_path, "run", "start"], cwd="./knowledge-files/gpt-crawler", check=True)
            print("GPT Crawler completed successfully.")
        except (subprocess.CalledProcessError) as e:
        # except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Error running GPT Crawler: {e}")
            await discord_message.channel.send("There was an error updating the knowledge base. <@611722032198975511> has been notified.")
            return
        subprocess.run(["python", "extract_messages.py"], check=True)
        subprocess.run(["python", "refresh_knowledge_files.py"], check=True)
        set_key('.env', 'LAST_KNOWLEDGE_FILE_UPDATE', dt.datetime.today().strftime('%m-%d-%Y'))
        load_dotenv(override=True)
        await discord_message.channel.send(KNOWLEDGE_UPDATE_SUCCESS_MESSAGE)
    except subprocess.CalledProcessError as e:
        print(f"Error refreshing knowledge files: {e}")
        await discord_message.channel.send(KNOWLEDGE_UPDATE_FAILED_MESSAGE)


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
