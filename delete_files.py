import openai
import os
from dotenv import load_dotenv

load_dotenv(override=True)

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

def delete_all_files():
    files = client.files.list()
    print(files)
    for file in files:
        file_id = file.id
        response = client.files.delete(file_id)
        print(f"Deleted file: {file_id}, Response: {response}")

# Call the function
delete_all_files()