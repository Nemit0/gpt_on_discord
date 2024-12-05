import requests
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

def youtube_search(api_key:str, keyword:str, max_results:int=25) -> tuple[list[str]]:
    youtube = build('youtube', 'v3', developerKey=api_key)

    try:
        # Perform the search
        search_response = youtube.search().list(
            q=keyword,
            part='id,snippet',
            maxResults=max_results
        ).execute()

        videos = []
        channels = []
        playlists = []

        # Iterate through the search results
        for search_result in search_response.get('items', []):
            if search_result['id']['kind'] == 'youtube#video':
                videos.append((search_result['snippet']['title'], search_result['id']['videoId']))
            elif search_result['id']['kind'] == 'youtube#channel':
                channels.append((search_result['snippet']['title'], search_result['id']['channelId']))
            elif search_result['id']['kind'] == 'youtube#playlist':
                playlists.append((search_result['snippet']['title'], search_result['id']['playlistId']))

        return videos, channels, playlists

    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred:\n{e.content}")
        return [], [], []

def preprocess_serpapi_results(results: dict) -> dict:
    if 'search_metadata' in results:
        results.pop('search_metadata', None)
    if "pagination" in results:
        results.pop('pagination', None)
    if "serpapi_pagination" in results:
        results.pop('serpapi_pagination', None)
    

    # Process the answer_box if it exists
    if 'answer_box' in results:
        if results['answer_box']['type'] == 'weather_result':
            keys_to_delete = ['thumbnail', 'hourly_forecast', 'precipitation_forecast', 'wind_forecast']
            for key in keys_to_delete:
                results['answer_box'].pop(key, None)
            for item in results['answer_box']['forecast']:
                item.pop('thumbnail', None)

        if results['answer_box']['type'] == 'air_quality':
            results['answer_box'].pop('indexes', None)
    if 'related_questions' in results:
        for item in results['related_questions']:
            keys_to_delete = ['next_page_token', 'serpapi_link']
            for key in keys_to_delete:
                item.pop(key, None)
    # Process knowledge_graph if it exists
    if 'knowledge_graph' in results and 'description' in results['knowledge_graph']:
        results['knowledge_graph_description'] = results['knowledge_graph']['description']

    # Process organic_results if it exists
    if 'organic_results' in results:
        top5_results = results['organic_results'][:5]
        for item in top5_results:
            keys_to_delete = [
                'displayed_link', 'thumbnail', 'favicon', 'snippet_highlighted_words',
                'sitelinks', 'about_this_result', 'about_page_link', 'about_page_serpapi_link',
                'related_pages_link', 'cached_page_link'
            ]
            for key in keys_to_delete:
                item.pop(key, None)

        results['organic_results_top5'] = top5_results

    # Process top_stories if it exists
    if 'top_stories' in results:
        for item in results['top_stories']:
            item.pop('thumbnail', None)

    # Process news_results if it exists
    if 'news_results' in results:
        for item in results['news_results']:
            item.pop('thumbnail', None)

    # Process people_also_search_for if it exists
    if 'people_also_search_for' in results:
        for block in results['people_also_search_for']:
            if 'news_results' in block and isinstance(block['news_results'], list):
                for item in block['news_results']:
                    item.pop('thumbnail', None)

    if "related_searches" in results:
        for item in results['related_searches']:
            item.pop('serpapi_link', None)

    return results

def get_city_coordinates(city_name:str="Seoul", user_agent:str="MyUniqueProjectGeocoder") -> tuple[float]:
    """
    Returns the coordinates (latitude, longitude) of a given city name.

    Args:
    - city_name (str): The name of the city for which to find coordinates.
    - user_agent (str): A unique identifier for the geocode request, to avoid being blocked.

    Returns:
    - tuple: A tuple containing the latitude and longitude of the city, or None if not found.
    """
    # Initialize the Nominatim geocoder with a unique user-agent
    geolocator = Nominatim(user_agent=user_agent)

    try:
        # Attempt to geocode the given city name
        location = geolocator.geocode(city_name)
        if location:
            return (location.latitude, location.longitude)
        else:
            return None
    except GeocoderTimedOut:
        return None

def get_weather(coordinate:tuple[float], state:str) -> dict:
    current_weather_arg_list:frozenset = frozenset(["temperature_2m", "relative_humidity_2m", "apparent_temperature", "is_day", "precipitation", "rain", "showers", "snowfall", "cloud_cover", "pressure_msl"])
    forecast_weather_arg_list:frozenset = frozenset(["temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation_probability", "precipitation", "rain", "showers", "snowfall", "snow_depth", "cloud_cover", "visibility", "wind_speed_10m", "wind_speed_80m", "wind_direction_10m", "wind_direction_80m", "uv_index", "is_day"])
    base_url:str = "https://api.open-meteo.com/v1/forecast?"
    latitude, longitude = coordinate
    if state == "current":
        request_url = f"{base_url}latitude={latitude}&longitude={longitude}&current={','.join(current_weather_arg_list)}"
    elif state == "forecast":
        request_url = f"{base_url}latitude={latitude}&longitude={longitude}&hourly={','.join(forecast_weather_arg_list)}"
    else:
        raise ValueError("Invalid state, must be either 'current' or 'forecast'")
    response = requests.get(request_url)
    return response.json()['hourly'] if state == "forecast" else response.json()

def convert_to_dataframe(data:dict) -> pd.DataFrame:
    _dataframe:pd.DataFrame = pd.DataFrame(data)
    _dataframe.set_index('time', inplace=True)
    return _dataframe

def summarize_weather(data:pd.DataFrame, return_days:int = 3) -> dict:
    """
    Write a summary for each day in the weather data.
    """
    # This function will give: max temp, min temp, avg temp, avg humidity, avg precipitation, avg cloud cover, avg wind speed
    # For each day in the data
    summary:dict = {}
    # Make sure the data index is a datetime object
    data.index = pd.to_datetime(data.index)
    # Group the data by day
    grouped = data.groupby(data.index.date)
    for day, day_data in grouped:
        summary[day] = {
            "max_temp": day_data['temperature_2m'].max(),
            "min_temp": day_data['temperature_2m'].min(),
            "avg_temp": day_data['temperature_2m'].mean(),
            "avg_humidity": day_data['relative_humidity_2m'].mean(),
            "avg_precipitation": day_data['precipitation'].mean(),
            "avg_cloud_cover": day_data['cloud_cover'].mean(),
            "avg_wind_speed": day_data['wind_speed_10m'].mean()
        }
    # round all values to 2 decimal places
    for day, day_summary in summary.items():
        for key, value in day_summary.items():
            summary[day][key] = round(value, 2)
    return {str(k): v for k, v in summary.items() if (k <= pd.Timestamp.now().date() + pd.Timedelta(days=return_days)) and (k > pd.Timestamp.now().date())}

def concat_current_weather(weather:dict) -> dict:
    """
    Concatenate the current weather data into the forecast data.
    """
    current_units = weather["current_units"]
    current = weather["current"]
    new_current = {'/'.join([str(k), str(v)]) : current[k] for k, v in current_units.items()}
    return new_current
