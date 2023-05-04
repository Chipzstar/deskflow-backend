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

from numpy import float64
from tqdm.auto import tqdm  # this is our progress bar
from scipy import spatial  # for calculating vector similarities for search
import typing  # for type hints
from typing import List, Dict, Literal, Optional, Tuple, Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel

openai.organization = os.environ["OPENAI_ORG_ID"]
openai.api_key = os.environ["OPENAI_API_KEY"]

# DECLARE GLOBAL VARIABLES #
EMBEDDING_MODEL = "text-embedding-ada-002"  # OpenAI's best embeddings as of Apr 2023
MAX_INPUT_TOKENS = 8191
COMPLETIONS_MODEL = "text-davinci-003"
CHAT_COMPLETIONS_MODEL = "gpt-3.5-turbo"
BATCH_SIZE = 1000  # you can submit up to 2048 embedding inputs per request
SCORES = []
ANSWERS = []
EMBEDDINGS = []


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
    history: Optional[List[Dict[str, str]]] = []
    company: Optional[str] = "Omnicentra"


app = FastAPI()

origins = ["*", "http://localhost", "http://localhost:4200", "https://deskflow-nine.vercel.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def num_tokens_from_text(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def get_date_string():
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def get_dataframe_from_csv(path: str, filename) -> pd.DataFrame:
    df = pd.read_csv(
        f"{path}/{filename}",
        dtype={'title': str, 'content': str, 'embedding': str},
    )
    return df


def save_dataframe_to_csv(df: pd.DataFrame, path: str, filename: str):
    if not os.path.exists(path):
        os.mkdir(path)
        print(f"Created {path}")
    df.to_csv(f"{path}/{filename}", index=False)


def convert_csv_embeddings_to_floats(embeddings: str) -> list[float]:
    str_arr = embeddings.replace("[", "").replace("]", "")
    floats_list = [float(item) for item in str_arr.split(",")]
    # print(type(floats_list))
    # print(np.array(floats_list).dtype)
    return floats_list


# search function
async def strings_ranked_by_relatedness(
    query: str, df: pd.DataFrame, relatedness_fn=lambda x, y: 1 - spatial.distance.cosine(x, y), top_n: int = 100
) -> tuple[list[str], list[float]]:
    """Returns a list of strings and relatednesses, sorted from most related to least."""
    query_embedding_response = openai.Embedding.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    query_embedding = query_embedding_response["data"][0]["embedding"]
    strings_and_relatednesses = []
    for i, row in df.iterrows():
        knowledge_base_embedding = convert_csv_embeddings_to_floats(row["embedding"])
        item = row["content"], relatedness_fn(np.array(query_embedding), knowledge_base_embedding)
        strings_and_relatednesses.append(item)
    strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)
    strings, relatednesses = zip(*strings_and_relatednesses)
    return strings[:top_n], relatednesses[:top_n], query_embedding


# 7. Use Text ADA Embedding model to generate user-friendly answers to the query
async def generate_gpt_opt_response(
    question: str,
    record: pd.Series,
    company: str = "Omnicentra",
    description: str = "an AI software company",
):
    context = record.top_answer
    prompt = f"""Name: Alfred

"Answer the following question by rephrasing the context below"
Context:
{context}

Question:
{question}

You are an AI-powered assistant designed to help employees with HR/IT questions at {company}. You have been programmed to provide fast and accurate solutions to their inquiries. As an AI, you do not have a gender, age, sexual orientation or human race.

As an experienced assistant, you can create Zendesk tickets and forward complex inquiries to the appropriate person. If you are unable to provide an answer, you will respond by saying "I don't know, would you like me to create a ticket on Zendesk or ask HR or IT?" and follow the steps accordingly based on their response.

If a question is outside your scope, you will make a note of it and store it as a "knowledge gap" to learn and improve. It is important to address employees in a friendly and compassionate tone, speaking to them in first person terms.

Please feel free to answer any HR/IT related questions, and do your best to assist employees with questions promptly and professionally. Do not include the question in your response."""

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


