import json
import logging
import os
import time
from pprint import pprint
from typing import Callable, Literal

from celery.result import AsyncResult
from app.db.prisma_client import prisma
from fastapi import APIRouter, Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.async_app import AsyncSay
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings
from slack_sdk import WebClient
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore

from app.redis.client import Redis
from app.redis.utils import generate_conversation_id, create_issue, update_issue
from app.utils.gpt import (
    get_similarities,
    generate_context_array,
    continue_chat_response,
    generate_gpt_chat_response,
    send_zendesk_ticket,
    classify_issue,
)
from app.utils.helpers import (
    remove_custom_delimiters,
    check_reply_requires_action,
    check_can_create_ticket,
    get_vector_embeddings_from_pinecone, ONE_HOUR_IN_SECONDS, border_asterisk,
)
from app.utils.slack import (
    display_support_dialog,
    get_user_from_event,
    get_profile_from_id,
    fetch_access_token,
    installation_base_dir,
)
from app.worker import create_task

router = APIRouter()

ENVIRONMENT = os.environ.get("DOPPLER_ENVIRONMENT", "dev")
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
SLACK_CLIENT_ID = os.environ["SLACK_CLIENT_ID"]
SLACK_CLIENT_SECRET = os.environ["SLACK_CLIENT_SECRET"]
SLACK_APP_SCOPES = os.environ["SLACK_APP_SCOPES"].split(",")


oauth_settings = AsyncOAuthSettings(
    client_id=SLACK_CLIENT_ID,
    client_secret=SLACK_CLIENT_SECRET,
    scopes=SLACK_APP_SCOPES,
    installation_store=FileInstallationStore(base_dir=installation_base_dir),
    state_store=FileOAuthStateStore(
        expiration_seconds=600, base_dir=f"{os.getcwd()}/app/data/states"
    ),
)

# Event API & Web API
app = AsyncApp(oauth_settings=oauth_settings, signing_secret=SLACK_SIGNING_SECRET)
app_handler = AsyncSlackRequestHandler(app)


async def generate_reply(
    event, client: WebClient, token: str, logger: logging.Logger, reply_in_thread=True
):
    history = []
    issue_id = None
    pprint(event)
    # fetch slack + user info from DB
    slack = await prisma.slack.find_first(where={"team_id": event["team"]})
    if slack is None:
        logger.error(f"Slack not found for team {event['team']}")
        return "", None, [], None
    org = await prisma.organization.find_unique(where={"clerk_id": slack.org_id})
    slack_profile = get_profile_from_id(event["user"], client)
    logger.debug(org)
    thread_ts = event.get("thread_ts", None)
    # initially return a message that Alfred is thinking and store metadata for that message
    logger.debug(f"IN_THREAD: {reply_in_thread}")
    if reply_in_thread:
        to_replace = client.chat_postMessage(
            channel=event["channel"],
            thread_ts=event["event_ts"],
            text=f"Alfred is thinking :robot_face:",
        )
    else:
        to_replace = client.chat_postMessage(
            channel=event["channel"], text=f"Alfred is thinking :robot_face:"
        )

    bot_id = client.auth_test()["bot_id"]
    # check if the message was made inside a thread and not root of channel
    if thread_ts:
        conversation_id = f"{bot_id}:{thread_ts}"
        # check if the GPT conversation history is cached in memory
        r = Redis()
        byte_result = r.get_value(conversation_id)
        if byte_result:
            str_result = str(byte_result, encoding="utf-8")
            history = json.loads(str_result)
    # check if the message was made inside alfred chat message tab
    elif str(event["channel"]).startswith("D"):
        conversation_id = f"{bot_id}:{event['channel']}"
        r = Redis()
        # check if the GPT conversation history is cached in memory
        byte_result = r.get_value(conversation_id)
        if byte_result:
            str_result = str(byte_result, encoding="utf-8")
            history = json.loads(str_result)

    sender_name = (await get_user_from_event(event, client))["first_name"]
    # Extract raw message from the event
    raw_message = str(event["text"])
    # remove any mention tags from the message and sanitize it
    message = remove_custom_delimiters(raw_message).strip()
    print(f"\nMESSAGE:\t {message}")
    # download knowledge base embeddings from pinecone namespace
    knowledge_base = get_vector_embeddings_from_pinecone("alfred", org.slug)
    # create query embedding and fetch relatedness between query and knowledge base in dataframe
    similarities = await get_similarities(message, knowledge_base)
    # Combine all top n answers into one chunk of text to use as knowledge base context for GPT
    context = generate_context_array(similarities)
    # check if the query is the first question of the conversation
    if len(history):
        # check if the message from user was a question or not
        is_question = "?" in message
        reply, messages = await continue_chat_response(
            message, context, history, is_question
        )
    else:
        reply, messages = await generate_gpt_chat_response(
            message, context, sender_name
        )
    print(f"\nREPLY: {reply}")
    response = client.chat_update(
        channel=event["channel"], ts=to_replace["message"]["ts"], text=reply
    )
    channel_type: Literal["DM_REPLY", "DM_MESSAGE", "CHANNEL_MENTION_REPLY"]
    # if the message was made inside the app message tab
    if "channel_type" in event and event["channel_type"] == "im":
        # if the message was a reply
        if thread_ts:
            channel_type = "DM_REPLY"
        else:
            channel_type = "DM_MESSAGE"
    # if the message was made in a group channel where the bot is mentioned
    else:
        channel_type = "CHANNEL_MENTION_REPLY"
    conversation_id = generate_conversation_id(channel_type, response.data, client, messages)
    issue_id = f"issue_{int(time.time())}"
    r = Redis()
    # Cache the message in Redis using the message ID as the key, TTL = 1 hour
    r.add_to_cache(conversation_id, json.dumps(messages), ONE_HOUR_IN_SECONDS)
    # schedule a worker job to send a message to the user that the conversation is now finished after the
    # cache expires
    task = create_task.delay(conversation_id, issue_id, token, event["channel"], ENVIRONMENT == "dev")
    category = classify_issue(message)
    # create reference to the start of the issue in the DB or update the issue if already exists
    if not len(history):
        issue = await create_issue(
            conversation_id,
            issue_id,
            task.id,
            org,
            slack_profile,
            event["user"],
            category,
            messages
        )
    else:
        issue = await update_issue(
            conversation_id,
            issue_id,
            task.id,
            slack_profile,
            event["user"],
            category,
            messages
        )
    return reply, response.data, messages, org


