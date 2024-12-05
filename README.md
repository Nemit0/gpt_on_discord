# Discord Bot for Raspberry Pi(or any debian system)

This project is to use openai and discord.py to make a discord bot that can interact with user on a given discord channel.
Requires Python>=3.10

## Project Setup

1. First, use the following command to make a venv(or you can use a conda env. Just don't install everything on base env)
```bash
python3 -m venv venv
source ./venv/bin/activate
```

2. Next install all the requirements from requirememnts.txt
```bash
python3 -m pip install -r requirements
```

3. Use the .env.template file to make .env file, and fill up all the keys accordingly
```bash
cp .env.template .env
```

4. The chatbot is in the Scripts/Cogs/chatbot.py cog and nasa img_of_day is in the same directory. You can edit it per your preference.

5. Run main.py to start the bot. If it runs sucessfully it will send online to set channel.