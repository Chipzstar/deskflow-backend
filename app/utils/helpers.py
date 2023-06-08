import os
import re
from datetime import datetime
from typing import List, Dict
from app.pinecone.client import Pinecone
import pandas as pd

ONE_DAY_IN_SECONDS = 60 * 60 * 24
ONE_HOUR_IN_SECONDS = 60 * 60


def border_asterisk():
    print("* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *")


def border_line():
    print("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -")


def border_equals():
    print("= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =")


def validate_ticket_object(ticket_dict):
    if not isinstance(ticket_dict, dict):
        print("Step 1: Object is not a dictionary")
        return False
    if "ticket" not in ticket_dict:
        print("Step 2: 'ticket' key not found in dictionary")
        return False
    ticket = ticket_dict["ticket"]
    if not isinstance(ticket, dict):
        print("Step 3: 'ticket' value is not a dictionary")
        return False
    if "comment" not in ticket:
        print("Step 4: 'comment' key not found in 'ticket' dictionary")
        return False
    comment = ticket["comment"]
    if not isinstance(comment, dict):
        print("Step 5: 'comment' value is not a dictionary")
        return False
    if "body" not in comment:
        print("Step 6: 'body' key not found in 'comment' dictionary")
        return False
    if not isinstance(comment["body"], str):
        print("Step 7: 'body' value is not a string")
        return False
    if "priority" not in ticket:
        print("Step 8: 'priority' key not found in 'ticket' dictionary")
        return False
    if not isinstance(ticket["priority"], str):
        print("Step 9: 'priority' value is not a string")
        return False
    if "subject" not in ticket:
        print("Step 10: 'subject' key not found in 'ticket' dictionary")
        return False
    if not isinstance(ticket["subject"], str):
        print("Step 11: 'subject' value is not a string")
        return False
    return True


def remove_custom_delimiters(input_str, start_delim='<@', end_delim='>'):
    pattern = re.escape(start_delim) + r'.*?' + re.escape(end_delim)
    output_str = re.sub(pattern, '', input_str)
    return output_str


def get_date_string(date_format: str = "%Y-%m-%dT%H-%M-%S"):
    return datetime.now().strftime(date_format)


def get_dataframe_from_csv(path: str, filename) -> pd.DataFrame:
    df = pd.read_csv(
        f"{path}/{filename}",
        dtype={'title': str, 'content': str, 'embedding': str},
    )
    return df


def get_vector_embeddings_from_pinecone(index_name: str, namespace: str = "chipzstar.dev@googlemail.com"):
    titles = []
    content = []
    categories = []
    embeddings = []
    p = Pinecone()
    # Connect to the index <INDEX_NAME> provided
    index = p.index(index_name)
    # describe the pincone index
    index_stats = index.describe_index_stats()
    # extract the total_vector_count
    num_vectors = int(index_stats["total_vector_count"])
    # Use vector count to fetch all vectors in the index
    ids = [str(x) for x in range(0, 38)]
    vectors = (index.fetch(ids=ids, namespace=namespace))["vectors"]
    # Keys = list(vectors.keys())
    # Keys.sort(key=int)
    # iterate over each vector space and append to pandas dataframe
    for i, (k, v) in enumerate(sorted(vectors.items(), key=lambda item: int(item[0]))):
        titles.append(v["metadata"]["title"])
        content.append(v["metadata"]["content"])
        categories.append(v["metadata"]["category"])
        embeddings.append(v["values"])
    return pd.DataFrame({"titles": titles, "content": content, "categories": categories, "embedding": embeddings})


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


def check_reply_requires_action(reply: str, messages: List[Dict[str, str]]):
    is_knowledge_gap = "information is not provided within the company’s knowledge base"
    is_zendesk_ticket = "create a ticket on Zendesk"
    is_contact_support = "ask HR/IT"
    hints = [is_knowledge_gap, is_zendesk_ticket, is_contact_support]
    if (is_zendesk_ticket.lower() in reply.lower()) or (is_contact_support.lower() in reply.lower()):
        return True
    else:
        return False


def check_can_create_ticket(reply: str, messages: List[Dict[str, str]]):
    ticket_hints = ["SUBJECT:", "BODY:", "PRIORITY:"]
    general_hints = ["Thank you for confirming", "I have created a Zendesk ticket"]
    # for hint in ticket_hints:
    #     if hint.lower() not in reply.lower():
    #         return False
    for hint in general_hints:
        if hint.lower() in reply.lower():
            return True
    return False
