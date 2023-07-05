#!/bin/bash
export DOPPLER_TOKEN="$(doppler configs tokens create deskflow-docker -p deskflow-backend -c dev_docker --plain --max-age 1m)"
doppler run \
  --mount docker-compose.yml \
  --mount-template doppler-docker-compose.yml \
  -- cat docker-compose.yml
