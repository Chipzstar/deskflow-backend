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

openai.organization = "org-C15lzQ0mQYcGkjGrpiBPk2Hb"
openai.api_key = "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"

# DECLARE GLOBAL VARIABLES #
EMBEDDING_MODEL = "text-embedding-ada-002"  # OpenAI's best embeddings as of Apr 2023
MAX_INPUT_TOKENS = 8191
COMPLETIONS_MODEL = "text-davinci-003"
BATCH_SIZE = 1000  # you can submit up to 2048 embedding inputs per request
SCORES = []
ANSWERS = []
EMBEDDINGS = []


class Payload(BaseModel):
    category: typing.Literal["IT", "HR"]
    query: str
    company: str = ("Omnicentra",)


app = FastAPI()

origins = ["http://localhost", "http://localhost:4200", "https://deskflow-nine.vercel.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_date_string():
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def get_dataframe_from_csv(path: str, filename: str) -> pd.DataFrame:
    df = pd.read_csv(f"{path}/{filename}")
    return df


def save_dataframe_to_csv(df: pd.DataFrame, path: str, filename: str):
    if not os.path.exists(path):
        os.mkdir(path)
        print(f"Created {path}")
    df.to_csv(f"{path}/{filename}", index=False)


# search function
def strings_ranked_by_relatedness(
    query: str, df: pd.DataFrame, relatedness_fn=lambda x, y: 1 - spatial.distance.cosine(x, y), top_n: int = 100
) -> tuple[list[str], list[float]]:
    """Returns a list of strings and relatednesses, sorted from most related to least."""
    query_embedding_response = openai.Embedding.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    query_embedding = query_embedding_response["data"][0]["embedding"]
    strings_and_relatednesses = [
        (row["content"], relatedness_fn(query_embedding, row["embedding"])) for i, row in df.iterrows()
    ]
    strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)
    strings, relatednesses = zip(*strings_and_relatednesses)
    return strings[:top_n], relatednesses[:top_n], query_embedding


# # 7. Use GPT3 model to generate user-friendly answers to the query
def generate_gpt_opt_response(
    record: pd.Series,
    category: typing.Literal["IT", "HR"],
    company: str = "Omnicentra",
    description: str = "an AI software company",
):
    question = record.question
    context = record.top_answer
    prompt = f"""Name: Alfred

"Answer the following question by rephrasing the context below"
Context:
{context}

Question:
{question}

You are an AI-powered assistant designed to help employees with {category} questions at {company}. You have been programmed to provide fast and accurate solutions to their inquiries. As an AI, you do not have a gender, age, sexual orientation or human race.

As an experienced assistant, you can create Zendesk tickets and forward complex inquiries to the appropriate person. If you are unable to provide an answer, you will respond by saying "I don't know, would you like me to create a ticket on Zendesk or ask {category}?" and follow the steps accordingly based on their response.

If a question is outside your scope, you will make a note of it and store it as a "knowledge gap" to learn and improve. It is important to address employees in a friendly and compassionate tone, speaking to them in first person terms.

Please feel free to answer any {category} related questions, and do your best to assist employees with questions promptly and professionally."""

    # pprint(prompt)
    response = (
        openai.Completion.create(
            prompt=prompt,
            temperature=0.9,
            max_tokens=500,
            frequency_penalty=0,
            presence_penalty=0,
            top_p=1,
            model=COMPLETIONS_MODEL,
        )['choices'][0]['text']
        .strip(" \n")
        .strip(" Answer:")
        .strip(" \n")
    )
    return response


@app.get("/")
def hello_world():
    return {"message": "Hello World!"}


@app.post("/api/v1/generate-response")
async def generate(payload: Payload):
    DF = get_dataframe_from_csv("apps/data", "zendesk_vector_embeddings.csv")

    strings, relatednesses, embedding = strings_ranked_by_relatedness(payload.query, DF, top_n=1)
    for string, relatedness in zip(strings, relatednesses):
        ANSWERS.append(string)
        SCORES.append("%.3f" % relatedness)
        EMBEDDINGS.append(embedding)

    results = pd.DataFrame({"top_answer": ANSWERS, "match_score": SCORES, "embeddings": EMBEDDINGS})
    results.head()
    save_dataframe_to_csv(results, f"data/{get_date_string()}/", "zendesk_query_embedding.csv")

    record = results.iloc[0]
    response = generate_gpt_opt_response(record, payload.category, payload.company)
    return {"message": response}


if __name__ == '__main__':
    uvicorn.run(app, port=8080, host='127.0.0.1')
