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
