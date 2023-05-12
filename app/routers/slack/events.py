import logging, os
from pprint import pprint
from typing import Callable, List, Dict

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.async_app import AsyncSay
from slack_sdk import WebClient
from fastapi import APIRouter, Request
from app.utils.gpt import get_similarities, generate_context_array, continue_chat_response, generate_gpt_chat_response
from app.utils.helpers import remove_custom_delimiters, get_dataframe_from_csv
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from app.utils.slack import display_support_dialog, get_user_from_event

router = APIRouter()

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']

# Event API & Web API
app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
app_handler = AsyncSlackRequestHandler(app)
client = WebClient(SLACK_BOT_TOKEN)


async def check_reply_requires_action(reply: str, messages: List[Dict[str, str]]):
    is_knowledge_gap = "information is not provided within the company’s knowledge base"
    is_zendesk_ticket = "create a ticket on Zendesk"
    is_contact_support = "ask HR/IT"
    hints = [is_knowledge_gap, is_zendesk_ticket, is_contact_support]
    if (is_zendesk_ticket.lower() in reply.lower()) or (is_contact_support.lower() in reply.lower()):
        return True
    else:
        return False


async def generate_reply(event, in_thread=True):
    history = []
    # initially return a message that Alfred is thinking and store metadata for that message
    thread_ts = event["event_ts"] if event["event_ts"] else None
    if in_thread:
        to_replace = client.chat_postMessage(channel=event["channel"],
                                             thread_ts=event["event_ts"],
                                             text=f"Alfred is thinking :robot_face:")
    else:
        to_replace = client.chat_postMessage(channel=event["channel"],
                                             text=f"Alfred is thinking :robot_face:")

    sender_name = await get_user_from_event(event, client)

    # Extract raw message from the event
    raw_message = str(event["text"])

    # remove any mention tags from the message and sanitize it
    message = remove_custom_delimiters(raw_message).strip()
    print(f"\nMESSAGE:\t {message}")
    # download knowledge base embeddings from csv
    knowledge_base = get_dataframe_from_csv(f"{os.getcwd()}/app/data", "zendesk_vector_embeddings.csv")
    # create query embedding and fetch relatedness between query and knowledge base in dataframe
    similarities = await get_similarities(message, knowledge_base)
    # Combine all top n answers into one chunk of text to use as knowledge base context for GPT
    context = generate_context_array(similarities)
    # check if the query is the first question of the conversation
    if len(history):
        reply, messages = await continue_chat_response(message, context, [])
    else:
        reply, messages = await generate_gpt_chat_response(message, context, sender_name)
    print(f"\nREPLY: {reply}")

    response = client.chat_update(channel=event["channel"],
                                  ts=to_replace['message']['ts'],
                                  text=reply
                                  )
    return reply, response.data


async def check_bot_mentioned_in_thread(channel: str, thread_ts: str):
    response = client.conversations_replies(channel=channel, ts=thread_ts, inclusive=True)
    bot_info = client.auth_test(token=SLACK_BOT_TOKEN)
    bot_user_id = bot_info["user_id"]
    for message in response.data['messages']:
        # Check if the message was authored by the Slack bot or contains a mention of the bot user ID
        # check if any message contains the bot user id
        if 'bot_id' in message and message['bot_id'] == bot_user_id:
            return True
        elif 'text' in message and f"<@{bot_user_id}>" in message['text']:
            return True
        elif 'user' in message and message["user"] == bot_user_id:
            return True
    return False


@app.middleware
async def log_request(logger: logging.Logger, body: dict, next: Callable):
    # print("*" * 100)
    # logger.debug(body)
    # print("*" * 100)
    return await next()


# This gets activated when the bot is tagged in a channel
@app.event("app_mention")
async def handle_app_mention(body: dict, say: AsyncSay, logger):
    logger.info(body["event"])
    print("app_mention event:")
    event = body["event"]
    pprint(event)
    # Check if the message was made in the main channel (outside thread)
    print(event.get("thread_ts", None))
    if not event.get("thread_ts", None):
        thread_ts = event.get("thread_ts", None) or event["ts"]
        history = []
        reply, response = await generate_reply(event)
        # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on zendesk
        # OR to contact someone from HR/IT
        take_action = await check_reply_requires_action(reply, [])
        if take_action:
            await display_support_dialog(client, response)


@app.event({"type": "message", "subtype": "file_share"})
async def handle_file_share(body, say: AsyncSay, logger):
    event = body["event"]
    pprint(event)
    thread_ts = event.get("thread_ts", None)
    # ERROR handling
    # check if a file was uploaded in the event, and respond with an error
    if "files" in event and len(event["files"]) > 0:
        await say(
            text="Sorry, I can't process that file. Please type out your question and I will try to answer it. 🙂",
            thread_ts=event["event_ts"]
        )
    # if raw_message is empty, return an error message
    elif not str(event["text"]):
        await say(text="Sorry, I didn't get that. Please try again.", thread_ts=event["event_ts"])


@app.event({"type": "message"})
async def handle_message(body, say, logger):
    # Log message
    event = body["event"]
    pprint(event)
    thread_ts = event.get("thread_ts", None)
    # USE CASE 1: Message sent directly to Alfred bot via the message tab
    if event["channel_type"] == "im":
        print("handle_bot_message event:")
        reply, response = await generate_reply(event, bool(thread_ts))
        # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on zendesk
        # OR to contact someone from HR/IT
        take_action = await check_reply_requires_action(reply, [])
        if take_action:
            await display_support_dialog(client, response)

    # USE CASE 2: Message was sent inside a thread where the initial message tagged Alfred
    # if the message was made inside a thread (excluding inside the Alfred messaging chat)
    elif thread_ts:
        print("handle_message_in_thread event:")
        # check for any messages in thread history where Alfred was tagged
        is_mentioned = await check_bot_mentioned_in_thread(event['channel'], thread_ts)
        if is_mentioned:
            # extract message from event
            reply, response = await generate_reply(event)
            # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on
            # zendesk OR to contact someone from HR/IT
            take_action = await check_reply_requires_action(reply, [])
            if take_action:
                await display_support_dialog(client, response)
        else:
            logger.info(f"No bot mention not found in thread: {thread_ts}")
    else:
        return


@app.command("/greet")
async def command(ack, body):
    user_id = body["user_id"]
    await ack(text=f"Hi <@{user_id}>! How can I help you?")


@router.post("/events")
async def endpoint(req: Request):
    return await app_handler.handle(req)
