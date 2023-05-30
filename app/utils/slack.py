from pprint import pprint

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import SectionBlock, ActionsBlock, DividerBlock

from app.db import database
from app.db.crud import get_slack_by_team_id
from app.utils.helpers import border_asterisk
from app.utils.types import Profile


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def display_plain_text_dialog(
        question: str,
        sender_id: str,
        recipient_name: str,
        client: WebClient,
        response
):
    pprint(response)
    blocks = [
        {
            "type": "input",
            "dispatch_action": True,
            "block_id": sender_id,
            "element": {
                "type": "plain_text_input",
                "action_id": "reply_support"
            },
            "label": {
                "type": "plain_text",
                "text": question,
                "emoji": True
            },
        }
    ]
    # Post a message to a user using the interactivity pointer
    try:
        response = client.chat_postMessage(channel=response['channel'], text=question, blocks=blocks)
        print(response)
    except SlackApiError as e:
        print("Error posting message: {}".format(e))


async def display_support_dialog(client: WebClient, response):
    print("TAKING ACTION!!!!")
    # Define the interactive message
    # Create an interactivity pointer for the "Create ticket" button
    create_ticket_pointer = {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": "Create ticket"
        },
        "style": "primary",
        "action_id": "create_ticket"
    }

    # Create an interactivity pointer for the "Cancel" button
    cancel_pointer = {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": "Contact HR/IT Support"
        },
        "style": "danger",
        "action_id": "contact_support"
    }
    # Create a message block containing the header and buttons
    header = SectionBlock(
        text="Create Zendesk Support Ticket"
    )
    buttons = ActionsBlock(
        elements=[create_ticket_pointer, cancel_pointer]
    )
    divider = DividerBlock()
    block = [divider, buttons]
    # Post a message to a user using the interactivity pointer
    try:
        response = client.chat_postMessage(channel=response['channel'], text="New message", blocks=block)
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
        profile = response.data['profile']
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
            print("-"*75)
            return profile
    except SlackApiError as e:
        print("Error getting user: {}".format(e))
        raise Exception(f"Error fetching user information: {e}")


def get_conversation_id(channel, ts, client: WebClient):
    # fetch all replies from the last message
    conversation = client.conversations_replies(
        channel=channel,
        ts=ts,
        inclusive=True
    )
    # get the timestamp of the root message for the conversation
    root_message_id = conversation.data["messages"][0]['ts']
    return root_message_id


async def fetch_access_token(team_id: str, db, logger):
    # fetch slack access token from database using the team_id
    if not team_id:
        return None
    slack_config = get_slack_by_team_id(db=db, team_id=team_id)
    border_asterisk()
    print(slack_config.access_token)
    border_asterisk()
    if not slack_config:
        logger.error(f"Slack config not found for team_id: {team_id}")
        return
    return slack_config.access_token
