import os
from pprint import pprint
from typing import Callable
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from app.utils.helpers import get_dataframe_from_csv, remove_custom_delimiters
from app.utils.gpt import get_similarities, \
    generate_context_array, generate_gpt_chat_response, continue_chat_response
from app.utils.types import ChatPayload
from slack_bolt.async_app import AsyncApp, AsyncSay
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_sdk import WebClient
from fastapi import FastAPI, Request, APIRouter
from .routers import slack

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']

logging.basicConfig(level=logging.DEBUG)

api = FastAPI()

api.include_router(slack.router, prefix="/slack", tags=["slack"])

origins = ["*", "http://localhost", "http://localhost:4200", "https://deskflow-nine.vercel.app"]

api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/")
def hello_world():
    return {"message": "Hello World!"}


@api.get("/cwd")
def get_cwd():
    return {"cwd": os.getcwd()}


@api.post("/api/v1/generate-chat-response")
async def chat(payload: ChatPayload):
    print(payload)
    # download knowledge base embeddings from csv
    knowledge_base = get_dataframe_from_csv(f"{os.getcwd()}/app/data", "zendesk_vector_embeddings.csv")
    # create query embedding and fetch relatedness between query and knowledge base in dataframe
    similarities = await get_similarities(payload.query, knowledge_base)
    # Combine all top n answers into one chunk of text to use as knowledge base context for GPT
    context = generate_context_array(similarities)
    print(context.split("\n"))
    print("-" * 50)
    # check if the query is the first question of the conversation
    if len(payload.history):
        response, messages = await continue_chat_response(payload.query, context, payload.history)
    else:
        response, messages = await generate_gpt_chat_response(payload.query, context, payload.company)
    print(response)
    return {"reply": response, "messages": messages}


if __name__ == '__main__':
    uvicorn.run(api, port=8080, host='127.0.0.1')
