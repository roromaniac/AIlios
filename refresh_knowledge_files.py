import glob
import os
import warnings
from openai import OpenAI
from config import OPENAI_ASSISTANT_ID
 
client = OpenAI()

# Delete all previous files.
files_list = client.files.list() 
for file in files_list:
    client.files.delete(file.id)

# Update the vector store ID if a new one is created.
vector_store_list = client.beta.vector_stores.list().data
if len(vector_store_list) == 0:
    vector_store = client.beta.vector_stores.create(name="KH2FM Rando Bot Knowledge Files")
    with open('config.py', 'r') as file:
        config_content = file.readlines()
    for i, line in enumerate(config_content):
        if line.strip().startswith('OPENAI_VECTOR_STORE_ID'):
            config_content[i] = f"OPENAI_VECTOR_STORE_ID = '{vector_store.id}'\n"
            break
    with open('config.py', 'w') as file:
        file.writelines(config_content)
    warnings.warn(f"The OPENAI_VECTOR_STORE_ID in config.py has been updated to {vector_store.id}")

from config import OPENAI_VECTOR_STORE_ID
# Generate the new knowledge files.
file_paths = glob.glob(os.path.join('knowledge-files', 'dynamic-files', '**', '*.json'), recursive=True)
file_paths += glob.glob(os.path.join('knowledge-files', 'static-files', '*.*'), recursive=True)
file_streams = [open(path, "rb") for path in file_paths]
 
# Use the upload and poll SDK helper to upload the files, add them to the vector store,
# and poll the status of the file batch for completion.
file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
  vector_store_id=OPENAI_VECTOR_STORE_ID, files=file_streams
)

print(file_batch.status)
print(file_batch.file_counts)

client.beta.assistants.update(
  assistant_id=OPENAI_ASSISTANT_ID,
  tool_resources={"file_search": {"vector_store_ids": [OPENAI_VECTOR_STORE_ID]}},
)