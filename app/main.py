from dotenv import load_dotenv

load_dotenv()

import logging
import os
from pprint import pprint

import uvicorn
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.db.prisma_client import prisma
from app.routers.slack import events, interactions, oauth
from app.routers.zendesk import zendesk_guide
from app.utils.gpt import (
    get_similarities,
    generate_context_array,
    generate_gpt_chat_response,
    continue_chat_response,
)
from app.utils.helpers import get_dataframe_from_csv
from app.utils.types import ChatPayload
from celery.result import AsyncResult
import app.worker as worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

api = FastAPI()

origins = [
    "*",
    "http://localhost",
    "http://localhost:4200",
    "https://deskflow.ngrok.app",
    "https://deskflow-app.vercel.app/",
    "https://deskflow-app-git-dev-deskflow.vercel.app",
    "https://dev.deskflow.ai",
    "https://app.deskflow.ai",
]

api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api.include_router(events.router, prefix="/slack", tags=["slack", "events"])
api.include_router(interactions.router, prefix="/slack", tags=["slack", "interactions"])
api.include_router(oauth.router, prefix="/slack", tags=["slack", "oauth"])
api.include_router(zendesk_guide.router, prefix="/zendesk", tags=["zendesk", "knowledge-base"])


@api.on_event("startup")
async def startup():
    await prisma.connect()


@api.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()


@api.get("/")
def hello_world():
    return {"message": "Hello World!"}


@api.get("/cwd")
def get_cwd():
    return {"cwd": os.getcwd()}


@api.post("/tasks", status_code=201)
def run_task(payload=Body(...)):
    task = worker.create_task.delay(payload["id"], payload["ttl"])
    return JSONResponse({"task_id": task.id, "convo_id": payload["id"]})


@api.get("/tasks/{task_id}")
def get_status(task_id):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    }
    return JSONResponse(result)


@api.post("/api/v1/generate-chat-response")
async def chat(payload: ChatPayload):
    pprint(payload)
    # download knowledge base embeddings from csv
    knowledge_base = get_dataframe_from_csv(f"{os.getcwd()}/app/data", "zendesk_vector_embeddings.csv")
    # create query embedding and fetch relatedness between query and knowledge base in dataframe
    similarities = await get_similarities(payload.query, knowledge_base, "csv")
    # Combine all top n answers into one chunk of text to use as knowledge base context for GPT
    context = generate_context_array(similarities)
    print(context.split("\n"))
    print("-" * 50)
    # check if the query is the first question of the conversation
    if len(payload.history):
        # check if the message from user was a question or not
        is_question = "?" in payload.query
        response, messages = await continue_chat_response(payload.query, context, payload.history, is_question)
    else:
        response, messages = await generate_gpt_chat_response(payload.query, context, payload.name, payload.company)
    print(response)
    return {"reply": response, "messages": messages}


if __name__ == "__main__":
    uvicorn.run("__main__:api", port=8080, host="127.0.0.1", reload=True)
