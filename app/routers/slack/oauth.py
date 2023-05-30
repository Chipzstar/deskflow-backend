import os
from pprint import pprint
from typing import Tuple

from fastapi import APIRouter, HTTPException, Depends
from slack_sdk import WebClient
from slack_sdk.oauth.installation_store import FileInstallationStore, Installation
from sqlalchemy.orm import Session

from app.db.crud import get_user_by_slack_state, get_slack, create_slack
from app.db.database import SessionLocal
from app.db.schemas import User, SlackCreate
from app.utils.types import OAuthPayload


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter()

SLACK_CLIENT_ID = os.environ['SLACK_CLIENT_ID']
SLACK_CLIENT_SECRET = os.environ['SLACK_CLIENT_SECRET']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
CLIENT_HOST = os.environ.get('CLIENT_HOST', None)

# Persist installation data and lookup it by IDs.
installation_store = FileInstallationStore(base_dir=f"{os.getcwd()}/app/data/installations")


def verify_state(state: str, db: Session) -> Tuple[User, bool]:
    user = get_user_by_slack_state(db=db, state=state)
    verified = bool(user)
    print(f"verified: {verified}")
    return user, bool(verified)


@router.post("/oauth/callback")
async def oauth_callback(payload: OAuthPayload, db: Session = Depends(get_db)):
    pprint(payload)
    # Retrieve the auth code and state from the request params
    if payload.code:
        user, verified = verify_state(payload.state, db)
        # Verify the state parameter
        if verified:
            client = WebClient()  # no prepared token needed for this
            # Complete the installation by calling oauth.v2.access API method
            oauth_response = client.oauth_v2_access(
                client_id=SLACK_CLIENT_ID,
                client_secret=SLACK_CLIENT_SECRET,
                redirect_uri=f"{CLIENT_HOST}/integrations/slack",
                code=payload.code
            )
            installed_enterprise = oauth_response.get("enterprise") or {}
            is_enterprise_install = oauth_response.get("is_enterprise_install")
            installed_team = oauth_response.get("team") or {}
            installer = oauth_response.get("authed_user") or {}
            incoming_webhook = oauth_response.get("incoming_webhook") or {}
            bot_token = oauth_response.get("access_token")
            # NOTE: oauth.v2.access doesn't include bot_id in response
            bot_id = None
            enterprise_url = None
            if bot_token is not None:
                auth_test = client.auth_test(token=bot_token)
                bot_id = auth_test["bot_id"]
                if is_enterprise_install is True:
                    enterprise_url = auth_test.get("url")

            installation = Installation(
                app_id=oauth_response.get("app_id"),
                enterprise_id=installed_enterprise.get("id"),
                enterprise_name=installed_enterprise.get("name"),
                enterprise_url=enterprise_url,
                team_id=installed_team.get("id"),
                team_name=installed_team.get("name"),
                bot_token=bot_token,
                bot_id=bot_id,
                bot_user_id=oauth_response.get("bot_user_id"),
                bot_scopes=oauth_response.get("scope"),  # comma-separated string
                user_id=installer.get("id"),
                user_token=installer.get("access_token"),
                user_scopes=installer.get("scope"),  # comma-separated string
                incoming_webhook_url=incoming_webhook.get("url"),
                incoming_webhook_channel=incoming_webhook.get("channel"),
                incoming_webhook_channel_id=incoming_webhook.get("channel_id"),
                incoming_webhook_configuration_url=incoming_webhook.get("configuration_url"),
                is_enterprise_install=is_enterprise_install,
                token_type=oauth_response.get("token_type"),
            )

            # Store the installation
            installation_store.save(installation)
            # search for slack entity in DB
            slack = get_slack(db=db, user_id=user.clerk_id)
            if slack is None:
                slack = create_slack(db=db, slack=SlackCreate(
                    user_id=user.clerk_id,
                    access_token=bot_token,
                    team_id=installed_team.get("id"),
                    team_name=installed_team.get("name"),
                    bot_id=bot_id,
                    bot_access_token=bot_token,
                    scopes=oauth_response.get("scope")
                ))
            return {"status": "Success", "message": "Thanks for installing Alfred!"}
        else:
            raise HTTPException(
                detail=f"Try the installation again (the state value is already expired)",
                status_code=400
            )
    raise HTTPException(status_code=404, detail="Authorization code was not provided!")
