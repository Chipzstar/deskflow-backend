from pprint import pprint

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import ActionsBlock, DividerBlock, ButtonElement

load_dotenv()

import ssl
import os
import logging
import time
from celery import Celery
from redis.exceptions import ResponseError, RedisError
from app.redis.client import Redis
from celery.signals import worker_shutdown, celeryd_after_setup, worker_process_init

logger = logging.getLogger(__name__)

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")
celery.flower_unauthenticated_api = True

if os.environ.get("DOPPLER_ENVIRONMENT") == "prd":
    celery.conf.redis_backend_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    celery.conf.broker_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }


@celeryd_after_setup.connect
def capture_worker_name(sender, instance, **kwargs):
    os.environ["CELERY_WORKER_NAME"] = '{0}'.format(sender)
    celery.conf.worker_name = '{0}'.format(sender)


@worker_process_init.connect
def configure_worker(**kwargs):
    print("Initialising Prisma")


@worker_shutdown.connect
def shutdown_worker(**kwargs):
    print("Shutting down Prisma")


def expired_conversation_callback(convo_id, issue_id, token, channel):
    try:
        print("executing task....")
        r = Redis()
        convo = r.get_value(convo_id)
        # if the conversation exists in redis cache, set resolved status to unresolved
        if convo:
            client = WebClient(token=token)
            response = client.chat_postMessage(channel=channel, text="Has this issue been resolved?")
            # Define the interactive message
            # Create an interactivity pointer for the "Yes" button
            yes_pointer = ButtonElement(text="Yes", action_id="issue_resolved_yes", style="primary", value=issue_id)
            # Create an interactivity pointer for the "No" button
            no_pointer = ButtonElement(text="No", action_id="issue_resolved_no", style="danger", value=issue_id)
            buttons = ActionsBlock(
                elements=[yes_pointer, no_pointer]
            )
            divider = DividerBlock()
            block = [divider, buttons]
            # Post a message to a user using the interactivity pointer
            try:
                response = client.chat_postMessage(
                    channel=response['channel'],
                    text="New message",
                    blocks=block
                )
                pprint(response)
            except SlackApiError as e:
                print("Error posting message: {}".format(e))
            return True
        else:
            return f"No conversation with ID {convo_id} found in Redis"
    except (ResponseError, RedisError) as e:
        logger.error(f"Error retrieving conversation from Redis: {e}")
        return None  # or any other default value you want to return


@celery.task()
def adding_task(x, y):
    return x + y


@celery.task()
def create_task(convo_id: str, issue_id: str, token: str, channel: str, debug: bool = False):
    time.sleep(10 if debug else 300)
    expired_conversation_callback(convo_id, issue_id, token, channel)
    return {"message": "Success"}
