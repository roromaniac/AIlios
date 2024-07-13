# You will need to download the DiscordChatExporter.Cli in order to extract the messages from the Discord server.
# You can download it from https://github.com/Tyrrrz/DiscordChatExporter/releases

import json
import os
import subprocess
import itertools as it
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from dateutil.relativedelta import relativedelta
from datetime import datetime

load_dotenv()

DATE_FORMAT = "%Y-%m-%d"
BASE_DIR = os.path.join(os.path.dirname(__file__), "knowledge-files")  # Get the directory of the current Python file

# #help messages
FILES_DIR = os.path.join(BASE_DIR, "help-messages")

# Get the current date
current_date = datetime.now()

# Generate the last day of the previous 13 months in chronological order
dates = [(current_date - relativedelta(months=i)).replace(day=1) - relativedelta(days=1) for i in range(12, -1, -1)]
dates = [date.strftime(DATE_FORMAT) for date in dates]

def strip_help_messages(date_filename):
    with open(os.path.join(FILES_DIR, date_filename), "r", encoding="utf-8") as file:
        data = json.load(file)
    for message in data["messages"]:
        del message["type"]
        del message["timestampEdited"]
        del message["callEndedTimestamp"]
        del message["isPinned"]
        del message["reactions"]
        del message["stickers"]
        del message["author"]["id"]
        del message["author"]["discriminator"]
        del message["author"]["nickname"]
        del message["author"]["color"]
        del message["author"]["avatarUrl"]
        message["author"]["roles"] = [role["name"] for role in message["author"]["roles"]]
    with open(os.path.join(FILES_DIR, date_filename), "w", encoding="utf-8") as file:
        json.dump(data, file)

commands = []
for after_date, before_date in zip(dates, dates[1:]):
    date_filename = f"{datetime.strptime(before_date, DATE_FORMAT).strftime('%B_%Y')}.json"
    output_file = os.path.join(FILES_DIR, date_filename)
    media_dir = os.path.join(FILES_DIR, f"{date_filename.replace(".json", "")} MEDIA")
    commands.append([
        "DiscordChatExporter.Cli.exe", "export", "-t", os.getenv("DISCORD_SCRAPER_TOKEN"), 
        "-c", "721205500556869642", "-f", "Json", "-o", output_file, 
        "--media", "--reuse-media", "--media-dir", media_dir, 
        "--after", after_date, "--before", before_date
    ])

def run_command(command):
    subprocess.run(command, shell=True, cwd=os.path.join(BASE_DIR, "DiscordChatExporter.Cli"))

with ThreadPoolExecutor(max_workers=12) as executor:
    executor.map(run_command, commands)

for after_date, before_date in zip(dates, dates[1:]):
    date_filename = f"{datetime.strptime(before_date, DATE_FORMAT).strftime('%B_%Y')}.json"
    strip_help_messages(date_filename)


