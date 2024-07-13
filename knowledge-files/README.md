# Knowledge Files

This folder contains all the knowledge files for the project. 

# Folder Structure

.
├── gpt-crawler (included in repo)
├── static-files (included in repo but could get removed if files become too large in size)
├── DiscordChatExporter.Cli
├── help-messages
├── kh2rando-website
├── dynamic-files 

### DiscordChatExporter CLI

Extracting the discord messages requires the use of a tool call DiscordChatExporter. The CLI can be installed following the instructions found [here](https://github.com/Tyrrrz/DiscordChatExporter/blob/master/.docs/Using-the-CLI.md). Ensure that the directory is named "DiscordChatExporter.Cli".

### help-messages

This is the directory in which all scraped discord messages from #help should be stored. All relevant media (such as images, videos, attachments, etc.) will be stored in a subdirectory called "<Month_YYYY> MEDIA". Running extract_messages.py should prepare all relevant #help knowledge files.

### kh2rando-website

This is the directory in which all scraped kh2random.com information should be stored. gpt-crawler contains all the code for the website scraping. Run the gpt crawler by navigating to the gpt-crawler directory and then following the instructions [here](https://github.com/BuilderIO/gpt-crawler). 

### dynamic-files

This is the directory where all non-static files will be stored. At the moment this should include files scraped from:

    #openkh-visual-mods
    #openkh-audio-mods
    #openkh-gameplay-mods
    #other-mods
    #lua-scripts