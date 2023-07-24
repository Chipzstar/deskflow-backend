import os
from pprint import pprint

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import ActionsBlock, DividerBlock, ButtonElement, PlainTextObject, \
    InputBlock, PlainTextInputElement

from app.db.prisma_client import prisma
from app.utils.types import Profile

installation_base_dir = (
    f"{os.getcwd()}/app/data/installations"
    if os.environ["DOPPLER_ENVIRONMENT"] == "dev"
    else f"/data/installations"
)


async def display_plain_text_dialog(
        question: str, sender_id: str, recipient_name: str, client: WebClient, response
):
    pprint(response)
    input_block = InputBlock(
        block_id=sender_id,
        label={
            "type": "plain_text",
            "text": question,
            "emoji": True
        },
        element=PlainTextInputElement(
            action_id="reply_support"
        ),
        dispatch_action=True
    )
    blocks = [input_block]
    # Post a message to a user using the interactivity pointer
    try:
        response = client.chat_postMessage(
            channel=response["channel"], text=question, blocks=blocks
        )
        print(response)
    except SlackApiError as e:
        print("Error posting message: {}".format(e))


def display_support_dialog(client: WebClient, response):
    print("TAKING ACTION!!!!")
    # Define the interactive message
    # Create an interactivity pointer for the "Create ticket" button
    create_ticket_pointer = ButtonElement(
        text=PlainTextObject(text="Create ticket"),
        action_id="create_ticket",
        style="primary"
    )
    # Create an interactivity pointer for the "Cancel" button
    cancel_pointer = ButtonElement(
        text="Contact HR/IT Support",
        action_id="contact_support",
        style="danger"
    )
    buttons = ActionsBlock(elements=[create_ticket_pointer, cancel_pointer])
    divider = DividerBlock()
    block = [divider, buttons]
    # Post a message to a user using the interactivity pointer
    try:
        response = client.chat_postMessage(
            channel=response["channel"], text="New message", blocks=block
        )
        print(response)
    except SlackApiError as e:
        print("Error posting message: {}".format(e))


async def issue_resolved_dialog(client: WebClient, response):
    # Define the interactive message
    # Create an interactivity pointer for the "Create ticket" button
    resolved_pointer = {
        "type": "button",
        "text": {"type": "plain_text", "text": "Yes"},
        "style": "primary",
        "action_id": "resolved_success",
    }

    # Create an interactivity pointer for the "Cancel" button
    not_resolved_pointer = {
        "type": "button",
        "text": {"type": "plain_text", "text": "No"},
        "style": "danger",
        "action_id": "resolved_failure",
    }
    buttons = ActionsBlock(elements=[resolved_pointer, not_resolved_pointer])
    divider = DividerBlock()
    block = [divider, buttons]
    # Post a message to a user using the interactivity pointer
    try:
        response = client.chat_postMessage(
            channel=response["channel"], text="New message", blocks=block
        )
        print(response)
    except SlackApiError as e:
        print("Error posting message: {}".format(e))


def get_user_from_id(user_id: str, client: WebClient):
    try:
        response = client.users_info(user=user_id)
        profile = response.data["user"]["profile"]
        pprint(f"{user_id} <=> {profile['first_name']}")
        return profile
    except SlackApiError as e:
        print("Error getting user: {}".format(e))
        raise Exception(f"Error fetching user information for user {user_id}: {e}")


def get_profile_from_id(user_id: str, client: WebClient) -> Profile:
    try:
        response = client.users_profile_get(user=user_id)
        profile = response.data["profile"]
        pprint(f"{user_id} <=> {profile['first_name']}")
        return Profile(name=profile["real_name_normalized"], email=profile["email"])
    except SlackApiError as e:
        print("Error getting user: {}".format(e))
        raise Exception(f"Error fetching user information for user {user_id}: {e}")


async def get_user_from_event(event, client: WebClient):
    try:
        # Extract the user ID from the message event
        user_id = event["user"]
        # Use the app.client method to fetch user information by ID
        response = client.users_info(user=user_id)
        pprint(f"USER INFO: {response.data['user']['profile']['real_name_normalized']}")
        # Extract the username from the API response
        if response.data:
            profile = response.data["user"]["profile"]
            pprint(f"{user_id} <=> {profile['first_name']}")
            print("-" * 75)
            return profile
    except SlackApiError as e:
        print("Error getting user: {}".format(e))
        raise Exception(f"Error fetching user information: {e}")


def get_conversation_id(channel, ts, client: WebClient):
    # fetch all replies from the last message
    conversation = client.conversations_replies(channel=channel, ts=ts, inclusive=True)
    # get the timestamp of the root message for the conversation
    root_message_id = conversation.data["messages"][0]["ts"]
    return root_message_id


async def fetch_access_token(team_id: str, logger):
    # fetch slack access token from database using the team_id
    if not team_id:
        return None
    slack_config = await prisma.slack.find_first(where={"team_id": team_id})
    if not slack_config:
        logger.error(f"Slack config not found for team_id: {team_id}")
        return
    return slack_config.access_token
