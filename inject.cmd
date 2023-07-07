#!/bin/bash
set DOPPLER_TOKEN="$(doppler configs tokens create deskflow-docker -p deskflow-backend -c dev_docker --plain --max-age 1m)"
doppler secrets substitute doppler-docker-compose-v2.yml --output docker-compose.yml