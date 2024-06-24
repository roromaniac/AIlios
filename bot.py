import os
import json
import logging
import asyncio

import discord
from dotenv import load_dotenv
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

conversations_logs = setup_conversation_logs()

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')


@discord_client.event
async def on_message(discord_message):
    
    await asyncio.sleep(.1)

    if discord_message.content.startswith(COMMAND_NAME):

        try:

            # identify if message is part of thread
            discord_thread = None
            is_thread = isinstance(discord_message.channel, discord.Thread)

            # storage sanity check
            await storage_check(discord_client)

            # handle rate limits
            remaining, reset = check_rate_limit("channels/1238177913212502087/messages")
            rate_limit_met = await handle_rate_limit(discord_message, float(remaining), float(reset), is_thread)
            if rate_limit_met:
                return

            # remove command from query
            text = discord_message.content[(len(COMMAND_NAME) + 1):]

            text_language = detect_message_language(text)

            if len(text) <= 2000:
    
                current_message = {"role": "user", "content": f"{text}"}
                openai_client = OpenAI()

                # check if the channel of the message is an instance of discord.Thread
                if is_thread:
                    discord_thread = discord_message.channel
                    conversations_logs[discord_thread.id]["message_log"].append(current_message)
                    header = EXISTING_THREAD_HEADER
                    header = GoogleTranslator(source='auto', target=text_language).translate(header)
                    await discord_thread.send(header)
                    await discord_thread.send(SEPARATOR)
                else:
                    # create a thread linked to the message if not already in a thread
                    response = openai_client.chat.completions.create(
                                    model=MODEL,
                                    messages=[
                                        {"role": "system", "content": THREAD_TITLE_SYSTEM_PROMPT},
                                        {"role": "user", "content": f"{THREAD_TITLE_USER_PROMPT}: {text}"}
                                    ]
                                )
                    discord_thread_name = f"{THREAD_CATEGORY}: {response.choices[0].message.content}"
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)
                    intro = f'Hey, {discord_message.author.display_name}! {NEW_THREAD_HEADER}'
                    intro = GoogleTranslator(source='auto', target=text_language).translate(intro)
                    # initialize conversation log with original help message and original response
                    conversations_logs[discord_thread.id] = {
                        "message_author": discord_message.author.name, 
                        "message_content_summary": discord_thread_name.removeprefix(f"{THREAD_CATEGORY}: "),
                        "message_language": text_language,
                        "message_log": [current_message, {"role": "assistant", "content": f"{intro}"}]
                    }
                    await discord_thread.send(intro)
                    await discord_thread.send(SEPARATOR)

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
                    max_completion_tokens=MAX_COMPLETION_TOKENS,
                )

                # extract assistant response if run successfully completed
                # this response is the only added message to the thread so openai_message only stores one message
                if run.status == 'completed':
                    openai_message = openai_client.beta.threads.messages.list(
                        thread_id=openai_thread.id
                    )
                else:
                    print(run.incomplete_details)
                    print(run.last_error)
                    raise RuntimeError("The OpenAI message failed to generate.")

                # extract the message content
                message_content = openai_message.data[0].content[0].text
                # handle citations
                annotations, citations = extract_citations(openai_client, message_content)

                # log conversation with knowledge files cited.
                conversations_logs[discord_thread.id]["message_log"].append({"role": "assistant", "content": message_content.value + '\n' + '\n'.join(citations)})

                for index, _ in enumerate(annotations):
                    # remove source citation text
                    message_content.value = message_content.value.replace(f' [{index}]', '')

                response = message_content.value

                num_messages_needed = (len(response) // MAX_CHARS_DISCORD) + 1
                for i in range(num_messages_needed):
                    if num_messages_needed == 1:
                        await discord_thread.send(response)
                    else:
                        await discord_thread.send(f"[{i}/{num_messages_needed}]" + response[(MAX_CHARS_DISCORD*i):(MAX_CHARS_DISCORD*(i+1))])

                
                
                with open(CONVERSATION_FILE, 'w', encoding='utf-8') as logs:
                    json.dump(conversations_logs, logs, indent=4)

            else:

                await discord_thread.send(TOO_LONG_DISCORD_MESSAGE_ERROR_MESSAGE)

        except Exception:

            text = discord_message.content[(len(COMMAND_NAME) + 1):]
            if discord_thread is None:
                is_thread = isinstance(discord_message.channel, discord.Thread) or isinstance(discord_thread, discord.Thread)
                if is_thread:
                    discord_thread = discord_message.channel
                else:
                    discord_thread_name = THREAD_TITLE_ERROR_MESSAGE
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)
                    current_message = {"role": "user", "content": f"{text}"}
                    conversations_logs[discord_thread.id] = {
                        "message_author": discord_message.author.name, 
                        "message_log": [current_message]
                    }
            try:
                text_language = detect_message_language(text)
                translated_error_message = GoogleTranslator(source='auto', target=text_language).translate(BOT_ERROR_MESSAGE)
            except Exception:
                translated_error_message = BOT_ERROR_MESSAGE
                logging.exception("ERROR OCCURRED")
            conversations_logs[discord_thread.id]["message_log"].append({"role": "assistant", "content": translated_error_message})
            await discord_thread.send(translated_error_message)
            logging.exception("ERROR OCCURRED")

            
    elif discord_message.content.startswith(REVIEW_NAME):

        try:

            text = discord_message.content[(len(REVIEW_NAME) + 1):]
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

        except Exception:

            if discord_thread is None:
                is_thread = isinstance(discord_message.channel, discord.Thread) or isinstance(discord_thread, discord.Thread)
                if is_thread:
                    discord_thread = discord_message.channel
                else:
                    discord_thread_name = THREAD_TITLE_ERROR_MESSAGE
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)

            await discord_thread.send(BOT_ERROR_MESSAGE)
            logging.exception("ERROR OCCURRED")

discord_client.run(os.getenv("DISCORD_TOKEN"))
