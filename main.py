import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os
import tracemalloc

if __name__ == "__main__":

    tracemalloc.start()
    # Set env
    load_dotenv()
    bot_token = os.getenv("DISCORD_TOKEN")

    intents = discord.Intents.all()
    intents.message_content = True

    bot = commands.Bot(command_prefix='.', intents=intents, application_id=int(os.getenv('APPLICATION_ID')))
    @bot.event
    async def on_ready():
        print('Online.')

    async def load():
        for filename in os.listdir(os.path.join(os.getcwd(), 'Scripts', 'Cogs')):
            if filename.endswith('.py') and filename != '__init__.py':
                await bot.load_extension(f'Scripts.Cogs.{filename[:-3]}')
                
    async def main():
        await load()
        await bot.start(bot_token)

    asyncio.run(main())