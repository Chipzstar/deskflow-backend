import json
from pprint import pprint
from typing import Literal, List, Dict

from redis.exceptions import ResponseError, RedisError
from slack_sdk import WebClient

from app.redis.client import Redis
from app.utils.helpers import ONE_DAY_IN_SECONDS, ONE_HOUR_IN_SECONDS
from app.utils.slack import get_conversation_id


def cache_conversation(
        channel_type: Literal["DM_REPLY", "DM_MESSAGE", "CHANNEL_MENTION_REPLY"],
        last_message,
        client: WebClient,
        history: List[Dict[str, str]]
):
    try:
        bot_id = client.auth_test()['bot_id']
        if channel_type == "CHANNEL_MENTION_REPLY" or channel_type == "DM_REPLY":
            root_message_id = get_conversation_id(
                last_message["channel"],
                last_message["message"]["thread_ts"],
                client
            )
            conversation_id = f"{bot_id}:{root_message_id}"
            pprint(f"CONVERSATION ID: {root_message_id}")
            r = Redis()
            # Cache the message in Redis using the message ID as the key, TTL = 1 day
            r.add_to_cache(conversation_id, json.dumps(history), ONE_DAY_IN_SECONDS)
        else:
            for message in history:
                print(message)
                print("-" * 80)
            conversation_id = f"{bot_id}:{last_message['channel']}"
            pprint(f"CONVERSATION ID: {conversation_id}")
            r = Redis()
            # Cache the message in Redis using the message ID as the key, TTL = 1 hour
            r.add_to_cache(conversation_id, json.dumps(history), ONE_HOUR_IN_SECONDS)
        return "Success"
    except ResponseError as e:
        print(f"Response Error: {e}")
        return None
    except RedisError as e:
        print(f"Redis Error: {e}")
        return None
