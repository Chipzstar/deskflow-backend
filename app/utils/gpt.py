from pprint import pprint
from typing import List, Dict, TypedDict, NamedTuple
import os, requests, json
import numpy as np
import openai
import pandas as pd
import tiktoken
from openai.embeddings_utils import cosine_similarity, get_embedding
from app.utils.helpers import convert_csv_embeddings_to_floats, validate_ticket_object
from app.utils.types import Message

openai.api_key = os.environ["OPENAI_API_KEY"]
openai.organization = os.environ["OPENAI_ORG_ID"]
zendesk_api_key = os.environ["ZENDESK_API_KEY"]

# DECLARE GLOBAL VARIABLES #
EMBEDDING_MODEL = "text-embedding-ada-002"  # OpenAI's best embeddings as of Apr 2023
MAX_INPUT_TOKENS = 8191
COMPLETIONS_MODEL = "text-davinci-003"
CHAT_COMPLETIONS_MODEL = "gpt-3.5-turbo"
BATCH_SIZE = 1000  # you can submit up to 2048 embedding inputs per request


class Credentials(NamedTuple):
    email: str
    token: str
    subdomain: str


def num_tokens_from_text(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def strings_ranked_by_relatedness(
        query: str, df: pd.DataFrame, relatedness_fn=lambda x, y: cosine_similarity(x, y), top_n: int = 100
) -> tuple[list[str], list[float], list[np.ndarray]]:
    """Returns a list of strings and relatednesses, sorted from most related to least."""
    question_vector = get_embedding(query, EMBEDDING_MODEL)
    strings_and_relatednesses = []
    for i, row in df.iterrows():
        knowledge_base_embedding = convert_csv_embeddings_to_floats(row["embedding"])
        item = (
            row["content"],
            relatedness_fn(np.array(question_vector), knowledge_base_embedding),
            knowledge_base_embedding,
        )
        strings_and_relatednesses.append(item)
    strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)
    strings, relatednesses, embedding = zip(*strings_and_relatednesses)
    return strings[:top_n], relatednesses[:top_n], embedding[:top_n]


async def get_similarities(query: str, df: pd.DataFrame) -> pd.DataFrame:
    SCORES = []
    ANSWERS = []
    EMBEDDINGS = []
    strings, relatednesses, embeddings = strings_ranked_by_relatedness(query, df, top_n=3)
    for string, relatedness, embedding in zip(strings, relatednesses, embeddings):
        ANSWERS.append(string)
        SCORES.append("%.3f" % relatedness)
        EMBEDDINGS.append(embedding)

    results = pd.DataFrame({"answers": ANSWERS, "match_scores": SCORES, "embeddings": EMBEDDINGS})
    return results


def generate_context_array(results: pd.DataFrame) -> str:
    context_array = []
    for i, row in results.iterrows():
        context_array.append(row.answers)

    context = "\n".join(context_array)
    return context


def query_message(query: str, context: str, company: str, token_budget: int, sender_name: str = "Ola") -> str:
    """Return a message for GPT, with relevant source texts pulled from a dataframe."""
    introduction = f"""Your name is Alfred. You are an AI-powered assistant designed to help employees with HR and IT questions at {company}. You have been programmed to provide fast and accurate solutions to their inquiries. As an AI, you do not have a gender, age, sexual orientation or human race.

As an experienced assistant, you can create Zendesk tickets and forward complex inquiries to the appropriate person.

The conversation is between you and {sender_name} and you should first greet them with a phrase like "Hello {sender_name}". When a HR / IT related question is asked by {sender_name}, only use information provided in the context and never use general knowledge. If the question asked is not in the context given to you or the context does not answer the question properly, you will respond apologetically saying something along the lines of "this information is not provided within the company’s knowledge base, would you like me to create a ticket on Zendesk or ask HR/IT?" and follow the steps accordingly based on their response.

For general responses by the user you should answer as a normal human assistant would in a friendly, polite manner. 

If a question is outside your scope, you will make a note of it and store it as a "knowledge gap" to learn and improve. It is important to address employees in a friendly and compassionate tone, speaking to them in first person terms.

Please feel free to answer any HR or IT related questions."""
    question = f"\n\nQuestion: {query}"
    message = introduction
    context = f'\n\nContext:\n"""\n{context}\n"""'
    num_tokens = num_tokens_from_text(message + context + question)
    if num_tokens > token_budget:
        print(f"Question too long: {num_tokens} tokens")
    else:
        message += context

    return message + question


async def generate_gpt_chat_response(
        question: str,
        context: str,
        sender_name: str = "Ola",
        company: str = "Omnicentra",
        system_message: str = f"Your name is Alfred. You are a helpful assistant that answers HR and IT questions at "
                              f"Omnicentra",
):
    message = query_message(question, context, company, MAX_INPUT_TOKENS, sender_name)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": message},
    ]
    response = openai.ChatCompletion.create(model=CHAT_COMPLETIONS_MODEL, messages=messages, temperature=0)
    sanitized_response = response['choices'][0]['message']['content'].strip(" \n").strip(" \n")
    messages.append({"role": "assistant", "content": sanitized_response})
    return sanitized_response, messages


async def continue_chat_response(
        query: str,
        context: str,
        messages: List[Dict[str, str]],
        is_question: False
):
    if is_question:
        message = Message(role="user", content=f"{query}\n\nContext: {context}")
    else:
        message = Message(role="user", content=f"{query}")
    print("*" * 100)
    print(message.to_dict())
    print("*" * 100)
    messages.append(message.to_dict())
    response = openai.ChatCompletion.create(model=CHAT_COMPLETIONS_MODEL, messages=messages, temperature=0)
    sanitized_response = response['choices'][0]['message']['content'].strip(" \n").strip(" \n")
    messages.append({"role": "assistant", "content": sanitized_response})
    return sanitized_response, messages


async def send_zendesk_ticket(query: str, system_message: str = "You are a Zendesk support ticket creator"):
    message = f"""You are an AI assistant that converts customer queries into Zendesk support tickets. 

            For every query, you should understand what the query is about and format the query into the 
            following JSON Zendesk ticket payload: `{{ "ticket": {{ "comment": {{"body": "<BODY>"}}, "priority": "<PRIORITY>", "subject": 
            "<SUBJECT>" }} }}`

            <PRIORITY> = the priority of the ticket (can be one of: low, normal, high, urgent)
            <SUBJECT> = the subject of the ticket
            <BODY> = the full description of the query
            
            Refer to the documentation for more information about how the ticket payload is formatted : https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/#create-ticket
            
            QUERY: {query}
            """
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": message},
    ]

    response = (
        openai.ChatCompletion.create(
            messages=messages,
            temperature=0,
            model=CHAT_COMPLETIONS_MODEL,
        )
    )
    data: Dict = json.loads(response['choices'][0]['message']['content'].replace("`", "").strip())
    is_valid = validate_ticket_object(data)
    if not is_valid:
        print(f"Failed to create ticket using the payload: {data}")
        print(data)
        return None

    creds = Credentials(
        email="chisom.oguibe@googlemail.com",
        token=zendesk_api_key,
        subdomain="secondstechnologies",
    )
    # Set up the authentication credentials
    auth = (creds.email + "/token", creds.token)
    url = f"https://{creds.subdomain}.zendesk.com/api/v2/tickets.json"
    response = requests.post(
        url,
        json=data,
        auth=auth
    )

    # Check the response status code
    if response.status_code == 201:
        print("Ticket created successfully")
        pprint(response.json())
        return response.json()['ticket']
    else:
        print(f"Failed to create ticket: {response.text}")
        return response.text


