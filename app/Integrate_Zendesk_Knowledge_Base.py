# imports
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

# Import the Zenpy Class
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket
from pprint import pprint
from scipy import spatial  # for calculating vector similarities for search
import typing  # for type hints


# Install any missing libraries with `pip install` in your terminal. E.g.,
#
# ```zsh
# pip install openai
# ```
#
# (You can also do this in a notebook cell with `!pip install openai`.)
#
# If you install any libraries, be sure to restart the notebook kernel.

# ### Set API key (if needed)
#
# Note that the OpenAI library will try to read your API key from the `OPENAI_API_KEY` environment variable. If you haven't already, set this environment variable by following [these instructions](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety).

# In[2]:


openai.organization = "org-C15lzQ0mQYcGkjGrpiBPk2Hb"
openai.api_key = "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"


# In[3]:


MAX_INPUT_TOKENS = 8191
COMPLETIONS_MODEL = "text-davinci-003"


# ## Configure Zendesk API config
#
# The Zendesk API is configured in the [Zendesk dashboard](https://app.zendesk.com/hc/en-us/articles/360001111134-Zendesk-API-Configuration).

# In[4]:


# Zenpy accepts an API token
creds = {
    "email": "chisom@exam-genius.com",
    "token": "1ASu216KqW6p0BHrBIOSAYaBlax2NmHvRu5rCAAk",
    "subdomain": "omnicentra",
}

# Default
zenpy_client = Zenpy(**creds)


# ## 1. Collect articles
#
# In this example, we'll download a few hundred Wikipedia articles related to the 2022 Winter Olympics.

# In[5]:


def get_date_string():
    return datetime.now().strftime("%Y-%m-%dT")


def fetch_zendesk_sections():
    sections = []
    for section in zenpy_client.help_center.sections():
        sections.append(section)
        pass
    return sections


def fetch_all_zendesk_articles():
    articles = zenpy_client.help_center.articles()
    for article in articles:
        pprint(article)
        pass
    return articles


def fetch_zendesk_articles_by_section(sections):
    my_articles = []
    for _section in sections:
        articles = zenpy_client.help_center.sections.articles(section=_section)
        print(f"Found {len(articles)} articles in section {_section}")
        for article in articles:
            # pprint("--------------------------------------------------------------------------------------------------")
            my_articles.append((article.title, article.body))
            pass
    return my_articles


# ### Fetch All Article sections

# In[6]:


article_sections = fetch_zendesk_sections()
print(article_sections)


# ### Fetch all articles for each section

# In[8]:


articles = fetch_zendesk_articles_by_section(article_sections)
len(articles)


# In[9]:


def create_txt_knowledge_base(articles):
    if not os.path.exists("../knowledge_base"):
        os.mkdir("../knowledge_base")

    with open(f"knowledge_base/base_{get_date_string()}.txt", "w") as file:
        for article in articles:
            file.write(article[0] + "\n" + article[1] + "\n\n")
            pass
    pass


# In[10]:


create_txt_knowledge_base(articles)


# ## 2. Chunk documents
#
# Now that we have our reference documents, we need to prepare them for search.
#
# Because GPT can only read a limited amount of text at once, we'll split each document into chunks short enough to be read.
#
# For this specific example on Wikipedia articles, we'll:
# - Remove all html syntax tags (e.g., \<ref>\, \<div>\), whitespace, and super short sections
# - Clean up the text by removing reference tags (e.g., <ref>), whitespace, and super short sections
# - Split each article into sections
# - Prepend titles and subtitles to each section's text, to help GPT understand the context
# - If a section is long (say, > 1,600 tokens), we'll recursively split it into smaller sections, trying to split along semantic boundaries like paragraphs

# In[11]:


