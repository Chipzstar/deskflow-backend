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

from starlette.responses import HTMLResponse
# Import the Zenpy Class
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket
from pprint import pprint
from scipy import spatial  # for calculating vector similarities for search
import typing  # for type hints
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def hello_world():
    return {"message": "Hello World!"}


@app.post("/api/v1/generate-response")
def generate(query: str, category: typing.Literal["IT", "HR"], company="Omnicentra"):
    return {"query": query, "category": category, "company": company }


if __name__ == '__main__':
    uvicorn.run(app, port=8080, host='127.0.0.1')
