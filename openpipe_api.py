# openpipe_api.py
import asyncio
import re
from openpipe import OpenAI
from config import OPENPIPE_API_KEY, OPENPIPE_API_KEY_EXPENSIVE, logger
from helpers import is_refusal

client_openpipe = OpenAI(
    openpipe={"api_key": OPENPIPE_API_KEY}
)

client_openpipe_expensive = OpenAI(
    openpipe={"api_key": OPENPIPE_API_KEY_EXPENSIVE}
)

async def get_valid_response(messages, tags, initial_temperature=0.1777, decrement=0.05, min_temperature=0.05, max_retries=3, use_expensive_model=False):
    temperature = initial_temperature
    retries = 0
    last_response = None

    client = client_openpipe_expensive if use_expensive_model else client_openpipe

    while retries < max_retries and temperature >= min_temperature:
        try:
            loop = asyncio.get_event_loop()
            completion = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="openpipe:CSRv2" if use_expensive_model else "openpipe:Sydney-Court",
                    messages=messages,
                    temperature=temperature,
                    openpipe={
                        "tags": tags,
                        "log_request": True
                    }
                )
            )
            response = completion.choices[0].message.content.strip()
            last_response = response
            if not is_refusal(response):
                return response
            logger.warning(f"Refusal detected at temperature {temperature}. Retrying...")
            retries += 1
            temperature -= decrement
            if not use_expensive_model:
                logger.info("Switching to the expensive model due to refusal.")
                use_expensive_model = True
                client = client_openpipe_expensive
        except Exception as e:
            logger.error(f"Error during API call: {e}", exc_info=True)
            break

    if last_response:
        logger.warning("Max retries reached or refusal detected. Returning the last response.")
        return last_response
    else:
        return "I'm sorry, I couldn't process your request at this time."

async def get_reaction_response(messages, initial_temperature=0.7, max_retries=3):
    temperature = initial_temperature
    retries = 0
    last_response = None

    client = client_openpipe  # Use the regular client for reactions

    while retries < max_retries:
        try:
            loop = asyncio.get_event_loop()
            completion = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="openpipe:Sydney-Court",
                    messages=messages,
                    temperature=temperature
                )
            )
            response = completion.choices[0].message.content.strip()
            last_response = response
            if re.match(r'^[^\w\s]{1,2}$', response):
                return response
            else:
                logger.warning(f"Invalid reaction received: {response}. Retrying...")
                retries += 1
                temperature += 0.1
        except Exception as e:
            logger.error(f"Error during reaction API call: {e}", exc_info=True)
            return None

    logger.warning("Max retries reached. No valid reaction obtained.")
    return None