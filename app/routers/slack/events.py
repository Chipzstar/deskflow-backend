import json
import logging, os
from pprint import pprint
from typing import Callable, Literal

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.async_app import AsyncSay
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings
from slack_sdk import WebClient
from fastapi import APIRouter, Request
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore

from app.redis.client import Redis
from app.utils.gpt import get_similarities, generate_context_array, continue_chat_response, generate_gpt_chat_response, \
    send_zendesk_ticket
from app.utils.helpers import remove_custom_delimiters, get_dataframe_from_csv, cache_conversation, \
    check_reply_requires_action, check_can_create_ticket
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from app.utils.slack import display_support_dialog, get_user_from_event, get_profile_from_id

router = APIRouter()

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
SLACK_CLIENT_ID = os.environ['SLACK_CLIENT_ID']
SLACK_CLIENT_SECRET = os.environ['SLACK_CLIENT_SECRET']
SLACK_APP_SCOPES = os.environ['SLACK_APP_SCOPES'].split(",")

oauth_settings = AsyncOAuthSettings(
    client_id=SLACK_CLIENT_ID,
    client_secret=SLACK_CLIENT_SECRET,
    scopes=SLACK_APP_SCOPES,
    installation_store=FileInstallationStore(base_dir="./data/installations"),
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data/states")
)

# Event API & Web API
app = AsyncApp(oauth_settings=oauth_settings, signing_secret=SLACK_SIGNING_SECRET)
app_handler = AsyncSlackRequestHandler(app)
client = WebClient(SLACK_BOT_TOKEN)


async def generate_reply(event, logger: logging.Logger, reply_in_thread=True):
    pprint(event)
    history = []
    thread_ts = event.get("thread_ts", None)
    # initially return a message that Alfred is thinking and store metadata for that message
    logger.debug(f"IN_THREAD: {reply_in_thread}")
    if reply_in_thread:
        to_replace = client.chat_postMessage(
            channel=event["channel"], thread_ts=event["event_ts"], text=f"Alfred is thinking :robot_face:"
        )
    else:
        to_replace = client.chat_postMessage(channel=event["channel"], text=f"Alfred is thinking :robot_face:")

    bot_id = client.auth_test()['bot_id']
    # check if the message was made inside a thread and not root of channel
    if thread_ts:
        conversation_id = f"{bot_id}:{thread_ts}"
        # check if the GPT conversation history is cached in memory
        r = Redis()
        byte_result = r.get_value(conversation_id)
        if byte_result:
            str_result = str(byte_result, encoding='utf-8')
            history = json.loads(str_result)
    # check if the message was made inside alfred jnr chat message tab
    elif str(event["channel"]).startswith("D"):
        conversation_id = f"{bot_id}:{event['channel']}"
        r = Redis()
        # check if the GPT conversation history is cached in memory
        byte_result = r.get_value(conversation_id)
        if byte_result:
            str_result = str(byte_result, encoding='utf-8')
            history = json.loads(str_result)

    sender_name = (await get_user_from_event(event, client))['first_name']
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
        # check if the message from user was a question or not
        is_question = '?' in message
        reply, messages = await continue_chat_response(message, context, history, is_question)
    else:
        reply, messages = await generate_gpt_chat_response(message, context, sender_name)
    print(f"\nREPLY: {reply}")
    response = client.chat_update(channel=event["channel"], ts=to_replace['message']['ts'], text=reply)
    logger.debug(response.data)
    # if the message was made inside the app message tab
    channel_type: Literal["DM_REPLY", "DM_MESSAGE", "CHANNEL_MENTION_REPLY"]
    if "channel_type" in event and event["channel_type"] == "im":
        # if the message was a reply
        if thread_ts:
            channel_type = "DM_REPLY"
        else:
            channel_type = "DM_MESSAGE"
    # if the message was made in a group channel where the bot is mentioned
    else:
        channel_type = "CHANNEL_MENTION_REPLY"
    result = cache_conversation(channel_type, response.data, client, messages)
    return reply, response.data, messages


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
    print("app_mention event:")
    event = body["event"]
    logger.debug(event)
    # Check if the message was made in the main channel (outside thread)
    if not event.get("thread_ts", None):
        thread_ts = event.get("thread_ts", None) or event["ts"]
        reply, response, history = await generate_reply(event, logger)
        # check if Alfred wants to create a Zendesk ticket and has all information needed to create one
        if check_can_create_ticket(reply, history):
            profile = get_profile_from_id(event['user'], client)
            await send_zendesk_ticket(reply, profile)
        # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on zendesk
        # OR to contact someone from HR/IT
        take_action = check_reply_requires_action(reply, [])
        if take_action:
            await display_support_dialog(client, response)


@app.event({"type": "message"})
async def handle_message(body, say, logger):
    # Log message
    event = body["event"]
    logger.debug(event)
    thread_ts = event.get("thread_ts", None)
    # USE CASE 1: Message sent directly to Alfred bot via the message tab
    if event["channel_type"] == "im":
        print("handle_bot_message event:")
        reply, response, history = await generate_reply(event, logger, bool(thread_ts))
        # check if Alfred wants to create a Zendesk ticket and has all information needed to create one
        if check_can_create_ticket(reply, history):
            profile = get_profile_from_id(event['user'], client)
            await send_zendesk_ticket(reply, profile)
        # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on zendesk
        # OR to contact someone from HR/IT
        take_action = check_reply_requires_action(reply, [])
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
            reply, response, history = await generate_reply(event, logger)
            # check if Alfred wants to create a Zendesk ticket and has all information needed to create one
            if check_can_create_ticket(reply, history):
                profile = get_profile_from_id(event['user'], client)
                await send_zendesk_ticket(reply, profile)
            # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on
            # zendesk OR to contact someone from HR/IT
            take_action = await check_reply_requires_action(reply, [])
            if take_action:
                await display_support_dialog(client, response)
        else:
            logger.info(f"No bot mention not found in thread: {thread_ts}")
    else:
        return


@app.event({"type": "message", "subtype": "file_share"})
async def handle_file_share(body, say: AsyncSay, logger):
    event = body["event"]
    logger.debug(event)
    # ERROR handling
    # check if a file was uploaded in the event, and respond with an error
    if "files" in event and len(event["files"]) > 0:
        await say(
            text="Sorry, I can't process that file. Please type out your question and I will try to answer it. 🙂",
            thread_ts=event["event_ts"],
        )
    # if raw_message is empty, return an error message
    elif not str(event["text"]):
        await say(text="Sorry, I didn't get that. Please try again.", thread_ts=event["event_ts"])


@app.command("/greet")
async def command(ack, body):
    user_id = body["user_id"]
    await ack(text=f"Hi <@{user_id}>! How can I help you?")


@router.post("/events")
async def endpoint(req: Request):
    data = await req.json()
    if 'challenge' in data:
        return {'challenge': data['challenge']}
    return await app_handler.handle(req)
