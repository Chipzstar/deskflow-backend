from sqlalchemy.orm import Session

from app.db import models


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_slack_state(db: Session, state: str):
    print(f"State: {state}")
    return db.query(models.User).filter(models.User.slack_auth_state_id == state).first()