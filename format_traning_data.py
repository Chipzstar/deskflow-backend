import os
import json
# Import the Zenpy Class
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket
from pprint import pprint
from time import time, sleep
from datetime import datetime

PROMPT_SEPARATOR = "\n\n###\n\n"
STOP_SEQUENCE = "END"

# Zenpy accepts an API token
creds = {
    'email': 'chisom@exam-genius.com',
    'token': '1ASu216KqW6p0BHrBIOSAYaBlax2NmHvRu5rCAAk',
    'subdomain': 'omnicentra'
}

# Default
zenpy_client = Zenpy(**creds)

src_dir = "finetuning/"


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        return infile.read()


# def fetch_all_categories():
#     categories = zenpy_client.help_center.categories()
#     for category in categories:
#         pass

def get_date_string():
    return datetime.now().strftime('%Y-%m-%dT%H-%M-%S')

def fetch_zendesk_sections():
    section_ids = []
    sections = zenpy_client.help_center.sections()
    for section in sections:
        section_ids.append(section.id)
        pass
    return section_ids


def fetch_all_zendesk_articles(sections):
    my_articles = []
    for section_id in sections:
        articles = zenpy_client.help_center.articles(section=section_id)
        for article in articles:
            # pprint("--------------------------------------------------------------------------------------------------")
            pprint(article)
            pprint("--------------------------------------------------------------------------------------------------")
            my_articles.append((article.title, article.body))
            pass
    return my_articles


def fetch_zendesk_articles_by_section():
    sections = zenpy_client.help_center.sections()
    for section in sections:
        articles = zenpy_client.help_center.sections.articles(section=section)
        for article in articles:
            pprint(article)
            pass


def create_txt_knowledge_base(articles):
    if not os.path.exists("knowledge_base"):
        os.mkdir("knowledge_base")

    with open(f"knowledge_base/base_{get_date_string()}.txt", 'w') as file:
        for article in articles:
            file.write(article[0] + "\n" + article[1] + "\n\n")
            pass
    pass


def save_to_file(data, filepath, filename):
    if not os.path.exists(filepath):
        os.mkdir(filepath)

    with open(f"{filepath}/{filename}", "w") as outfile:
        for i in data:
            json.dump(i, outfile)
            outfile.write("\n")


if __name__ == '__main__':
    SECTIONS = fetch_zendesk_sections()
    print(SECTIONS)
    ARTICLES = fetch_all_zendesk_articles(SECTIONS)
    # for debug purposes and verifying that the knowledge base is fetched is correct
    create_txt_knowledge_base(ARTICLES)
    JSONL = list()
    for article in ARTICLES:
        prompt = f"{article[0]}{PROMPT_SEPARATOR}"
        completion = f"{article[1]}{STOP_SEQUENCE}"
        data = {'prompt': prompt, 'completion': completion}
        JSONL.append(data)

    save_to_file(JSONL, "finetuning", f"alfred_{get_date_string()}.jsonl")

