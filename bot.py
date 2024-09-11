"""Script for bot behavior on startup and on message."""

# pylint: disable=wildcard-import, unused-wildcard-import, broad-exception-caught

import os
import json
import logging
import asyncio
import subprocess
import datetime as dt

import discord
from dotenv import load_dotenv, set_key

import openai
from openai import OpenAI

from config import *
from messages import *
from utils import *

load_dotenv()

intents = discord.Intents.all()
discord_client = discord.Client(intents=intents)
permissions = discord.Permissions(8)

openai.organization = os.getenv("ORG")
openai.api_key = os.getenv("OPENAI_API_KEY")

logging.basicConfig(
    filename='app.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@discord_client.event
async def on_ready():
    """
        Tasks to perform upon bot server startup.
    """
    print(f'Logged in as {discord_client.user}')


@discord_client.event
async def on_message(discord_message):
    """
        Tasks to perform when the discord server receives a message.
    """
    await asyncio.sleep(.1)

    load_dotenv()

    conversations_logs = setup_conversation_logs()

    if discord_message.content.startswith(HELP_COMMAND):

        if knowledge_file_needs_update():
            update_knowledge_files(discord_message)
            return

        discord_thread = None
        openai_client = OpenAI()

        # remove command from query
        text = discord_message.content.removeprefix(HELP_COMMAND + " ")

        text_language = detect_message_language(text)

        try:

            # check if memory is getting close to server limit
            await storage_check(discord_client)

            # handle rate limits
            remaining, reset = check_rate_limit(f"channels/{discord_message.channel.id}/messages")
            rate_limit_met = await handle_rate_limit(discord_message, float(remaining), float(reset), is_discord_thread(discord_message, discord_thread))
            if rate_limit_met:
                return

            if len(text) > MAX_CHARS_DISCORD:
                await discord_thread.send(TOO_LONG_DISCORD_MESSAGE_ERROR_MESSAGE)
                return

            discord_thread, existing_thread = await get_discord_thread(openai_client, discord_message, message_content=text)
            await send_initial_discord_response(discord_thread, discord_message, text_language)
            conversations_logs = log_conversation(conversations_logs, discord_message, discord_thread, text_language, "user", text, existing_thread)

            if thread_message_counts(conversations_logs, discord_thread) > MAX_MESSAGES_ALLOWED_IN_THREAD:
                await send_response_to_discord(discord_thread, MAX_MESSAGES_REACHED_MESSAGE)
                return

            # establish existing conversation thread for context
            openai_thread = openai_client.beta.threads.create(
                messages = conversations_logs[discord_thread.id]["message_log"]
            )

            # create text and image content to send to assistant
            text_content, image_content = await populate_OPENAI_ASSISTANT_ID_content(openai_client, discord_message, discord_thread, text)
            _ = openai_client.beta.threads.messages.create(
                thread_id=openai_thread.id,
                role="user",
                content=text_content + image_content
            )

            # attempt to extract response
            run = openai_client.beta.threads.runs.create_and_poll(
                thread_id=openai_thread.id,
                assistant_id=OPENAI_ASSISTANT_ID,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
            )

            # extract assistant response if run successfully completed
            openai_message = await get_assistant_response(openai_client, openai_thread, run, discord_thread)

            # log the cost of getting the last response
            input_cost, output_cost, image_cost = get_openai_run_cost(run, len(image_content))
            conversations_logs[discord_thread.id]["cost_in_dollars"]["input_cost"] += input_cost
            conversations_logs[discord_thread.id]["cost_in_dollars"]["output_cost"] += output_cost
            conversations_logs[discord_thread.id]["cost_in_dollars"]["image_cost"] += image_cost
            conversations_logs[discord_thread.id]["cost_in_dollars"]["total_cost"] += (input_cost + output_cost + image_cost)

            # extract the message content
            # the list is populated from the front so the first message is the most recent assistant response
            message_content = openai_message.data[0].content[0].text
            # handle citations
            annotations, citations = extract_citations(openai_client, message_content)

            # log conversation with knowledge files cited (in a thread that already exists)
            conversations_logs = log_conversation(conversations_logs, discord_message, discord_thread, text_language, "assistant", message_content.value + '\n' + '\n'.join(citations), True)

            for index, _ in enumerate(annotations):
                # remove source citation text
                message_content.value = message_content.value.replace(f' [{index}]', '')

            # send response to discord using several messages if need be
            await send_response_to_discord(discord_thread, message_content.value)  

        except Exception:

            discord_thread, existing_thread = await get_discord_thread(openai_client, discord_message, THREAD_TITLE_ERROR_MESSAGE)
            await send_initial_discord_response(discord_thread, existing_thread, discord_message, text_language)
            translated_error_message = translate_error_message(text_language)
            conversations_logs = log_conversation(conversations_logs, discord_message, discord_thread, text_language, "assistant", translated_error_message, existing_thread)
            await discord_thread.send(translated_error_message)
            logging.exception("ERROR OCCURRED")


    elif discord_message.content.startswith(REVIEW_COMMAND):

        openai_client = OpenAI()
        discord_thread, existing_thread = await get_discord_thread(openai_client, discord_message, discord_thread_name=THREAD_TITLE_ERROR_MESSAGE)
        # store the review or send an error message that review can't be done
        try:
            conversations_logs = await submit_review(discord_thread, discord_message, conversations_logs)

        except Exception:
            # communicate to user that there is a fatal error
            await discord_thread.send(BOT_ERROR_MESSAGE)
            logging.exception("ERROR OCCURRED")

    
    elif discord_message.content.startswith(CORRECTION_COMMAND):

        openai_client = OpenAI()
        discord_thread, existing_thread = await get_discord_thread(openai_client, discord_message, discord_thread_name=THREAD_TITLE_ERROR_MESSAGE)
        
        if existing_thread and (
            discord_message.author.name == conversations_logs[discord_thread.id]["message_author"] or
            any(role.name in CORRECTION_PERMITTED_ROLES for role in discord_message.author.roles)
        ):
            # store the review or send an error message that review can't be done
            try:
                conversations_logs = await submit_correction(discord_thread, discord_message, conversations_logs)

            except Exception:
                # communicate to user that there is a fatal error
                await discord_thread.send(BOT_ERROR_MESSAGE)
                logging.exception("ERROR OCCURRED")

        else:
            await discord_thread.send(PERMISSION_DENIED_MESSAGE)

    
    elif discord_message.content.startswith(TRIGGER_UPDATE_COMMAND):

        if any(role.name in CORRECTION_PERMITTED_ROLES for role in discord_message.author.roles):

            update_knowledge_files(discord_message)

    elif discord_message.content.startswith(LAST_UPDATE_COMMAND):

        await discord_message.channel.send(LAST_UPDATE_MESSAGE)

    # save the conversation logs
    with open(CONVERSATION_FILE, 'w', encoding='utf-8') as logs:
        json.dump(conversations_logs, logs, indent=4)

discord_client.run(os.getenv("DISCORD_TOKEN"))
