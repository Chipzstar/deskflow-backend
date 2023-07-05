#!/bin/bash
export DOPPLER_TOKEN="$(doppler configs tokens create deskflow-docker -p deskflow-backend -c dev --plain --max-age 1m)"
doppler run -- docker-compose build && docker-compose up