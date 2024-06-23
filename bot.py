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
from utils import *

load_dotenv()

intents = discord.Intents.all()
discord_client = discord.Client(intents=intents)
permissions = discord.Permissions(8)

openai.organization = os.getenv("ORG")
openai.api_key = os.getenv("OPENAI_API_KEY")

logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

if os.path.exists(CONVERSATION_FILE):
    with open(CONVERSATION_FILE, "r") as logs:
        try:
            conversations_logs = json.load(logs)
            conversations_logs = {int(k): v for k, v in conversations_logs.items()}
        except json.decoder.JSONDecodeError:
            conversations_logs = {}
else:
    conversations_logs = {}
    with open(CONVERSATION_FILE, "w") as logs:
        json.dump(conversations_logs, logs)

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')


@discord_client.event
async def on_message(discord_message):
    global total_ctx_string_len
    global context_file
    global context
    global convo_log_count
    
    await asyncio.sleep(.1)

    if discord_message.content.startswith(COMMAND_NAME):

        try:

            # identify if message is part of thread
            discord_thread = None
            is_thread = isinstance(discord_message.channel, discord.Thread)

            # storage sanity check
            storage_check(discord_client)

            # handle rate limits
            remaining, reset = check_rate_limit("channels/1238177913212502087/messages")
            rate_limit_met = handle_rate_limit(discord_message, remaining, reset, is_thread)
            if rate_limit_met:
                return
            
            # remove command from query
            text = discord_message.content[(len(COMMAND_NAME) + 1):]
            
            # detect message language
            text_language = detect_message_language(text)

            if len(text) <= 2000:
                
                current_message = {"role": "user", "content": f"{text}"}
                openai_client = OpenAI()

                # check if the channel of the message is an instance of discord.Thread
                if is_thread:
                    discord_thread = discord_message.channel
                    conversations_logs[discord_thread.id]["message_log"].append(current_message)
                    header = f'Trying to generate a helpful response...'
                    header = GoogleTranslator(source='auto', target=text_language).translate(header)
                    await discord_thread.send(header)
                    await discord_thread.send(f'====================================================================')
                else:
                    # create a thread linked to the message if not already in a thread
                    response = openai_client.chat.completions.create(
                                    model=MODEL,
                                    messages=[
                                        {"role": "system", "content": THREAD_TITLE_SYSTEM_PROMPT},
                                        {"role": "user", "content": f"{THREAD_TITLE_USER_PROMPT}: {text}"}
                                    ]
                                )
                    discord_thread_name = f"Discussion: {response.choices[0].message.content}"
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)
                    intro = f'Hey, {discord_message.author.display_name}! I will try to help you with your inquiry. Friendly reminder that I am just a bot and my responses are not guaranteed to work. Please consult #help for a higher guarantee of resolution should my response not help.'
                    intro = GoogleTranslator(source='auto', target=text_language).translate(intro)
                    separator = f'===================================================================='
                    # initialize conversation log with original help message and original response
                    conversations_logs[discord_thread.id] = {
                        "message_author": discord_message.author.name, 
                        "message_content_summary": discord_thread_name.removeprefix("Discussion: "),
                        "message_language": text_language,
                        "message_log": [current_message, {"role": "assistant", "content": f"{intro} + \n + {separator}"}]
                    }
                    await discord_thread.send(intro)
                    await discord_thread.send(separator)
                
                # establish existing conversation thread for context
                openai_thread = openai_client.beta.threads.create(
                    messages = conversations_logs[discord_thread.id]["message_log"]
                )

                if len(discord_message.attachments) > 0:
                    # establish new message for assistant
                    text_content = [{
                        "type": "text",
                        "text": text
                    }]
                    image_content = discord_to_openai_image_conversion(discord_message, openai_client)
                    user_inquiry = openai_client.beta.threads.messages.create(
                        thread_id=openai_thread.id,
                        role="user",
                        content=text_content + image_content
                    )
                
                else:
                    # establish new message for assistant
                    user_inquiry = openai_client.beta.threads.messages.create(
                        thread_id=openai_thread.id,
                        role="user",
                        content=text
                    )

                # attempt to extract response
                run = openai_client.beta.threads.runs.create_and_poll(
                    thread_id=openai_thread.id,
                    assistant_id=OPENAI_ASSISTANT,
                )

                # extract assistant response if run successfully completed
                # this response is the only added message to the tread so openai_message only stores one message
                if run.status == 'completed': 
                    openai_message = openai_client.beta.threads.messages.list(
                        thread_id=openai_thread.id
                    )
                else:
                    raise RuntimeError("The OpenAI message failed to generate.")
                
                # extract the message content
                message_content = openai_message.data[0].content[0].text
                # handle citations
                annotations, citations = extract_citations(message_content)
                
                # log conversation with knowledge files cited.
                conversations_logs[discord_thread.id]["message_log"].append({"role": "assistant", "content": message_content.value + '\n' + '\n'.join(citations)})

                for index, annotation in enumerate(annotations):
                    # Remove source citation text
                    message_content.value = message_content.value.replace(f' [{index}]', f'')

                response = message_content.value

                if len(response) > 2000:
                    await discord_thread.send("Discord can't process message longer than 2000 chars. Try to ask a simpler question so that the character limit is not exceeded.")
                    
                await discord_thread.send(response)
                                
                with open(CONVERSATION_FILE, 'w') as logs:
                    json.dump(conversations_logs, logs, indent=4)

            else:

                await discord_thread.send('Too long, please send shorter messages.')

        except Exception as e:

            ERROR_MESSAGE = f'The Ailios bot could not process the response. Please try again. I have pinged <@611722032198975511> informing him of the incident.'
            text = discord_message.content[(len(COMMAND_NAME) + 1):]
            if discord_thread is None:
                # Check if the channel of the message is an instance of discord.Thread
                is_thread = isinstance(discord_message.channel, discord.Thread) or isinstance(discord_thread, discord.Thread)
                if is_thread:
                    discord_thread = discord_message.channel
                else:
                    discord_thread_name = f"FATAL ERROR OCCURRED"
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)
                    current_message = {"role": "user", "content": f"{text}"}
                    conversations_logs[discord_thread.id] = {
                        "message_author": discord_message.author.name, 
                        "message_log": [current_message]
                    }
            try:
                text_language = detect_message_language(text)
                translated_error_message = GoogleTranslator(source='auto', target=text_language).translate(ERROR_MESSAGE)
            except Exception as e_translate:
                translated_error_message = ERROR_MESSAGE
                logging.exception("ERROR OCCURRED")
            conversations_logs[discord_thread.id]["message_log"].append({"role": "assistant", "content": translated_error_message})
            await discord_thread.send(translated_error_message)
            # Log the exception
            logging.exception("ERROR OCCURRED")

            
    elif discord_message.content.startswith(REVIEW_NAME):

        try:

            text = discord_message.content[(len(REVIEW_NAME) + 1):]
            # Check if the channel of the message is an instance of discord.Thread
            is_thread = isinstance(discord_message.channel, discord.Thread)
            if is_thread:
                discord_thread = discord_message.channel
                first_thread_message = conversations_logs[discord_thread.id]["message_log"][0]["content"]
                text_language = detect_message_language(first_thread_message)
                if discord_message.author.name == conversations_logs[discord_thread.id]["message_author"]:
                    try:
                        user_rating = float(text)
                        if user_rating >= 1 and user_rating <= 10:
                            conversations_logs[discord_thread.id]["rating"] = user_rating
                            await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(REVIEW_SUCCESS_MESSAGE))
                        else:
                            await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(REVIEW_FAILURE_MESSAGE))
                    except ValueError:
                        await discord_thread.send(GoogleTranslator(source='auto', target=text_language).translate(REVIEW_FAILURE_MESSAGE))

        except Exception as e:

            ERROR_MESSAGE = f'The Ailios bot could not process the response. Please try again. I have pinged <@611722032198975511> informing him of the incident.'
            if discord_thread is None:
                # check if the channel of the message is an instance of discord.Thread
                is_thread = isinstance(discord_message.channel, discord.Thread) or isinstance(discord_thread, discord.Thread)
                if is_thread:
                    discord_thread = discord_message.channel
                else:
                    discord_thread_name = f"FATAL ERROR OCCURRED"
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)

            await discord_thread.send(ERROR_MESSAGE)
            # log the exception
            logging.exception("ERROR OCCURRED")

discord_client.run(os.getenv("DISCORD_TOKEN"))