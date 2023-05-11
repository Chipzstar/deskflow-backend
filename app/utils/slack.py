from pprint import pprint

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import SectionBlock, ActionsBlock, DividerBlock


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


def get_user(user_id: str, client: WebClient):
    try:
        response = client.users_info(user=user_id)
        profile = response.data["user"]["profile"]
        pprint(f"{user_id} <=> {profile['first_name']}")
        return profile
    except SlackApiError as e:
        print("Error getting user: {}".format(e))
