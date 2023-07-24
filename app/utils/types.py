from typing import Literal, Optional, List, Dict, NamedTuple
from pydantic import BaseModel


class Profile(NamedTuple):
    name: str
    email: str


class ZendeskCredentials(NamedTuple):
    email: str
    token: str
    subdomain: str


class ZendeskOAuthCredentials(NamedTuple):
    oauth_token: str
    subdomain: str


class Message:
    def __init__(self, role: Literal["user", "system", "assistant"], content: str):
        self.role = role
        self.content = content

    def to_dict(self):
        return {"role": self.role, "content": self.content}


class MessagePayload(BaseModel):
    role: Literal["user", "system", "assistant"]
    content: str


class Payload(BaseModel):
    query: str
    company: str = "Omnicentra"


class ChatPayload(BaseModel):
    query: str
    name: str
    email: str
    history: Optional[List[Dict[str, str]]] = []
    company: Optional[str] = "Omnicentra"


class OAuthPayload(BaseModel):
    code: str
    state: str


class ZendeskKBPayload(BaseModel):
    token: str
    subdomain: str
    slug: str


class DeleteKBPayload(BaseModel):
    slug: str