def query_message(query: str, company: str, content: str, token_budget: int) -> str:
    """Return a message for GPT, with relevant source texts pulled from a dataframe."""
    introduction = f"""You are an AI-powered assistant designed to help employees with HR and IT questions at {company}. You have been programmed to provide fast and accurate solutions to their inquiries. As an AI, you do not have a gender, age, sexual orientation or human race.

As an experienced assistant, you can create Zendesk tickets and forward complex inquiries to the appropriate person. If the question asked is not in the context given to you or the context does not answer the question properly, you will respond apologetically saying something along the lines of "this information is not provided within the company’s knowledge base, would you like me to create a ticket on Zendesk or ask HR/IT?" and follow the steps accordingly based on their response.

If a question is outside your scope, you will make a note of it and store it as a "knowledge gap" to learn and improve. It is important to address employees in a friendly and compassionate tone, speaking to them in first person terms.

Please feel free to answer any HR or IT related questions."""
    question = f"\n\nQuestion: {query}"
    message = introduction
    context = f'\n\nContext:\n"""\n{content}\n"""'
    num_tokens = num_tokens_from_text(message + context + question)
    if num_tokens > token_budget:
        print(f"Question too long: {num_tokens} tokens")
    else:
        message += context

    return message + question


async def generate_gpt_chat_response(
    question: str,
    record: pd.Series,
    company: str = "Omnicentra",
    system_message: str = f"Your name is Alfred. You are a helpful assistant that answers HR and IT questions at Omnicentra",
):
    message = query_message(question, company, record.top_answer, MAX_INPUT_TOKENS)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": message},
    ]
    response = openai.ChatCompletion.create(model=CHAT_COMPLETIONS_MODEL, messages=messages, temperature=0)
    sanitized_response = response['choices'][0]['message']['content'].strip(" \n").strip(" \n")
    messages.append({"role": "assistant", "content": sanitized_response})
    return sanitized_response, messages


async def continue_chat_response(
    question: str,
    messages: List[Dict[str, str]],
):
    message = Message(role="user", content=question)
    print("*" * 100)
    print(message.to_dict())
    print("*" * 100)
    messages.append(message.to_dict())
    response = openai.ChatCompletion.create(model=CHAT_COMPLETIONS_MODEL, messages=messages, temperature=0)
    sanitized_response = response['choices'][0]['message']['content'].strip(" \n").strip(" \n")
    messages.append({"role": "assistant", "content": sanitized_response})
    return sanitized_response, messages


@app.get("/")
def hello_world():
    return {"message": "Hello World!"}


@app.get("/cwd")
def get_cwd():
    return {"cwd": os.getcwd()}


# @app.post("/api/v1/generate-response")
# async def generate(payload: Payload):
#     print(payload)
#     DF = get_dataframe_from_csv(f"{os.getcwd()}/app/data", "zendesk_vector_embeddings.csv")
#     strings, relatednesses, embedding = await strings_ranked_by_relatedness(payload.query, DF, top_n=1)
#     for string, relatedness in zip(strings, relatednesses):
#         ANSWERS.append(string)
#         SCORES.append("%.3f" % relatedness)
#         EMBEDDINGS.append(embedding)
#
#     results = pd.DataFrame({"top_answer": ANSWERS, "match_score": SCORES, "embeddings": EMBEDDINGS})
#     record = results.iloc[0]
#     response = await generate_gpt_opt_response(payload.query, record, payload.category, payload.company)
#     print(response)
#     return {"reply": response}


@app.post("/api/v1/generate-chat-response")
async def chat(payload: ChatPayload):
    print(payload)
    # download knowledge base embeddings from csv
    DF = get_dataframe_from_csv(f"{os.getcwd()}/app/data", "zendesk_vector_embeddings.csv")
    # create query embedding and fetch relatedness between query and knowledge base embeddings
    strings, relatednesses, embedding = await strings_ranked_by_relatedness(payload.query, DF, top_n=1)
    for string, relatedness in zip(strings, relatednesses):
        ANSWERS.append(string)
        SCORES.append("%.3f" % relatedness)
        EMBEDDINGS.append(embedding)

    # Store answers and relatedness in dataframe
    results = pd.DataFrame({"top_answer": ANSWERS, "match_score": SCORES, "embeddings": EMBEDDINGS})
    record = results.iloc[0]
    print("-" * 50)
    print(record['top_answer'])
    # check if the query is the first question asked Alfred
    if len(payload.history):
        response, messages = await continue_chat_response(payload.query, payload.history)
    else:
        response, messages = await generate_gpt_chat_response(payload.query, record, payload.company)
    print(response)
    return {"reply": response, "messages": messages}


if __name__ == '__main__':
    uvicorn.run(app, port=8080, host='127.0.0.1')
