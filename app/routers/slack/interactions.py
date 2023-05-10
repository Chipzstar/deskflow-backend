import os
from pprint import pprint

from fastapi import APIRouter, Request
from slack_bolt import Ack
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.respond.async_respond import AsyncRespond
from slack_sdk import WebClient

router = APIRouter()

SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']

# Event API & Web API
app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
app_handler = AsyncSlackRequestHandler(app)
client = WebClient(SLACK_BOT_TOKEN)


@app.action("create_ticket")
async def handle_create_ticket(ack: AsyncAck, body: dict, respond: AsyncRespond):
    await ack()
    user_id = body["user"]["id"]
    button_text = body["actions"][0]["text"]["text"]
    # Acknowledge the action request
    pprint(body)
    await respond(
        {
            "response_type": "in_channel",
            "replace_original": True,
            "text": f"<@{user_id}> clicked the '{button_text}' button!",
        }
    )
    await respond(
        replace_original=False,
        text=":white_check_mark: Done!",
    )
    # Create a Zendesk support ticket using the data from the action payload
    # ...


@router.post("/interactions")
async def endpoint(req: Request):
    return await app_handler.handle(req)
