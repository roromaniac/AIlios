import openai
from openai import OpenAI
import discord
import os
import json
import requests
from dotenv import load_dotenv
import asyncio
import logging
from langdetect import detect
from deep_translator import GoogleTranslator
load_dotenv()

COMMAND_NAME = "/randohelp"
REVIEW_NAME = "/review"
CONVERSATION_FILE = "conversation_logging.json"

model = 'asst_CVyBlCLuW65qRZ3MnVlTMjv6'
intents = discord.Intents.all()
client = discord.Client(intents=intents)
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

def check_rate_limit(endpoint):
    url = f"https://discord.com/api/v9/{endpoint}"
    headers = {
        "Authorization": f"Bot {os.getenv('DISCORD_TOKEN')}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        rate_limit_reset = response.headers.get("X-RateLimit-Reset")
        return rate_limit_remaining, rate_limit_reset
    else:
        logging.error(f"Failed to check rate limit: {response.status_code}")
        return None, None

# Discord helper functions
# print(f"Message sent by: {message.author.name}")
# print(f"Message sent by: {message.author}")
# print(f"User ID: {message.author.id}")
# print(f"Message sent in: {message.channel.name}")
# print(f"Message sent on server: {message.guild.name}")
# print(f"Message sent at: {message.created_at}")
# print(f"Is this a DM?: {isinstance(message.channel, discord.DMChannel)}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')


@client.event
async def on_message(discord_message):
    global total_ctx_string_len
    global context_file
    global context
    global convo_log_count
    
    await asyncio.sleep(.1)

    if discord_message.content.startswith(COMMAND_NAME):

        try:
            
            remaining, reset = check_rate_limit("channels/1238177913212502087/messages")
            print(remaining, reset)
            text = discord_message.content[(len(COMMAND_NAME)):]
            text_language = detect(text)
            if len(text) <= 2000:
                # if total_ctx_string_len < 26200: # -> 26200
                #     if total_ctx_string_len > 23850: # -> 23850
                    # print('Warning: You have used up 90 percent of the max context length for this conversation')
                # await default_channel.send('Warning: You have used up 90 percent of the max context length for this conversation, use `/newchat` to create a new one.')

                # with open(f'{path}/conversation_logs_{convo_log_count}.json', 'r') as f:
                #     context = json.load(f)
                
                current_message = {"role": "user", "content": f"{text}"}

                client = OpenAI()

                # Check if the channel of the message is an instance of discord.Thread
                is_thread = isinstance(discord_message.channel, discord.Thread)
                if is_thread:
                    discord_thread = discord_message.channel
                    conversations_logs[discord_thread.id]["message_log"].append(current_message)
                    header = f'Trying to generate a helpful response...'
                    header = GoogleTranslator(source='auto', target=text_language).translate(header)
                    await discord_thread.send(header)
                    await discord_thread.send(f'====================================================================')
                else:
                    # Create a thread linked to the message if not already in a thread
                    response = client.chat.completions.create(
                                    model="gpt-3.5-turbo",
                                    messages=[
                                        {"role": "system", "content": "You are a summarizer that adequately summarizes a help inquiry in 8 words or less in order to create good thread titles."},
                                        {"role": "user", "content": f"Please create a thread title based on the following inquiry: {text}"}
                                    ]
                                )
                    discord_thread_name = f"Discussion: {response.choices[0].message.content}"
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)
                    intro = f'Hey, {discord_message.author.display_name}! I will try to help you with your inquiry. Friendly reminder that I am just a bot and my responses are not guaranteed to work. Please consult #help for a higher guarantee of resolution should my response not help.'
                    intro = GoogleTranslator(source='auto', target=text_language).translate(intro)
                    separator = f'===================================================================='
                    # initialize conversation log with original help message and original response
                    conversations_logs[discord_thread.id] = {
                        "message_author": discord_message.author, 
                        "message_log": [current_message, {"role": "assistant", "content": f"{intro} + \n + {separator}"}]
                    }
                    await discord_thread.send(intro)
                    await discord_thread.send(separator)
                
                openai_thread = client.beta.threads.create(
                    messages = conversations_logs[discord_thread.id]["message_log"]
                )

                openai_message = client.beta.threads.messages.create(
                    thread_id=openai_thread.id,
                    role="user",
                    content=text
                )

                run = client.beta.threads.runs.create_and_poll(
                    thread_id=openai_thread.id,
                    assistant_id="asst_CVyBlCLuW65qRZ3MnVlTMjv6",
                )

                if run.status == 'completed': 
                    openai_message = client.beta.threads.messages.list(
                        thread_id=openai_thread.id
                    )
                else:
                    print(run.status)
                
                # Extract the message content
                message_content = openai_message.data[0].content[0].text
                annotations = message_content.annotations
                citations = []
                # Iterate over the annotations and add footnotes
                for index, annotation in enumerate(annotations):
                    # Replace the text with a footnote
                    message_content.value = message_content.value.replace(annotation.text, f' [{index}]')
                    # Gather citations based on annotation attributes
                    if (file_citation := getattr(annotation, 'file_citation', None)):
                        cited_file = client.files.retrieve(file_citation.file_id)
                        citations.append(f'[{index}] {file_citation.quote} from {cited_file.filename}')
                    elif (file_path := getattr(annotation, 'file_path', None)):
                        cited_file = client.files.retrieve(file_path.file_id)
                        citations.append(f'[{index}] Click <here> to download {cited_file.filename}')
                # Add footnotes to the end of the message before displaying to user
                
                # Log conversation with knowledge files cited.
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
                # print('Too long, please send shorter messages.')
                await discord_thread.send('Too long, please send shorter messages.')

        except Exception as e:

            if discord_thread is None:
                # Check if the channel of the message is an instance of discord.Thread
                is_thread = isinstance(discord_message.channel, discord.Thread) or isinstance(discord_thread, discord.Thread)
                if is_thread:
                    discord_thread = discord_message.channel
                else:
                    discord_thread_name = f"FATAL ERROR OCCURRED"
                    discord_thread = await discord_message.create_thread(name=discord_thread_name)

            await discord_thread.send('The Ailios bot could not process the response. Please try again. If it continues to fail, please ping @roromaniac informing him of the incident.')
            # Log the exception
            logging.exception("An error occurred!")

            
    elif discord_message.content.startswith(REVIEW_NAME):
        text = discord_message.content[(len(REVIEW_NAME)):]
        # Check if the channel of the message is an instance of discord.Thread
        is_thread = isinstance(discord_message.channel, discord.Thread)
        if is_thread:
            discord_thread = discord_message.channel
            text_language = detect(conversations_logs[discord_thread.id]["message_log"][0]["content"])
            if discord_message.author == conversations_logs[discord_thread.id]["message_author"]:
                try:
                    user_rating = float(text)
                    if user_rating >= 1 and user_rating <= 10:
                        conversations_logs[discord_thread.id]["rating"] = user_rating
                        await discord_thread.send("Thanks for reviewing AI-lios! Your review will help us focus on creating better responses in the future.")
                except ValueError:
                    await discord_thread.send("To leave a review for AI-lios, please provide a value between 1 (indicating inappropriate/inaccurate response) and 10 (perfect response).")


