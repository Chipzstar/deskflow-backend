import json
from pprint import pprint
from typing import Literal, List, Dict

from celery.result import AsyncResult
from prisma.models import User
from redis.exceptions import ResponseError, RedisError
from slack_sdk import WebClient

from app.db.prisma_client import prisma
from app.redis.client import Redis
from app.utils.helpers import ONE_DAY_IN_SECONDS, ONE_HOUR_IN_SECONDS, TWO_DAYS_IN_SECONDS
from app.utils.slack import get_conversation_id, get_profile_from_id
from app.utils.types import Profile


async def update_issue(
    conversation_id: str,
    issue_id: str,
    task_id: str,
    slack_profile: Profile,
    employee_id: str,
    category: str,
    messages: List[Dict[str, str]]
):
    # fetch the latest open issue with matching conversation_id
    issues = await prisma.issue.find_many(
        where={"conversation_id": conversation_id, "status": "open"},
        order={"created_at": "desc"},
        take=1
    )
    # revoke the previous celery task if it exists
    if len(issues) and issues[0].celery_task_id:
        print(f"Previous celery task ID: {issues[0].celery_task_id}")
        task = AsyncResult(issues[0].celery_task_id)
        task.revoke(terminate=True, signal="SIGKILL")
        # issue already exists, locate issue in DB and update accordingly
        return await prisma.issue.update(
            where={"id": issues[0].id},
            data={
                "issue_id": issue_id,
                "celery_task_id": task_id,
                "employee_id": employee_id,
                "employee_name": slack_profile.name,
                "employee_email": slack_profile.email,
                "category": category,
                "messageHistory": str(messages),
                "status": "open"
            },
        )
    return None


async def create_issue(
        conversation_id: str,
        issue_id: str,
        task_id: str,
        user: User,
        slack_profile: Profile,
        employee_id: str,
        category: str,
        messages: List[Dict[str, str]]
):
    org = await prisma.organization.find_unique(
        where={"clerk_id": user.organization_id}
    )
    return await prisma.issue.create(
        data={
            "user_id": user.clerk_id,
            "issue_id": issue_id,
            "conversation_id": conversation_id,
            "celery_task_id": task_id,
            "org_id": org.clerk_id,
            "org_name": org.name,
            "channel": "slack",
            "employee_id": employee_id,
            "employee_name": slack_profile.name,
            "employee_email": slack_profile.email,
            "category": category,
            "messageHistory": str(messages),
            "status": "open",
            "is_satisfied": False,
        }
    )


def generate_conversation_id(
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
            pprint(f"CONVERSATION ID: {conversation_id}")
        else:
            for message in history:
                print(message)
                print("-" * 80)
            conversation_id = f"{bot_id}:{last_message['channel']}"
            pprint(f"CONVERSATION ID: {conversation_id}")
        return conversation_id
    except ResponseError as e:
        print(f"Response Error: {e}")
        return None
    except RedisError as e:
        print(f"Redis Error: {e}")
        return None
