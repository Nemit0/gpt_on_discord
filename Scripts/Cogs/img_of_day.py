import discord
from discord.ext import tasks, commands
from datetime import datetime
import requests
import os

class NasaImagePoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.nasa_api_key = os.getenv('NASA_API_KEY')  # Load NASA API Key from environment variables
        self.channel_id = int(os.getenv("NASA_IMAGE_CHANNEL_ID"))  # Load Discord channel ID from environment variables
        self.nasa_url = 'https://api.nasa.gov/planetary/apod'
        self.post_image_of_the_day.start()  # Start the loop

    @tasks.loop(hours=24)
    async def post_image_of_the_day(self):
        # If the time is not 1600 UTC, wait until it is
        now = datetime.now(datetime.timezone.utc)
        if now.hour != 16 or now.minute != 0:
            print(f'Waiting until 16:00 UTC. Current time is {now.strftime("%H:%M")}.')
            return
        
        # Parameters for the NASA API request
        params = {
            'api_key': self.nasa_api_key
        }

        try:
            response = requests.get(self.nasa_url, params=params)
            response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code

            # Proceed with parsing the response...
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")  # Python 3.6
        except Exception as err:
            print(f"An error occurred: {err}")

        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()

            # Access the image, its title, and explanation
            image_url = data['url']
            title = data['title']
            explanation = data['explanation']

            # Find the channel
            channel = self.bot.get_channel(self.channel_id)

            if channel:
                # Create an embed message for Discord
                embed = discord.Embed(title=title, description=explanation, color=0x1a1aff)
                embed.set_image(url=image_url)

                # Send the embed message to the channel
                try:
                    await channel.send(embed=embed)
                except discord.errors.Forbidden:
                    print("I don't have permission to send messages in this channel.")
                except discord.errors.HTTPException as e:
                    print(f"Sending message failed: {e}")
                    
            else:
                print(f'Channel with ID {self.channel_id} not found.')
        else:
            print(f"Error: Unable to retrieve data. Status code: {response.status_code}")

    @post_image_of_the_day.before_loop
    async def before_post_image_of_the_day(self):
        print('Waiting for the bot to be ready before starting the loop...')
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        print('NasaImagePoster cog is ready and online!')

async def setup(bot):
    await bot.add_cog(NasaImagePoster(bot), guilds=[discord.Object(id=os.getenv("DISCORD_GUILD"))])