"""
You will need to download the DiscordChatExporter.Cli in order to extract the messages from the Discord server.
You can download it from https://github.com/Tyrrrz/DiscordChatExporter/releases
"""

import json
import os
import re
import subprocess
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from dateutil.relativedelta import relativedelta
from datetime import datetime

from config import DATE_FORMAT, DYNAMIC_CHANNEL_IDS

load_dotenv(override=True)

BASE_DIR = os.path.join(os.path.dirname(__file__), "knowledge-files")  # Get the directory of the current Python file
DYNAMIC_FILES_DIR = os.path.join(BASE_DIR, "dynamic-files")

# Get the current date
current_date = datetime.now()

# Generate the last day of the previous 13 months in chronological order
dates = [(current_date - relativedelta(months=i)).replace(day=1) - relativedelta(days=1) for i in range(12, -1, -1)]
dates = [date.strftime(DATE_FORMAT) for date in dates]

def run_command(command):
    """
        Runs a terminal command to start Discord Chat Exporting.

        Args:
            command: The terminal command to be run.
    """
    subprocess.run(command, cwd=os.path.join(BASE_DIR, "DiscordChatExporter.Cli"), check=True)

def strip_discord_messages(knowledge_filepath, dated_filename):
    """
        Strips the relevant content from the messages within a discord channel. 

        Args:
            knowledge_filepath: The filepath of where the relevant knowledge files are located (usually dynamic files).
            dated_filename: The filename for the information in question. May be dated.

        Outputs:
            Stripped discord messages pertaining to the relevant files in question.
    """
    current_filepath = os.path.join(knowledge_filepath, dated_filename)
    if os.path.exists(current_filepath):
        with open(current_filepath, "r", encoding="utf-8") as file:
            if os.path.getsize(current_filepath) > 0:  # Check if the file has non-null content
                data = json.load(file)
            else:
                os.remove(current_filepath)  # Delete the file if it is empty
                return  # Exit the function as there's no need to process further
        for message in data["messages"]:
            message.pop("type", None)
            message.pop("timestampEdited", None)
            message.pop("callEndedTimestamp", None)
            message.pop("isPinned", None)
            message.pop("reactions", None)
            message.pop("stickers", None)
            message["author"].pop("id", None)
            message["author"].pop("discriminator", None)
            message["author"].pop("nickname", None)
            message["author"].pop("color", None)
            message["author"].pop("avatarUrl", None)
            # ensure that the roles are in dictionary form before scarping the relevant role titles
            if "roles" in message["author"]:
                if isinstance(message["author"]["roles"], list):
                    if len(message["author"]["roles"]) > 0 and isinstance(message["author"]["roles"][0], dict):
                        message["author"]["roles"] = [role["name"] for role in message["author"]["roles"]]
        with open(os.path.join(knowledge_filepath, dated_filename), "w", encoding="utf-8") as file:
            json.dump(data, file)

def delete_excess_media(media_dir):
    media_files = os.listdir(media_dir)
    emotes_and_profiles = [file for file in media_files if re.search(r"-[a-zA-Z0-9]{5}", file)]
    for file in emotes_and_profiles:
        os.remove(os.path.join(media_dir, file))


command_list = []
COMMAND_NAME = "DiscordChatExporter.Cli.exe" if os.name == 'nt' else "./DiscordChatExporter.Cli"
for channel_name, channel_info in DYNAMIC_CHANNEL_IDS.items():
    channel_id, batch_channel_by_date = channel_info["id"], channel_info["batch_by_date"]
    current_knowledge_filepath = os.path.join(DYNAMIC_FILES_DIR, channel_name)
    if batch_channel_by_date:
        for after_date, before_date in zip(dates, dates[1:]):
            date_filename = f"{channel_name}-{datetime.strptime(before_date, DATE_FORMAT).strftime('%B_%Y')}.json"
            output_file = os.path.join(current_knowledge_filepath, date_filename)
            # media_dir = os.path.join(current_knowledge_filepath, f"{date_filename.replace(".json", "")} MEDIA")
            command_list.append([
                COMMAND_NAME, "export", "-t", os.getenv("DISCORD_SCRAPER_TOKEN"), 
                "-c", f"{channel_id}", "-f", "Json", "-o", output_file, 
                # "--media", "--reuse-media", "--media-dir", media_dir, 
                "--after", after_date, "--before", before_date
            ])
    else:
        output_file = os.path.join(current_knowledge_filepath, f"{channel_name}.json")
        media_dir = os.path.join(current_knowledge_filepath, f"{channel_name} MEDIA")
        command_list.append([
            COMMAND_NAME, "export", "-t", os.getenv("DISCORD_SCRAPER_TOKEN"), 
            "-c", f"{channel_id}", "-f", "Json", "-o", output_file, 
            # "--media", "--reuse-media", "--media-dir", media_dir
        ])

with ThreadPoolExecutor(max_workers=12) as executor:
    executor.map(run_command, command_list)


for channel_name, channel_info in DYNAMIC_CHANNEL_IDS.items():
    channel_id, batch_channel_by_date = channel_info["id"], channel_info["batch_by_date"]
    current_knowledge_filepath = os.path.join(DYNAMIC_FILES_DIR, channel_name)
    if batch_channel_by_date:
        for after_date, before_date in zip(dates, dates[1:]):
            date_filename = f"{channel_name}-{datetime.strptime(before_date, DATE_FORMAT).strftime('%B_%Y')}.json"
            strip_discord_messages(current_knowledge_filepath, date_filename)
            # media_dir = os.path.join(current_knowledge_filepath, f"{date_filename.replace(".json", "")} MEDIA")
            # delete_excess_media(media_dir)
    else:
        date_filename = f"{channel_name}.json"
        strip_discord_messages(current_knowledge_filepath, date_filename)
        # media_dir = os.path.join(current_knowledge_filepath, f"{channel_name} MEDIA")
        # delete_excess_media(media_dir)

