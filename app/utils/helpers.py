import os
from datetime import datetime
import pandas as pd


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
