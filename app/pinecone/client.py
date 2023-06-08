import os
import pinecone

PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]


class Pinecone(object):
    def __init__(self):
        pinecone.init(api_key=PINECONE_API_KEY, environment="us-west1-gcp-free")
        # Connect to the "Alfred" index
        self.pinecone = pinecone

    def index(self, index_name):
        return self.pinecone.Index(index_name)
