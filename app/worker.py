from dotenv import load_dotenv

load_dotenv()

import ssl
import os
import logging
import time
from celery import Celery
from redis.exceptions import ResponseError, RedisError
from app.redis.client import Redis

logger = logging.getLogger(__name__)

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")
print(os.environ.get("DOPPLER_ENVIRONMENT"))

if not os.environ.get("DOPPLER_ENVIRONMENT") == "dev":
    celery.conf.redis_backend_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    celery.conf.broker_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
celery.flower_unauthenticated_api = True


@celery.task()
def adding_task(x, y):
    return x + y


@celery.task()
def create_task(convo_id, ttl, debug=False):
    time.sleep(30 if debug else ttl)
    r = Redis()
    try:
        convo = r.get_value(convo_id)
        print(convo)
        return convo
    except (ResponseError, RedisError) as e:
        logger.error(f"Error retrieving conversation from Redis: {e}")
        return None  # or any other default value you want to return
