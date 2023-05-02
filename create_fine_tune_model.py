import os
import sys
import openai
import json

# Import the Zenpy Class
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket
from pprint import pprint
from time import time, sleep
from datetime import datetime


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        return infile.read()


openai.api_key = open_file("keys/openai_api_key.txt")


def create_openai_FTmodel(dataset, model_engine="davinci", num_epochs=3, batch_size=4):
    openai.FineTune.create(
        {
            dataset: dataset,
            model_engine: model_engine,
        }
    )


if __name__ == "__main__":
    # total arguments
    n = len(sys.argv)
    print("Total arguments passed:", n)

    # Arguments passed
    print("\nName of Python script:", sys.argv[0])

    args = sys.argv[1:]

    model_name = args[0]
