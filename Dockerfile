FROM python:3.11-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

# Opt out of 'Running pip as the 'root' user' warning message
ENV PIP_ROOT_USER_ACTION=ignore

RUN useradd -ms /bin/bash celery

WORKDIR /code

RUN pip install --upgrade pip

COPY requirements.txt /code/requirements.txt

RUN pip install --root-user-action=ignore --no-cache-dir --upgrade -r /code/requirements.txt

COPY prisma /code/prisma

RUN prisma py generate

COPY ./app /code/app

RUN chown -R celery:celery /code

EXPOSE 8000