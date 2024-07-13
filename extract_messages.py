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

# Get the current date
current_date = datetime.now()

# Generate the last day of the previous 13 months in chronological order
dates = [(current_date - relativedelta(months=i)).replace(day=1) - relativedelta(days=1) for i in range(12, -1, -1)]
dates = [date.strftime(DATE_FORMAT) for date in dates]

def strip_messages(date_filename):
    with open(os.path.join(BASE_DIR, date_filename), "r") as file:
        data = json.load(file)

    

commands = []
for after_date, before_date in zip(dates, dates[1:]):
    date_filename = f"{datetime.strptime(before_date, DATE_FORMAT).strftime('%B_%Y')}.json"
    output_file = os.path.join(BASE_DIR, date_filename)
    media_dir = os.path.join(BASE_DIR, f"{date_filename} MEDIA")
    commands.append([
        "DiscordChatExporter.Cli.exe", "export", "-t", os.getenv("DISCORD_SCRAPER_TOKEN"), 
        "-c", "721205500556869642", "-f", "Json", "-o", output_file, 
        "--media", "--reuse-media", "--media-dir", media_dir, 
        "--after", after_date, "--before", before_date
    ])
    strip_messages(date_filename)

def run_command(command):
    subprocess.run(command, shell=True, cwd=os.path.join(BASE_DIR, "DiscordChatExporter.Cli"))

with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(run_command, commands)


