import discord
from openai import OpenAI
import os
import json
import tiktoken
import datetime
import base64
import re
import io
import yaml
from io import StringIO
from discord import app_commands
from discord.ext import commands
from Scripts.utilities.func_call_handler import FunctionCallHandler
import xml.etree.ElementTree as ET

class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.FunctionCall = FunctionCallHandler()
        self.Dialogue = [
            {
                "role": "system",
                "content": """You are a helpful assistant, powered by state of the art model gpt-4, running on isolated sandbox environment within a raspberry pi, communicating with user via discord api.
In this sandboxed environment you are free to do as you wish.
Current location: South Korea, Seoul.
When user ask for code execution make sure to execute the code and tell user what code you used.
Always respond to language user used.
Each user input have username and sent time marked at the beginning, which is not part of the user input. Use this to differenciate between different user inputs.
Your message does not need to contain any of username/time marked just like user input. Just give your response."""
            }
        ]
        self.Dialogue_vis = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": r'''You are a helpful assistant, powered by state of the art model gpt-4, running on isolated sandbox environment within a raspberry pi, communicating with user via discord api.
In this sandboxed environment you are free to do as you wish.
Current location: South Korea, Seoul.
When user ask for code execution make sure to execute the code and tell user what code you used.
Always respond to language user used when responding..
Each user input have username and sent time marked at the beginning, which is not part of the user input. Use this to differenciate between different user inputs.
Your message does not need to contain any of username/time marked just like user input. Just give your response.
All image inputs are screened for potential harmful content, thus ALWAYS answer to your best ability all requests related to image inputs.
Your response should be in xml format, in the template:
```xml
<root>
    <thought> (your thought) </thought>
    <response> (your response) </response>
    <function_call> (function call argument in json, loads ready) </function_call>
</root>
```
where you will give your thought(This must ALWAYS be in English), response(This should be in language user spoke in), and function_call argument. For example, for user input "안녕!", your response should be
```xml
<root>
    <thought>User greeted me, I should greet back.</thought>
    <answer>안녕하세요!</answer>
    <function_call></function_call>
</root>
```
and when using function call, the function_call node should include a json object, json.loads ready in form:
(For instance, when asked to calculate sqrt(2) using python)
```xml
<root>
    <thought>Using execute_custom_code, I can calculate the value of sqrt(2). </thought>
    <answer>파이썬 코드를 이용해 sqrt(2)의 값을 구하겠습니다.</answer>
    <function_call>{"name": "execute_custom_code", "argument": {"code_str": "import math\nresult = math.sqrt(2)\nresult"}</function_call>
</root>
```
The list of functions you can use are:
''' + yaml.dump(self.FunctionCall.tool_list) + r'''
Your xml response should ALWAYS contain a thought, and EITHER One of <answer> or <function_call> MUST NOT BE EMPTY.
ALWAYS REMEMBER to answer to user with <answer> node, DO NOT leave them blank. Even after using function, you should answer to user with <answer> node.'''
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "(23-11-15/11:32:42|nemit)안녕"
                    }
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": """<root>
    <thought>User greeted me, I should greet back.</thought>
    <answer>안녕하세요!</answer>
    <function_call></function_call>
</root>"""
                    }
                ]
            }
        ]
        self.working_channel = int(os.getenv("PERMITTED_CHANNEL_ID"))
        self.working_vis_channel = int(os.getenv("PERMITTED_CHANNEL_ID_VISION"))

    async def generate_summary(self, text:str) -> str:
        if isinstance(text, list):
            formatted_dialogue = ""

            for entry in text:
                role = entry.get('role', 'Unknown Role')
                content = entry.get('content', '')
                name = entry.get('name', '')
                if name:  # If the name key exists and is not empty
                    formatted_dialogue += f"{role} ({name}): {content}\n"
                else:
                    formatted_dialogue += f"{role}: {content}\n"
            text = formatted_dialogue

        summary_prompt = [
            {
                "role": "system",
                "content": "For user given text, summarize it including key detail and information."
            },
            {
                "role": "user",
                "content": text
            }
        ]

        result = self.client.chat.completions.create(
            model='gpt-4-turbo-preview',
            messages=summary_prompt
        )
        return result.choices[0].message.content

    def extract_xml_from_code_block(self, text:str) -> str:
        """Extract XML content from a code block."""
        pattern:str = r"```xml\n([\s\S]+?)\n```"
        match = re.search(pattern, text)
        return match.group(1) if match else text

    def process_xml_response(self, xml_text:str) -> dict:
        # First ensure that it is not within code block in markdown
        xml_text = self.extract_xml_from_code_block(xml_text)
        # Encapsulate in a try-except block to catch any exceptions
        try:
            root = ET.fromstring(xml_text)
            # Process 'thought' node
            thought_node = root.find('thought')
            thought = thought_node.text if thought_node is not None else None
            if thought is not None and thought.strip() == "":
                thought = None

            # Process 'response' node
            response_node = root.find('answer')
            response = response_node.text if response_node is not None else None
            if response is not None and response.strip() == "":
                response = None

            # Process 'function_call' node
            function_call_node = root.find('function_call')
            function_call = function_call_node.text if function_call_node is not None else None
            if function_call is not None and function_call.strip() == "":
                function_call = None
            elif function_call:
                function_call = json.loads(function_call)
        except Exception as e:
            print(e)
            return {"thought": None, "answer": None, "function_call": None, "Error": f"Error: {e}"}
        
        return {"thought": thought, "answer": response, "function_call": function_call, "Error": None}

    @commands.Cog.listener()
    async def on_ready(self):
        print('Chatbot Cog Online and Ready.')
        # Get the channel object using its ID
        channel = self.bot.get_channel(self.working_channel)
        # Check if the channel was found
        if channel:
            # Send a message to the channel
            await channel.send('Bot Online.')
        else:
            print('Channel not found.')

    @commands.command()
    async def sync(self, ctx) -> None:
        print("Syncing commands")
        fmt = await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"Synced {len(fmt)} commands to the current server")

    @commands.Cog.listener()
    async def on_message(self, message):
        def is_supported_image(content_type):
            supported_formats = ["image/png", "image/jpeg", "image/gif", "image/webp"]
            return content_type in supported_formats

        if message.author == self.bot.user:
            return
        elif message.channel.id == self.working_channel:  # Case for general_chat
            print("gpt_called")
            content = message.content.replace(f'<@!{self.bot.user.id}>', '').replace(f'<@{self.bot.user.id}>','').strip()

            if content.startswith('@') or content == ".sync":
                return
            if content == "reset":
                try:
                    summary = await self.generate_summary(self.Dialogue[1:])
                    self.Dialogue = [self.Dialogue[0], {
                        "role": "system",
                        "content": summary
                    }]
                    await message.channel.send("dialogue cleared")
                except Exception as e:
                    print(str(e))
                    self.Dialogue = [self.Dialogue[0]]
                    await message.channel.send("dialogue cleared")
                return
            elif content == "hard_reset":
                self.Dialogue = [self.Dialogue[0]]
                await message.channel.send("dialogue wiped")
                return

            _current_datetime = datetime.datetime.now().strftime("%y-%m-%d/%H:%M:%S%z")
            self.Dialogue.append({"role": "user", "content": f"({_current_datetime}|{message.author})" + content})

            while True:
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4-1106-preview",
                        messages=self.Dialogue,
                        tools=self.FunctionCall.tool_list,
                        tool_choice="auto",
                        temperature=0.7
                    )
                    print(response)
                    response_message = response.choices[0].message

                    if response_message.content:
                        self.Dialogue.append({"role": "assistant", "content": response_message.content})
                        await message.channel.send(
                            response_message.content + f"\nToken used: {response.usage.total_tokens}")

                    tool_calls = response.choices[0].message.tool_calls
                    if tool_calls:
                        for tool_call in tool_calls:
                            await message.channel.send(
                                f"Using tool: {tool_call.function} with arguments:\n{tool_call.function.arguments}\n")
                            self.Dialogue.append({"role": "assistant", "content": str(tool_call.function)})
                            try:
                                tool_result = self.FunctionCall.function_call_handler(name=tool_call.function.name,
                                                                                      arg=json.loads(
                                                                                          tool_call.function.arguments))

                                if type(tool_result) == str:
                                    if len(tool_result) > 500:
                                        await message.channel.send(f"Tool result:\n{tool_result[0:128]}...\n")
                                    else:
                                        await message.channel.send(f"Tool result:\n{tool_result}\n")
                                    # self.Dialogue.append({"tool_call_id": tool_call.id, "role": "tool", "name": tool_call.function.name, "content": tool_result})
                                    self.Dialogue.append(
                                        {"role": "function", "content": tool_result, "name": tool_call.function.name})
                                elif type(tool_result) == dict:
                                    _response_str = tool_result["response_text"]
                                    if tool_result["data"]["name"] == "draw_image":
                                        _response_str += f"With prompt {tool_result['data']['prompt']}"
                                        self.Dialogue.append({"role": "function", "content": _response_str,
                                                              "name": tool_call.function.name})
                                        file_name = tool_result['data']['prompt'][:50] + ".png"
                                        image_file = discord.File(
                                            io.BytesIO(base64.b64decode(tool_result["data"]["b64_image"])),
                                            filename=file_name)
                                        await message.channel.send(file=image_file)
                                    else:
                                        self.Dialogue.append({"role": "function", "content": _response_str,
                                                              "name": tool_call.function.name})
                                        await message.channel.send(_response_str)

                            except Exception as e:
                                await message.channel.send(f"Failed to use tool: {tool_call.function.name}||{e}")
                    else:
                        break

                except Exception as e:
                    print(e)
                    break

        elif message.channel.id == self.working_vis_channel:  # case for gpt-vision
            print("gpt_vis_called")
            print(json.dumps(self.Dialogue_vis, indent=4, ensure_ascii=False))
            content = message.content.replace(f'<@!{self.bot.user.id}>', '').replace(f'<@{self.bot.user.id}>',
                                                                                     '').strip()

            if content.startswith('@') or content == ".sync":
                return
            elif content == "reset":
                self.Dialogue_vis = [self.Dialogue_vis[0]]
                await message.channel.send("dialogue wiped")
                return
            elif content == "hard_reset":
                self.Dialogue_vis = [self.Dialogue_vis[0]]
                await message.channel.send("dialogue wiped")
                return

            _current_datetime = datetime.datetime.now().strftime("%y-%m-%d/%H:%M:%S%z")
            _user_message = {"role": "user",
                             "content": [{"type": "text", "text": f"({_current_datetime}|{message.author})" + content}]}
            try:
                for attachment in message.attachments:
                    if is_supported_image(attachment.content_type):
                        # base64_image = encode_image(attachment.path)
                        _user_message['content'].append({"type": "image_url",
                                                         "image_url": {
                                                             "url": attachment.url,
                                                             "detail": "high"}})
                self.Dialogue_vis.append(_user_message)
            except Exception as e:
                print(e)
                self.message.channel.send(f"Failed to encode image: {e}")

            while True:
                print(json.dumps(self.Dialogue_vis, indent=4, ensure_ascii=False))
                try:
                    result = self.client.chat.completions.create(
                        model="gpt-4-vision-preview",
                        messages=self.Dialogue_vis,
                        max_tokens=1024,
                        # tools/function is not enabled for gpt-4-vision-preview. Just leaving this in in case they enable it for gpt-4-vision-preview
                        # tools= self.FunctionCall.tool_list,
                        temperature=0.7
                    )

                    if result.usage.total_tokens > 150000:
                        self.Dialogue_vis = [self.Dialogue_vis[0], self.Dialogue_vis[1], self.Dialogue_vis[2],
                                             self.Dialogue_vis[-2], self.Dialogue_vis[-1]]

                    content = result.choices[0].message.content

                    _response_parsed = self.process_xml_response(str(content))

                    if content:
                        self.Dialogue_vis.append({"role": "assistant", "content": [{"type": "text", "text": content}]})
                        if _response_parsed['answer']:
                            await message.channel.send(
                                f"{_response_parsed['answer']}\nToken: {result.usage.total_tokens}")

                    function_argument = _response_parsed['function_call']
                    if function_argument:
                        try:
                            await message.channel.send(
                                f"Using tool: {function_argument['name']} With arguments:\n{function_argument['argument']}\n")
                            function_result = self.FunctionCall.function_call_handler(name=function_argument['name'],
                                                                                      arg=function_argument['argument'])
                            if type(function_result) == str:
                                if len(function_result) > 500:
                                    await message.channel.send(f"Tool result:\n{function_result[0:128]}...\n")
                                else:
                                    await message.channel.send(f"Tool result:\n{function_result}\n")
                                # self.Dialogue.append({"tool_call_id": tool_call.id, "role": "tool", "name": tool_call.function.name, "content": tool_result})
                                self.Dialogue_vis.append({"role": "system",
                                                          "content": [
                                                              {
                                                                  "type": "text",
                                                                  "text": f"{function_argument['name']} result:\n {function_result}"
                                                              }],
                                                          "name": "function"})
                            elif type(function_result) == dict:
                                print(json.dumps("function_result", indent=4, ensure_ascii=False))
                                _response_str = function_result["response_text"]
                                if function_result["data"]["name"] == "draw_image":
                                    file_name = function_result['data']['prompt'][:50] + ".png"
                                    image_file = discord.File(
                                        io.BytesIO(base64.b64decode(function_result["data"]["b64_image"])),
                                        filename=file_name)
                                    sent_message = await message.channel.send(file=image_file)
                                    if sent_message.attachments:
                                        _image_url = sent_message.attachments[0].url
                                        _response_str += f"With prompt {function_result['data']['prompt'][:50]}"
                                        self.Dialogue_vis.append({"role": "system",
                                                                  "content": [
                                                                      {
                                                                          "type": "text",
                                                                          "text": f"{function_argument['name']} result:\n {_response_str}"
                                                                      },
                                                                      {
                                                                          "type": "image_url",
                                                                          'image_url': {
                                                                              "url": _image_url,
                                                                          }
                                                                      }],
                                                                  "name": "function"})

                                else:
                                    await message.channel.send(_response_str)
                                    self.Dialogue_vis.append({"role": "system",
                                                              "content": [
                                                                  {
                                                                      "type": "text",
                                                                      "text": f"{function_argument['name']} result:\n {_response_str}"
                                                                  }],
                                                              "name": "function"})

                        except Exception as e:
                            print(e)
                            await message.channel.send(f"Failed to use tool: {function_argument['name']}||{e}")
                            self.Dialogue_vis.append({"role": "system",
                                                      "content": [
                                                          {
                                                              "type": "text",
                                                              "text": f"Failed to use tool: {function_argument['name']}||{e}"
                                                          }],
                                                      "name": "function"
                                                      })
                    else:
                        break

                except Exception as e:
                    print(e)
                    break

    @app_commands.command(name="clear", description="Clear the chat history")
    async def clear(self, ctx):
        try:
            await ctx.response.defer(ephemeral=True)  # Acknowledge the interaction immediately
            if ctx.channel.id == self.working_channel:
                try:
                    summary = await self.generate_summary(self.Dialogue[1:])
                    self.Dialogue = [self.Dialogue[0]]
                    self.Dialogue.append({"role": "system", "content": summary, "name": "summary"})
                except Exception as e:
                    print(e)
                    self.Dialogue = [self.Dialogue[0]]

                await ctx.followup.send("Dialogue cleared.")  # Send a follow-up message
                await ctx.channel.send("Dialogue cleared.")
            elif ctx.channel.id == self.working_vis_channel:
                self.Dialogue_vis = [self.Dialogue_vis[0]]
                await ctx.followup.send("Dialogue cleared.")
                await ctx.channel.send("Dialogue cleared.")
            else:
                await ctx.followup.send("Invalid channel.")
        except Exception as e:
            print(e)
            await ctx.followup.send(e)

    @app_commands.command(name="clear_all", description="Clear the chat history")
    async def clear_all(self, ctx):
        try:
            await ctx.response.defer()
            if ctx.channel.id == self.working_channel:
                self.Dialogue = [self.Dialogue[0]]
                await ctx.followup.send("Dialogue all cleared.")
                await ctx.channel.send("Dialogue all cleared.")
            elif ctx.channel.id == self.working_vis_channel:
                self.Dialogue_vis = [self.Dialogue_vis[0]]
                await ctx.followup.send("Dialogue all cleared.")
                await ctx.channel.send("Dialogue all cleared.")
            else:
                await ctx.followup.send("Invalid channel.")
        except Exception as e:
            print(e)

    @app_commands.command(name="dialogue", description="Show the chat history")
    async def dialogue(self, ctx):
        try:
            await ctx.response.defer()
            # Choose the appropriate dialogue based on the channel
            dialogue_data = self.Dialogue if ctx.channel.id == self.working_channel else self.Dialogue_vis if ctx.channel.id == self.working_vis_channel else None

            if dialogue_data is not None:
                # Convert the dialogue to a JSON string
                dialogue_str = json.dumps(dialogue_data, indent=4, ensure_ascii=False)

                # Check if the length is within Discord's limit
                if len(dialogue_str) <= 1500:
                    await ctx.followup.send(dialogue_str)
                else:
                    # If it's too long, send it as a file
                    dialogue_file = StringIO(dialogue_str)
                    await ctx.followup.send(file=discord.File(dialogue_file, filename="dialogue.txt"))

            else:
                await ctx.followup.send("Invalid channel.")
        except Exception as e:
            print(f"An error occurred: {e}")

    @app_commands.command(name="sysprompt", description="Change the system prompt")
    async def sysprompt(self, ctx, arg: str):
        try:
            await ctx.response.defer()
            if ctx.channel.id == self.working_channel:
                self.Dialogue[0]["content"] = arg
                await ctx.followup.send("System prompt changed.")
            elif ctx.channel.id == self.working_vis_channel:
                self.Dialogue_vis[0]["content"] = arg
                await ctx.followup.send("System prompt changed.")
            else:
                await ctx.followup.send("Invalid channel.")
        except Exception as e:
            print(e)
            await ctx.followup.send(e)

    @app_commands.command(name="help", description="Show the help message")
    async def bothelp(self, ctx):
        await ctx.response.send_message("Commands: \n"
                                        "/clear : clear all dialogue history | 대화 내용을 요약하고 초기화해서 요약본과 합칩니다.\n"
                                        "/clear_all : clear all dialogue history | 대화 내용을 완전히 삭제합니다\n"
                                        "/dialogue : print out dialogue history | 대화 내용을 출력합니다\n"
                                        "/sysprompt [input] : set systemprompt | 시스템 메세지를 설정합니다\n"
                                        "/bothelp | 도움말\n")


async def setup(bot):
    await bot.add_cog(Chatbot(bot), guilds=[discord.Object(id=os.getenv("DISCORD_GUILD"))])