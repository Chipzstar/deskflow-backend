from sqlalchemy.orm import Session

from app.db import models
from app.db.schemas import Slack, SlackCreate, User, Zendesk


async def get_user(db: Session, user_id: str) -> User | None:
    """READS a user from the database using the user_id."""
    return await db.query(models.User).filter(models.User.clerk_id == user_id).first()


async def get_user_by_slack_state(db: Session, state: str) -> User | None:
    """READS a user from the database using the slack_state."""
    print(f"State: {state}")
    return await db.query(models.User).filter(models.User.slack_auth_state_id == state).first()


async def get_slack(db: Session, user_id: str) -> Slack | None:
    """READS a slack config from the database using the user_id."""
    return db.query(models.Slack).filter(models.Slack.user_id == user_id).first()


async def get_slack_by_team_id(db: Session, team_id: str) -> Slack | None:
    """READS a slack config from the database using the team_id."""
    return await db.query(models.Slack).filter(models.Slack.team_id == team_id).first()


async def get_zendesk(db: Session, user_id: str) -> Zendesk | None:
    """READS a zendesk config from the database using the user_id."""
    return await db.query(models.Zendesk).filter(models.Zendesk.user_id == user_id).first()


def create_slack(db: Session, slack: SlackCreate):
    db_slack = models.Slack(
        user_id=slack.user_id,
        team_id=slack.team_id,
        access_token=slack.access_token,
        team_name=slack.team_name,
        scopes=slack.scopes,
        bot_id=slack.bot_id,
        bot_access_token=slack.bot_access_token,
    )
    db.add(db_slack)
    db.commit()
    db.refresh(db_slack)
    return db_slack
