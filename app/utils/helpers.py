import os, re
from datetime import datetime
import pandas as pd


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
