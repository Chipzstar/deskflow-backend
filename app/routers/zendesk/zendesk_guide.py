import os
from pprint import pprint

import pinecone
from fastapi import APIRouter
from zenpy import Zenpy

from app.utils.helpers import border_line
from app.utils.types import ZendeskKBPayload, DeleteKBPayload
from app.utils.zendesk import (
    fetch_zendesk_sections,
    fetch_zendesk_articles_by_section,
    clean_up_text,
    print_example_data,
    calculate_embeddings,
    store_embeddings_into_pinecone,
)

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]

router = APIRouter()


@router.post("/knowledge-base")
def integrate_kb(payload: ZendeskKBPayload):
    # Configure Zendesk API config
    # Zenpy accepts an API token
    border_line()
    pprint(payload)
    creds = {
        "oauth_token": payload.token,
        "subdomain": payload.subdomain,
    }

    zenpy_client = Zenpy(**creds)
    article_sections = fetch_zendesk_sections(zenpy_client)
    articles = fetch_zendesk_articles_by_section(zenpy_client, article_sections)
    # create_txt_knowledge_base(articles, f"{os.getcwd()}/app/knowledge_base")
    # split each document/article into chunks short enough to be read.
    cleaned_articles = clean_up_text(articles)
    print_example_data(cleaned_articles)

    # calculate embeddings
    df, embeddings = calculate_embeddings(cleaned_articles)
    print(df.count())

    # save document chunks and knowledge base embeddings to CSV file for local checking
    # save_dataframe_to_csv(df, f"data/{get_date_string()}", "zendesk_vector_embeddings.csv")

    # Initialise pinecone client with valid API key and environment
    pinecone.init(api_key=PINECONE_API_KEY, environment="us-west1-gcp-free")
    # Connect to the "Alfred" index
    index = pinecone.Index("alfred")
    # Insert the vector embeddings into the index
    store_embeddings_into_pinecone(df, index, payload.slug)
    return {"status": "COMPLETE"}


@router.delete("/knowledge-base")
def delete_kb(payload: DeleteKBPayload):
    pinecone.init(api_key=PINECONE_API_KEY, environment="us-west1-gcp-free"),
    # Connect to the "Alfred" index,
    index = pinecone.Index("alfred")
    index_stats = index.describe_index_stats()
    # extract the total_vector_count
    num_vectors = int(index_stats["namespaces"][payload.slug]["vector_count"])
    # Use vector count to fetch all vectors in the index
    ids = [str(x) for x in range(0, num_vectors)]
    index.delete(ids=ids, namespace=payload.slug)
    return {"status": "Success", "message": f"Vectors deleted for namespace {payload.slug}!"}
