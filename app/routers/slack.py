import logging, os
from pprint import pprint
from typing import Callable

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.async_app import AsyncSay
from slack_sdk import WebClient
from fastapi import APIRouter, Request
from app.utils.gpt import get_similarities, generate_context_array, continue_chat_response, generate_gpt_chat_response
from app.utils.helpers import remove_custom_delimiters, get_dataframe_from_csv
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

router = APIRouter()

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']

# Event API & Web API
app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
app_handler = AsyncSlackRequestHandler(app)
client = WebClient(SLACK_BOT_TOKEN)


async def generate_reply(event, in_thread=True):
    history = []
    # Reply to thread
    thread_ts = event["event_ts"] if event["event_ts"] else None
    if in_thread:
        to_replace = client.chat_postMessage(channel=event["channel"],
                                             thread_ts=event["event_ts"],
                                             text=f"Alfred is thinking :robot_face:")
    else:
        to_replace = client.chat_postMessage(channel=event["channel"],
                                             text=f"Alfred is thinking :robot_face:")

    print("-" * 200)
    print(to_replace['message'])
    print("-" * 200)
    # Extract raw message from the event
    raw_message = str(event["text"])

    # remove any mention tags from the message and sanitize it
    message = remove_custom_delimiters(raw_message).strip()
    print(message)

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
        reply, messages = await continue_chat_response(message, context, [])
    else:
        reply, messages = await generate_gpt_chat_response(message, context)
    print(reply)

    response = client.chat_update(channel=event["channel"],
                                  ts=to_replace['message']['ts'],
                                  text=reply
                                  )
    print(response)
    return reply, messages


@app.middleware
async def log_request(logger: logging.Logger, body: dict, next: Callable):
    print("*" * 100)
    logger.debug(body)
    print("*" * 100)
    return await next()


# This gets activated when the bot is tagged in a channel
@app.event("app_mention")
async def handle_app_mention(body: dict, say: AsyncSay, logger):
    logger.info(body["event"])
    print("app_mention event:")
    event = body["event"]
    pprint(event)
    # Check if the message was made in the main channel (outside thread)
    print("*" * 200)
    print(event.get("thread_ts", None))
    if not event.get("thread_ts", None):
        thread_ts = event.get("thread_ts", None) or event["ts"]
        history = []
        response, messages = await generate_reply(event)
        # await say(text=f"{response}", thread_ts=thread_ts)


@app.event({"type": "message"})
async def handle_message(body, say, logger):
    # Log message
    print(body["event"]["text"])
    event = body["event"]
    pprint(event)
    thread_ts = event.get("thread_ts", None)
    # if message was a direct message to Alfred bot
    if event["channel_type"] == "im":
        print("handle_bot_message event:")
        response, messages = await generate_reply(event, bool(thread_ts))
        # await say(text=f"{response}", thread_ts=thread_ts)
    # if the message was made inside a thread (excluding inside the Alfred messaging chat)
    elif thread_ts:
        print("handle_message_in_thread event:")
        # extract message from event
        response, messages = await generate_reply(event)
        # await say(text=f"{response}", thread_ts=thread_ts)
    else:
        return


@app.command("/greet")
async def command(ack, body):
    user_id = body["user_id"]
    await ack(text=f"Hi <@{user_id}>! How can I help you?")


@router.post("/events")
async def endpoint(req: Request):
    return await app_handler.handle(req)