def num_tokens_from_text(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


# In[12]:


def clean_up_text(articles):
    cleaned_articles = []
    for title, body in articles:
        cleaned_body = BeautifulSoup(body, "html.parser").get_text()
        if num_tokens_from_text(title.strip() + cleaned_body.strip()) > MAX_INPUT_TOKENS:
            left = body[:MAX_INPUT_TOKENS]
            right = body[MAX_INPUT_TOKENS:]
            cleaned_articles.append((title, left))
            cleaned_articles.append((title, right))
        else:
            cleaned_articles.append((title, cleaned_body))
    pass
    return cleaned_articles


# In[13]:


CLEANED_ARTICLES = clean_up_text(articles)

# Next, we'll recursively split long sections into smaller sections.
#
# There's no perfect recipe for splitting text into sections.
#
# Some tradeoffs include:
# - Longer sections may be better for questions that require more context
# - Longer sections may be worse for retrieval, as they may have more topics muddled together
# - Shorter sections are better for reducing costs (which are proportional to the number of tokens)
# - Shorter sections allow more sections to be retrieved, which may help with recall
# - Overlapping sections may help prevent answers from being cut by section boundaries
#
# Here, we'll use a simple approach and limit sections to 1,600 tokens each, recursively halving any sections that are too long. To avoid cutting in the middle of useful sentences, we'll split along paragraph boundaries when possible.

# ## 3. Embed document chunks
#
# Now that we've split our library into shorter self-contained strings, we can compute embeddings for each.
#
# (For large embedding jobs, use a script like [api_request_parallel_processor.py](api_request_parallel_processor.py) to parallelize requests while throttling to stay under rate limits.)

# In[15]:


# calculate embeddings
EMBEDDING_MODEL = "text-embedding-ada-002"  # OpenAI's best embeddings as of Apr 2023
BATCH_SIZE = 1000  # you can submit up to 2048 embedding inputs per request


def calculate_embeddings(articles):
    titles = []
    content = []
    embeddings = []
    for batch_start in range(0, len(articles), BATCH_SIZE):
        batch_end = batch_start + BATCH_SIZE
        batch = articles[batch_start:batch_end]
        titles = [article[0] for article in batch]
        content = [article[1] for article in batch]
        batch_text = [title + " " + body for title, body in batch]
        print(f"Batch {batch_start} to {batch_end - 1}")
        response = openai.Embedding.create(model=EMBEDDING_MODEL, input=batch_text)
        for i, be in enumerate(response["data"]):
            assert i == be["index"]  # double check embeddings are in same order as input
        batch_embeddings = [e["embedding"] for e in response["data"]]
        embeddings.extend(batch_embeddings)

    return pd.DataFrame({"titles": titles, "content": content, "embedding": embeddings}), embeddings


# In[16]:


DF, EMBEDDINGS = calculate_embeddings(CLEANED_ARTICLES)


# ## 4. Store document chunks and embeddings
#
# Because this example only uses a few thousand strings, we'll store them in a CSV file.
#
# (For larger datasets, use a vector database, which will be more performant.)

# In[19]:


# save document chunks and embeddings
def save_dataframe_to_csv(df: pd.DataFrame, path: str, filename: str):
    if not os.path.exists(path):
        os.mkdir(path)
        print(f"Created {path}")
    df.to_csv(f"{path}/{filename}", index=False)


# In[20]:


save_dataframe_to_csv(DF, f"data/{get_date_string()}", "zendesk_vector_embeddings.csv")


# ## Store embeddings in Pinecone database

# In[21]:


# Initialise pinecone client with valid API key and environment
import pinecone

pinecone.init(api_key="50f995ae-f134-4a60-8aba-edf67c153790", environment="us-west1-gcp-free")
# Connect to the "Alfred" index
index = pinecone.Index("alfred")


# In[22]:


# Insert the vector embeddings into the index
from tqdm.auto import tqdm  # this is our progress bar


def store_embeddings_into_pinecone(embeddings: np.ndarray, index: pinecone.Index):
    batch_size = 32  # process everything in batches of 32
    for i in tqdm(range(0, len(DF), batch_size)):
        i_end = min(i + batch_size, len(DF))
        batch = DF[i : i + batch_size]
        embeddings_batch = batch["embedding"]
        ids_batch = [str(n) for n in range(i, i_end)]
        # prep metadata and upsert batch
        meta = [{'title': titles, "content": content} for titles, content, embeddings in batch.to_numpy()]
        to_upsert = zip(ids_batch, embeddings_batch, meta)
        print(to_upsert)
        index.upsert(vectors=list(to_upsert))
        # upsert to Pinecone


# In[23]:


store_embeddings_into_pinecone(EMBEDDINGS, index)
