from pydantic import BaseModel


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    email: str
    firstname: str
    lastname: str
    fullname: str


class User(UserBase):
    id: int
    clerk_id: str
    email: str
    firstname: str
    lastname: str
    fullname: str
    stripe_customer_id: str
    stripe_subscription_id: str
    stripe_payment_method: str
    slack_auth_state_id: str

    class Config:
        orm_mode = True


class SlackBase(BaseModel):
    user_id: str
    team_name: str
    team_id: str
    access_token: str
    scopes: str
    bot_id: str
    bot_access_token: str


class Slack(SlackBase):
    id: int
    user_id: str
    team_name: str
    team_id: str
    access_token: str
    scopes: str
    bot_id: str
    bot_access_token: str

    class Config:
        orm_mode = True


class SlackCreate(SlackBase):
    user_id: str
    team_name: str
    team_id: str
    access_token: str
    scopes: str
    bot_id: str
    bot_access_token: str


class ZendeskBase(BaseModel):
    user_id: str
    access_token: str
    subdomain: str
    account_email: str
    account_id: str
    guide: bool
    support: bool


class Zendesk(ZendeskBase):
    id: int
    user_id: str
    access_token: str
    subdomain: str
    account_email: str
    account_id: str
    guide: bool
    support: bool

    class Config:
        orm_mode = True
