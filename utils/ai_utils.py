import os
import aiohttp
import io
import time
import random
import json
import urllib.parse
try:
    from langdetect import detect
except ImportError:
    def detect(text):
        return "en"

try:
    from gtts import gTTS
except ImportError:
    gTTS = None
from urllib.parse import quote
from utils.config_loader import load_current_language, config
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None
try:
    from duckduckgo_search import AsyncDDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS as AsyncDDGS
    except Exception:
        AsyncDDGS = None
from dotenv import load_dotenv

load_dotenv()

current_language = load_current_language()
internet_access = config['INTERNET_ACCESS']

client = AsyncOpenAI(
    base_url=config['API_BASE_URL'],
    api_key="nah-ha",
)

async def generate_response(instructions, history):
    messages = [
            {"role": "system", "name": "instructions", "content": instructions},
            *history,
        ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "searchtool",
                "description": "Searches the internet.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query for search engine",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]
    response = await client.chat.completions.create(
        model=config['MODEL_ID'],
        messages=messages,        
        tools=tools,
        tool_choice="auto",
    )
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        available_functions = {
            "searchtool": duckduckgotool,
        }
        messages.append(response_message)

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            function_response = await function_to_call(
                query=function_args.get("query")
            )
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            )
        second_response = await client.chat.completions.create(
            model=config['MODEL_ID'],
            messages=messages
        ) 
        return second_response.choices[0].message.content
    return response_message.content

async def duckduckgotool(query) -> str:
    if config['INTERNET_ACCESS']:
        return "internet access has been disabled by user"
    blob = ''
    results = await AsyncDDGS(proxy=None).text(query, max_results=6)
    try:
        for index, result in enumerate(results[:6]):  # Limiting to 6 results
            blob += f'[{index}] Title : {result["title"]}\nSnippet : {result["body"]}\n\n\n Provide a cohesive response base on provided Search results'
    except Exception as e:
        blob += f"Search error: {e}\n"
    return blob


def get_pollinations_api_keys():
    keys = []
    # 1. From environment variable POLLINATIONS_API_KEY (highest priority)
    env_key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    if env_key:
        for k in env_key.split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    # 2. From config.yml POLLINATIONS_API_KEYS (list)
    conf_keys = config.get("POLLINATIONS_API_KEYS")
    if isinstance(conf_keys, list):
        for k in conf_keys:
            if k and str(k).strip():
                clean_k = str(k).strip()
                if clean_k not in keys:
                    keys.append(clean_k)
    # 3. From config.yml POLLINATIONS_API_KEY (string or list)
    conf_single = config.get("POLLINATIONS_API_KEY")
    if isinstance(conf_single, list):
        for k in conf_single:
            if k and str(k).strip():
                clean_k = str(k).strip()
                if clean_k not in keys:
                    keys.append(clean_k)
    elif conf_single and str(conf_single).strip():
        clean_k = str(conf_single).strip()
        if clean_k not in keys:
            keys.append(clean_k)
    return keys


async def poly_image_gen(session: aiohttp.ClientSession, prompt: str) -> io.BytesIO:
    clean_prompt = urllib.parse.unquote(str(prompt)).strip()
    encoded_prompt = urllib.parse.quote(clean_prompt)
    api_keys = get_pollinations_api_keys()

    # Rotate keys to balance quota across multiple keys
    if len(api_keys) > 1:
        random.shuffle(api_keys)

    base_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    timeout = aiohttp.ClientTimeout(total=35, connect=10)
    last_error = None

    # Try authenticated keys first with rotation & automatic failover
    for api_key in api_keys:
        headers = dict(base_headers)
        headers["Authorization"] = f"Bearer {api_key}"
        urls = [
            f"https://gen.pollinations.ai/image/{encoded_prompt}",
            f"https://image.pollinations.ai/prompt/{encoded_prompt}?key={api_key}"
        ]
        for url in urls:
            try:
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status == 402:
                        last_error = f"Key {api_key[:8]}... returned 402 Payment Required"
                        break  # Move to next key
                    if response.status != 200:
                        last_error = f"HTTP {response.status}: {response.reason}"
                        continue
                    data = await response.read()
                    if len(data) < 1000:
                        last_error = f"Received incomplete image data ({len(data)} bytes)"
                        continue
                    if not (data.startswith(b"\xff\xd8") or data.startswith(b"\x89PNG") or data.startswith(b"RIFF")):
                        last_error = "Invalid image format returned"
                        continue
                    img_io = io.BytesIO(data)
                    img_io.seek(0)
                    return img_io
            except Exception as e:
                last_error = str(e)
                continue

    # Fallback to public unauthenticated endpoints if no keys or all keys exhausted
    public_urls = [
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?nofeed=true",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}",
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=turbo"
    ]
    for url in public_urls:
        try:
            async with session.get(url, headers=base_headers, timeout=timeout) as response:
                if response.status == 402:
                    raise ValueError("Daily image generation free limit reached.")
                if response.status != 200:
                    last_error = f"HTTP {response.status}: {response.reason}"
                    continue
                data = await response.read()
                if len(data) < 1000:
                    last_error = f"Received incomplete image data ({len(data)} bytes)"
                    continue
                if not (data.startswith(b"\xff\xd8") or data.startswith(b"\x89PNG") or data.startswith(b"RIFF")):
                    last_error = "Invalid image format returned"
                    continue
                img_io = io.BytesIO(data)
                img_io.seek(0)
                return img_io
        except ValueError:
            raise
        except Exception as e:
            last_error = str(e)
            continue

    err_text = last_error or "All image generation endpoints failed"
    raise RuntimeError(f"Failed to generate image: {err_text}")

async def generate_image_prodia(prompt, model, sampler, seed, neg):
    print("\033[1;32m(Prodia) Creating image for :\033[0m", prompt)
    start_time = time.time()
    async def create_job(prompt, model, sampler, seed, neg):
        url = 'https://api.prodia.com/generate'
        params = {
            'new': 'true',
            'prompt': f'{quote(prompt)}',
            'model': model,
            'steps': '100',
            'cfg': '9.5',
            'seed': f'{seed}',
            'sampler': sampler,
            'upscale': 'True',
            'aspect_ratio': 'square'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return data['job']

    job_id = await create_job(prompt, model, sampler, seed, neg)
    url = f'https://api.prodia.com/job/{job_id}'
    headers = {
        'authority': 'api.prodia.com',
        'accept': '*/*',
    }

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(url, headers=headers) as response:
                json = await response.json()
                if json['status'] == 'succeeded':
                    async with session.get(f'https://images.prodia.xyz/{job_id}.png?download=1', headers=headers) as response:
                        content = await response.content.read()
                        img_file_obj = io.BytesIO(content)
                        duration = time.time() - start_time
                        print(f"\033[1;34m(Prodia) Finished image creation\n\033[0mJob id : {job_id}  Prompt : ", prompt, "in", duration, "seconds.")
                        return img_file_obj

async def text_to_speech(text):
    bytes_obj = io.BytesIO()
    detected_language = detect(text)
    tts = gTTS(text=text, lang=detected_language)
    tts.write_to_fp(bytes_obj)
    bytes_obj.seek(0)
    return bytes_obj