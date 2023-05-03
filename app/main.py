import os

from bs4 import BeautifulSoup
import mwclient  # for downloading example Wikipedia articles
import mwparserfromhell  # for splitting Wikipedia articles into sections
import openai  # for generating embeddings
import numpy as np  # for arrays to store embeddings
import pandas as pd  # for DataFrames to store article sections and embeddings
import re  # for cutting <ref> links out of Wikipedia articles
import tiktoken  # for counting tokens
from datetime import datetime
from tqdm.auto import tqdm  # this is our progress bar
from starlette.responses import HTMLResponse

# Import the Zenpy Class
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket
from pprint import pprint
from scipy import spatial  # for calculating vector similarities for search
import typing  # for type hints
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import generate_ai_response

openai.organization = "org-C15lzQ0mQYcGkjGrpiBPk2Hb"
openai.api_key = "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"

## DECLARE GLOBAL VARIABLES ##
MAX_INPUT_TOKENS = 8191
COMPLETIONS_MODEL = "text-davinci-003"

class Payload(BaseModel):
    category: typing.Literal["IT", "HR"]
    query: str
    company: str = ("Omnicentra",)


app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def hello_world():
    return {"message": "Hello World!"}


@app.post("/api/v1/generate-response")
async def generate(payload: Payload):
    await generate_ai_response.start(payload.query, payload.category, payload.company)

if __name__ == '__main__':
    uvicorn.run(app, port=8080, host='127.0.0.1')
