import os
import openai
from time import time, sleep
import requests


# See PyCharm help at https://www.jetbrains.com/help/pycharm/


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        return infile.read()


openai.api_key = open_file("keys/openai_api_key.txt")


def gpt3_completion(prompt):
    return None


def fine_tune_model(
    prompt, dataset, model_engine="davinci", num_epochs=3, batch_size=4
):
    headers = {
        "Content - Type": "application / json",
        "Authorization": f"Bearer {openai.api_key}",
    }

    data = {
        "model": f"{model_engine} - 0",
        "dataset": dataset,
        "prompt": prompt,
        "num_epochs": num_epochs,
        "batch_size": batch_size,
    }

    url = "https: // api.openai.com / v1 / fine - tunes"
    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200:
        raise ValueError("Failed to fine - tune the model.")

        # Get the ID of the fine-tuned model
        model_id = response.json()["model_id"]
        return model_id


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    fine_tune_model("")
