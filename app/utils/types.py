from typing import Literal, Optional, List, Dict
from pydantic import BaseModel


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
    history: Optional[List[Dict[str, str]]] = []
    company: Optional[str] = "Omnicentra"
