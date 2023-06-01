import os
from pprint import pprint

import pinecone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.utils.types import OAuthPayload
from app.utils.zendesk import fetch_zendesk_sections, fetch_zendesk_articles_by_section, create_txt_knowledge_base, \
    clean_up_text, print_example_data, calculate_embeddings, store_embeddings_into_pinecone

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter()


@router.post("/knowledge-base")
def integrate_kb(db: Session = Depends(get_db)):
    article_sections = fetch_zendesk_sections()
    articles = fetch_zendesk_articles_by_section(article_sections)
    # create_txt_knowledge_base(articles, f"{os.getcwd()}/app/knowledge_base")
    # split each document/article into chunks short enough to be read.
    cleaned_articles = clean_up_text(articles)
    print_example_data(cleaned_articles)

    # calculate embeddings
    df, embeddings = calculate_embeddings(cleaned_articles)
    print(df.count())

    # save document chunks and knowledge base embdeddings to CSV file for local checking
    # save_dataframe_to_csv(df, f"data/{get_date_string()}", "zendesk_vector_embeddings.csv")

    # Initialise pinecone client with valid API key and environment
    pinecone.init(api_key=PINECONE_API_KEY, environment="us-west1-gcp-free")
    # Connect to the "Alfred" index
    index = pinecone.Index("alfred")

    # Insert the vector embeddings into the index
    store_embeddings_into_pinecone(df, index)
    return {"status": "COMPLETE"}


@router.delete("/knowledge-base")
def delete_kb(db: Session = Depends(get_db)):
    pinecone.init(api_key=PINECONE_API_KEY, environment="us-west1-gcp-free"),
    # Connect to the "Alfred" index,
    index = pinecone.Index("alfred")
    index_stats = index.describe_index_stats()
    # extract the total_vector_count
    num_vectors = int(index_stats["total_vector_count"])
    # Use vector count to fetch all vectors in the index
    ids = [str(x) for x in range(0,38)]
    index.delete(ids=ids, namespace="chipzstar.dev@googlemail.com")
    return { "status": "Success", "message": "Vectors deleted!"}