async def check_bot_mentioned_in_thread(
    token: str, channel: str, thread_ts: str, client: WebClient
):
    response = client.conversations_replies(
        channel=channel, ts=thread_ts, inclusive=True
    )
    bot_info = client.auth_test(token=token)
    bot_user_id = bot_info["user_id"]
    for message in response.data["messages"]:
        # Check if the message was authored by the Slack bot or contains a mention of the bot user ID
        # check if any message contains the bot user id
        if "bot_id" in message and message["bot_id"] == bot_user_id:
            return True
        elif "text" in message and f"<@{bot_user_id}>" in message["text"]:
            return True
        elif "user" in message and message["user"] == bot_user_id:
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
    token = await fetch_access_token(body["authorizations"][0]["team_id"], logger)
    client = WebClient(token=token)
    # Check if the message was made in the main channel (outside thread)
    if not event.get("thread_ts", None):
        thread_ts = event.get("thread_ts", None) or event["ts"]
        reply, response, history, user = await generate_reply(
            event, client, token, logger
        )
        # check if Alfred wants to create a Zendesk ticket and has all information needed to create one
        if check_can_create_ticket(reply, history):
            profile = get_profile_from_id(event["user"], client)
            # fetch zendesk config for the user in DB
            zendesk = await prisma.zendesk.find_first(where={"user_id": user.clerk_id})
            await send_zendesk_ticket(reply, profile, zendesk)
        # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on zendesk
        # OR to contact someone from HR/IT
        take_action = check_reply_requires_action(reply, [])
        if take_action:
            await display_support_dialog(client, response)


@app.event({"type": "message"})
async def handle_message(body: dict, say: AsyncSay, logger: logging.Logger):
    # Log message
    event = body["event"]
    logger.debug(event)
    thread_ts = event.get("thread_ts", None)
    token = await fetch_access_token(body["authorizations"][0]["team_id"], logger)
    client = WebClient(token=token)
    # USE CASE 1: Message sent directly to Alfred bot via the message tab
    if event["channel_type"] == "im":
        print("handle_bot_message event:")
        reply, response, history, user = await generate_reply(
            event, client, token, logger, bool(thread_ts)
        )
        # check if Alfred wants to create a Zendesk ticket and has all information needed to create one
        if check_can_create_ticket(reply, history):
            slack_profile = get_profile_from_id(event["user"], client)
            # fetch zendesk config for the user in DB
            zendesk = await prisma.zendesk.find_first(where={"user_id": user.clerk_id})
            if zendesk:
                await send_zendesk_ticket(reply, slack_profile, zendesk)
            else:
                await say(
                    text=f"Sorry, it looks you haven't integrated your Zendesk account yet on Deskflow. Please "
                    f"confirm with your manager that this has been setup or contact us at support@deskflow.ai"
                )
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
        is_mentioned = await check_bot_mentioned_in_thread(
            token, event["channel"], thread_ts, client
        )
        if is_mentioned:
            # extract message from event
            reply, response, history, user = await generate_reply(
                event, client, token, logger
            )
            # check if Alfred wants to create a Zendesk ticket and has all information needed to create one
            if check_can_create_ticket(reply, history):
                slack_profile = get_profile_from_id(event["user"], client)
                # fetch zendesk config for the user in DB
                zendesk = await prisma.zendesk.find_first(
                    where={"user_id": user.clerk_id}
                )
                if zendesk:
                    await send_zendesk_ticket(reply, slack_profile, zendesk)
                else:
                    await say(
                        thread_ts=thread_ts,
                        text=f"Sorry, it looks you haven't integrated your Zendesk account yet on Deskflow. "
                        f"Please confirm with your manager that this has been setup or contact us at "
                        f"support@deskflow.ai",
                    )
            # check if Alfred could not find the answer in the knowledge base and is offering to create a ticket on
            # zendesk OR to contact someone from HR/IT
            take_action = check_reply_requires_action(reply, [])
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
        await say(
            text="Sorry, I didn't get that. Please try again.",
            thread_ts=event["event_ts"],
        )


@app.event({"type": "message", "subtype": "message_deleted"})
async def handle_message_deleted(body, say: AsyncSay, logger):
    event = body["event"]
    logger.debug(event)
    # handle message deleted event
    return None


@app.command("/greet")
async def command(ack, body):
    user_id = body["user_id"]
    await ack(text=f"Hi <@{user_id}>! How can I help you?")


@router.post("/events")
async def endpoint(req: Request):
    data = await req.json()
    if "challenge" in data:
        return {"challenge": data["challenge"]}
    return await app_handler.handle(req)
