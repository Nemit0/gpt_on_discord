import os
import subprocess
import requests
import yaml
import json
import tiktoken
from openai import OpenAI
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from IPython.core.interactiveshell import InteractiveShell

from Scripts.utilities.func_call_logics import *

class FunctionCallHandler(object):
    def __init__(self):
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        self.shell = InteractiveShell.instance()
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.tool_list = [
            {
                "type": "function",
                "function": {
                    "name": "search_online",
                    "description": "Search on web the search_keyword, used for when user ask something that you do not know. The function will return an answer for the question that you passed on with the search_keyword, to save token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search_keyword": {
                                "type": "string",
                                "description": "string to search"
                            },
                            "question": {
                                "type": "string",
                                "description": "Question to ask regarding the search result"
                            }
                        },
                        "required": ["search_keyword", "question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_custom_code",
                    "description": "Executes a custom Python code. Can be used with random to answer absurd request such as fortune telling. This is run via Ipython with Ipython.cord.interactiveshell InteractiveShell with store_history=True.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code_str": {
                                "type": "string",
                                "description": "Python code string to execute"
                            }
                        },
                        "required": ["code_str"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_shell_command",
                    "description": "Execute a shell command. When making or modifying a file the task might be done successfully but have no result, therefore you should recheck to print out modified content or file list to check if the task is successful.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "script": {
                                "type": "string",
                                "description": "Shell script to run"
                            }
                        },
                        "required": ["script"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Retrieve weather data from location using OpenMetro.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "Location to retrieve information from. Example query: New York"
                            },
                            "state": {
                                "type": "string",
                                "description": "State of the weather data to retrieve. Must be either 'current' or 'forecast'. Default to 'current'"
                            }
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "youtube_transcript",
                    "description": "Get transcript of YouTube video. If it's too long it's summarized.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Video ID to get transcript from. May not give anything if there's none."
                            }
                        },
                        "required": ["id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "crawl_from_url",
                    "description": "Get text and content from a given url, this will be summarized via gpt model within context of question",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to get content from."
                            },
                            "question": {
                                "type": "string",
                                "description": "question, or context necessary to summarize the content"
                            },
                        },
                        "required": ["url", "question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "draw_image",
                    "description": "Generate image using dall-e model",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "Prompt to generate image from. If the request is not in English ALWAYS translate it to English, and ALWAYS mention image type(photo, oil/watercolor painting, illustration, cartoon, vector, etc.)\n ALWAYS enrich user's request to be more lengthy and detailed."
                            },
                            "size": {
                                "type": "string",
                                "description": "size of generated image, must be one of 1024x1024, 1792x1024, or 1024x1792. default to 1024x1024"
                            },
                            "style": {
                                "type": "string",
                                "description": "style of the generated images. Must be one of vivid or natrual. Default to vivid"
                            }
                        },
                        "required": ["prompt"]
                    }
                }
            }
        ]

    def execute_shell_command(self, script):
        """
        Uses subprocess module to execute a shell command and return the output.
        """
        result = subprocess.run(script, shell=True, capture_output=True, text=True)
        return str(result)

    def get_weather(self, location:str, state:str="current") -> str:
        coordinate = get_city_coordinates(location)
        if state == "current":
            weather = get_weather(coordinate, state)
            weather = concat_current_weather(weather)
            return json.dumps(weather, ensure_ascii=False)
        elif state == "forecast":
            weather = get_weather(coordinate, state)
            weather = convert_to_dataframe(weather)
            summary = summarize_weather(weather)
            return json.dumps(summary, ensure_ascii=False)
        else:
            raise ValueError("Invalid state, must be either 'current' or 'forecast'")


    def youtube_transcript(self, id):
        try:
            language_list = ['en', 'ko', 'jp', 'zh-Hans', 'zh-Hant', 'fr', 'es', 'ru', 'de', 'pt', 'it', 'ar', 'tr', ]
            transcript = YouTubeTranscriptApi.get_transcript(id, languages=language_list)
            _concat_str = ''.join([element['text'] for element in transcript])

            vid_token_count = len(self.encoder.encode(_concat_str))
            if vid_token_count < 30000:
                return _concat_str
            elif (vid_token_count >= 300000) and (vid_token_count < 60000):
                # Summarize video using gpt-4-turbo-preview model
                _summary_dialogue = [
                    {
                        "role": "system",
                        "content": "Instruction: summarize the video transcript given from user, including key information and details"
                    },
                    {
                        "role": "user",
                        "content": _concat_str
                    }
                ]
                response = self.openai_client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=_summary_dialogue
                )
                summary = response.choices[0].message.content
                return summary
            else:
                return "Video is too long to parse"
        except Exception as e:
            return f"Unable to get transcript: {str(e)}"

    def search_online(self, search_keyword, question):

        # SerpAPI endpoint
        serpapi_endpoint = "https://serpapi.com/search"
        serpapi_key = os.getenv("SERPAPI_API_KEY")

        # Parameters for SerpAPI
        serpapi_params = {
            "q": search_keyword,
            "api_key": serpapi_key,
            "engine": "google",
            "location": "Seoul, South Korea",
        }

        # Make the request to SerpAPI
        response = requests.get(serpapi_endpoint, params=serpapi_params)
        serpapi_results = response.json()

        # Process the SerpAPI results (optional preprocessing step)
        processed_results = yaml.dump(preprocess_serpapi_results(serpapi_results), allow_unicode=True,
                                      default_flow_style=False, sort_keys=False)

        # Prepare the prompt for GPT
        prompt = f"Based on the following search results for the query '{search_keyword}':\n{processed_results}\n\nAnswer the question: {question}.\nALWAYS Annotate your response with proper url in markdown format."

        # Make the request to OpenAI GPT using chat.completions.create
        gpt_response = self.openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "system", "content": prompt}]
        )

        # Extracting and returning the answer from the response
        answer = gpt_response.choices[0].message.content
        return answer

    def execute_custom_code(self, code_str):
        """
        Function to execute custom python code on the csv data.
        """
        execution_result = self.shell.run_cell(code_str, store_history=True)
        if execution_result.error_in_exec is not None:
            print(execution_result.error_in_exec)
            return str(execution_result.error_in_exec)

        result = execution_result.result  # Access the result attribute of the ExecutionResult object
        # Return the result along with the execution count
        return f"Out[{execution_result.execution_count}]: {result}"

    def execute_shell_command(self, script:str) -> str:
        """
        Uses subprocess module to execute a shell command and return the output.
        """
        result = subprocess.run(script, shell=True, capture_output=True, text=True)
        return str(result)

    def crawl_from_url(self, url, question):
        # # Set up Selenium WebDriver
        # options = webdriver.ChromeOptions()
        # options.headless = True  # Run in headless mode
        # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        try:
            # Send a GET request to the URL
            response = requests.get(url)
            # Check if the request was successful
            if response.status_code != 200:
                return f"Error fetching the page: Status code {response.status_code}"
            # Parse the content of the page using BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract all text from the page
            text = soup.get_text()
            # Optional: Clean up the text by removing extra spaces, newlines, etc.
            text = ' '.join(text.split())

            # driver.get(url)
            # time.sleep(5)  # Wait for JavaScript content to load

            # # Parse the page source with BeautifulSoup
            # soup = BeautifulSoup(driver.page_source, 'html.parser')

            # # Example: Extract text from a specific element, e.g., article tag
            # article = soup.find('article')
            # text = article.get_text() if article else soup.get_text()

            # text = ' '.join(text.split())  # Clean up the text

            _summary_dialogue = [
                {
                    "role": "system",
                    "content": f"Instruction: summarize the content from url given from user, including key information and details within the context:{question}"
                },
                {
                    "role": "user",
                    "content": text
                }
            ]

            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=_summary_dialogue
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"An error occurred: {e}"

        # finally:
        #     driver.quit()

    def draw_image(self, prompt, size="1024x1024", style="vivid"):
        image = self.openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=size,
            style=style,
            response_format= "b64_json"
        )
        return {"response_text": "Image sucessfully created and is being displayed to user.", "data": { "name": "draw_image", "prompt": image.data[0].revised_prompt[:200], "b64_image": image.data[0].b64_json}}

    def function_call_handler(self, name, arg):
        if name == "search_online":
            return self.search_online(**arg)
        elif name == "execute_custom_code":
            return self.execute_custom_code(**arg)
        elif name == "execute_shell_command":
            return self.execute_shell_command(**arg)
        elif name == "get_weather":
            return self.get_weather(**arg)
        elif name == "youtube_transcript":
            return self.youtube_transcript(**arg)
        elif name == "crawl_from_url":
            return self.crawl_from_url(**arg)
        elif name == "draw_image":
            return self.draw_image(**arg)
        else:
            return f"Function {name} not found."
        
if __name__ == '__main__':
    client = FunctionCallHandler()
    # test get weather function with argument {"location":"Seoul"}
    print(client.function_call_handler("get_weather", {"location":"Seoul", "state":"forecast"}))