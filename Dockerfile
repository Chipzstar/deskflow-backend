#FROM ubuntu
#
## Install Doppler CLI
#RUN apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg && \
#    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
#    echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
#    apt-get update && \
#    apt-get -y install doppler
#
## Fetch and view secrets using "printenv". Testing purposes only!
## Replace "printenv" with the command used to start your app, e.g. "npm", "start"
#CMD ["doppler", "run", "--", "printenv"]

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