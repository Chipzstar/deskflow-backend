import os
from pprint import pprint
from typing import Tuple

from fastapi import APIRouter, Request
from slack_bolt import Ack
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.respond.async_respond import AsyncRespond
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.utils.gpt import send_zendesk_ticket
from app.utils.slack import get_user, display_plain_text_dialog

router = APIRouter()

SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']

# Event API & Web API
app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
app_handler = AsyncSlackRequestHandler(app)
client = WebClient(SLACK_BOT_TOKEN)


def validate_user(body: dict) -> Tuple[bool, str]:
    # fetch the user's ID'
    user_id = body["user"]["id"]
    conversation = client.conversations_history(
        channel=body["channel"]["id"],
        limit=3
    )
    # pprint(conversation.data)
    # Retrieve the last message containing the original question asked to Alfred
    last_message = conversation.data['messages'][2]
    pprint(last_message)
    print(f"{'-' * 100}{last_message['text']}{'-' * 100}")
    # Validate that the user that clicked the button matches the user that posted the question
    return user_id == last_message["user"], last_message


@app.action({"action_id": "user_select"})
async def handle_user_select(ack: AsyncAck, body: dict, respond: AsyncRespond):
    await ack()
    pprint(body)
    channel_id = body["channel"]["id"]
    selected_user_id = body["actions"][0]["selected_user"]
    recipient = get_user(selected_user_id, client)
    print(f"Selected user: {recipient['real_name_normalized']}")
    try:
        conversation = client.conversations_history(
            channel=channel_id,
            limit=7
        )
        # for message in conversation.data['messages']:
        #     print(f"{'-' * 50}\n{message['text'][0:50]}\n{'-' * 50}")

        for message in conversation.data['messages']:
            print("user" in message)
            print("app_id" in message)
            if "user" in message and "app_id" not in message:
                last_message = message
                user = get_user(last_message["user"], client)
                response = client.chat_postMessage(
                    text=f"Hello {recipient['first_name']}, <@{last_message['user']}> wants to know:\n",
                    channel=selected_user_id
                )
                await display_plain_text_dialog(
                    last_message["text"],
                    last_message['user'],
                    recipient['first_name'],
                    client,
                    response.data
                )
                print(f"Sent message to {recipient['first_name']}")
                break
        await respond(
            replace_original=True,
            text=f":white_check_mark:  Your query has been sent to <@{selected_user_id}>! I will update you as soon "
                 f"as I get a reply"
        )
    except SlackApiError as e:
        print(f"Error sending message: {e}")


@app.action({"action_id": "reply_support"})
async def handle_reply_support(ack: AsyncAck, body: dict, respond: AsyncRespond):
    await ack()
    pprint(body)
    user_id = body["actions"][0]["block_id"]
    sender = body["user"]["id"]
    user_profile = get_user(user_id, client)
    client.chat_postMessage(channel=user_id, text=f"<@{sender}> says: {body['actions'][0]['value']}")
    await respond(
        replace_original=True,
        text=f":white_check_mark:  Thank you for replying to <@{user_id}>",
    )
    return None


@app.action({"action_id": "create_ticket"})
async def handle_create_ticket(ack: AsyncAck, body: dict, respond: AsyncRespond):
    # Acknowledge the action request
    await ack()
    authorized, last_message = validate_user(body)
    if not authorized:
        await respond(
            replace_original=False,
            text=":x: It seems like you are not the author of that question",
        )
        return
    else:
        await respond(
            replace_original=False,
            text="Ok, hold on while I create your Zendesk support ticket for you",
        )
        # Create a Zendesk support ticket using the data from the action payload
        await send_zendesk_ticket(last_message)
        await respond(
            replace_original=False,
            text=":white_check_mark: Done!",
        )


@app.action({"action_id": "contact_support"})
async def handle_contact_support(ack: AsyncAck, body: dict, respond: AsyncRespond):
    # Acknowledge the action request
    await ack()
    authorized, last_message = validate_user(body)
    if not authorized:
        await respond(
            replace_original=False,
            text=":x: It seems like you are not the author of that question",
        )
        return
    else:
        await respond(
            blocks=[
                {
                    "type": "section",
                    "block_id": "section678",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Select an employee from the dropdown list"
                    },
                    "accessory": {
                        "action_id": "user_select",
                        "type": "users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Which employee would you like to contact?"
                        }
                    }
                }
            ]
        )


@router.post("/interactions")
async def endpoint(req: Request):
    return await app_handler.handle(req)
