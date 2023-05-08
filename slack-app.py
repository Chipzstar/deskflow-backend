import os
import logging
from typing import Callable

logging.basicConfig(level=logging.INFO)

from slack_bolt.async_app import AsyncApp, AsyncSay
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.utils.gpt import get_similarities, generate_context_array, continue_chat_response, generate_gpt_chat_response
from app.utils.helpers import get_dataframe_from_csv
from app.utils.types import ChatPayload

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']

from slack_sdk import WebClient
from fastapi import FastAPI, Request

# Event API & Web API
app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
app_handler = AsyncSlackRequestHandler(app)
client = WebClient(SLACK_BOT_TOKEN)


@app.middleware
async def log_request(logger: logging.Logger, body: dict, next: Callable):
    print("*" * 100)
    logger.debug(body)
    print("*" * 100)
    return await next()


# This gets activated when the bot is tagged in a channel
@app.event("app_mention")
async def handle_app_mention(body: dict, say: AsyncSay, logger):
    # logger.info(body)
    logger.info(body["event"]["text"])

    print("app_mention event:")
    event = body["event"]
    print(event)
    thread_ts = event.get("thread_ts", None) or event["ts"]
    history = []
    # Check if the message is a command
    print(str(body["event"]["text"]).split(">")[1])

    # Reply to thread
    response = client.chat_postMessage(channel=body["event"]["channel"],
                                       thread_ts=body["event"]["event_ts"],
                                       text=f"Alfred is thinking :robot_face:")

    # Extract message from mention tag and strip out all whitespaces
    message = str(body["event"]["text"]).split(">")[1].strip()

    # download knowledge base embeddings from csv
    knowledge_base = get_dataframe_from_csv(f"{os.getcwd()}/app/data", "zendesk_vector_embeddings.csv")
    # create query embedding and fetch relatedness between query and knowledge base in dataframe
    similarities = await get_similarities(message, knowledge_base)
    # Combine all top n answers into one chunk of text to use as knowledge base context for GPT
    context = generate_context_array(similarities)
    print(context.split("\n"))
    print("-" * 50)
    # check if the query is the first question of the conversation
    if len(history):
        response, messages = await continue_chat_response(message, context, [])
    else:
        response, messages = await generate_gpt_chat_response(message, context)
    print(response)

    await say(text=f"{response}", thread_ts=thread_ts)


# @app.event({"type": "message", "subtype": None})
# async def reply_in_thread(body: dict, say: AsyncSay):
#     print("Reply in thread function called:")
#     event = body["event"]
#     print(event)
#     thread_ts = event.get("thread_ts", None) or event["ts"]
#
#     message = str(body["event"]["text"])
#
#     await say(text=f"Hello from Alfred! :robot_face: \nYour message was: \n{message}", thread_ts=thread_ts)


@app.event("message")
async def handle_message_direct(body, say, logger):
    # Log message
    logger.info(body["event"])
    logger.info(body["event"]["text"])

    # Create prompt for ChatGPT
    message = str(body["event"]["text"])

    say(f"Hello from Alfred! :robot_face: \nYour message was: \n{message}")


@app.command("/greet")
async def command(ack, body):
    user_id = body["user_id"]
    await ack(text=f"Hi <@{user_id}>! How can I help you?")


api = FastAPI()


@api.post("/slack/events")
async def endpoint(req: Request):
    return await app_handler.handle(req)