client.run(os.getenv("DISCORD_TOKEN"))

# async def new_conversation(default_channel, length_reached):
#     global convo_log_count
#     global total_ctx_string_len
#     convo_log_count += 1


#     with open(f'{path}/conversation_logs_{convo_log_count}.json', 'w') as f:
#         json.dump([], f, indent=4)
#     if length_reached:
#         # print('Context length reached. Starting new conversation.')
#         await default_channel.send('Context length reached. Starting new conversation.')
#         # get gpt-4 to summarize the entire conversation
#         with open(f'{path}/conversation_logs_{convo_log_count-1}.json', 'r') as f:
#             new_conv_context = json.load(f)
#         response = openai.chat.completions.create(
#                     model="gpt-4",
#                     messages=[{"role": "system", "content": f"Summarize the what was discussed and asked in the following conversation: {new_conv_context}"}]
#                 )
#         response = response['choices'][0]["message"]['content']
#         summary = response

#         with open('info.json', 'r') as f:
#             info = json.load(f)
#         conservations = info[0]

#         next_key = str(len(conservations))

#         info[0][str(convo_log_count-1)]['summarization'] = summary

#         new_entry = {
#             "total_length": 0,
#             "summarization": ""
#         }

#         conservations[next_key] = new_entry

#         info[0] = conservations
#         with open('info.json', 'w') as f:
#             json.dump(info, f, indent=4)

#         with open(f'{path}/conversation_logs_{convo_log_count}.json', 'w') as f:
#             json.dump([{"role": "system", "content": f"{summary}"}], f, indent=4) 
        
#     else:
#         # print('Started new conversation.')

#         with open(f'{path}/conversation_logs_{convo_log_count-1}.json', 'r') as f:
#             new_conv_context = json.load(f)
#         response = openai.chat.completions.create(
#                     model=model,
#                     messages=[{"role": "system", "content": f"Summarize the what was discussed and asked in the following conversation: {new_conv_context}"}]
#                 )
#         response = response.choices[0].message.content
#         summary = response
#         with open('info.json', 'r') as f:
#             info = json.load(f)
#         conservations = info[0]

#         next_key = str(len(conservations))

#         info[0][str(convo_log_count-1)]['summarization'] = summary

#         new_entry = {
#             "total_length": 0,
#             "summarization": ""
#         }

#         conservations[next_key] = new_entry

#         info[0] = conservations
#         with open('info.json', 'w') as f:
#             json.dump(info, f, indent=4)
#         context = sys_prompt
#         with open(f'{path}/conversation_logs_{convo_log_count}.json', 'w') as f:
#             json.dump(context, f, indent=4) 
#         await default_channel.send('Started new conversation.')