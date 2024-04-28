from datetime import datetime

import requests
import config

PROMETHEUS_BASE = f"{config.PROMETHEUS_ROOT}/api/v1"

# NOTE: Maybe should integrate valkey here to save on
# NOTE: requests to prometheus here?

def is_prometheus_active():
    if config.PROMETHEUS_ROOT == None or config.PROMETHEUS_ROOT.strip() == "":
        return False
    return True

# All functions below assume the calling context has already
# checked that prometheus is active

def get_request_count():
    """
    Returns the number of requests made to the app
    """
    req = requests.get(f"{PROMETHEUS_BASE}/query?query=app_request_count")
    if req.ok:
        data = req.json()
        if data["status"] == "success":
            return data["data"]["result"][0]["value"][1]
    return None

def get_request_count_history(start, end):
    """
    Returns the number of requests made to the app
    """
    if isinstance(start, datetime):
        start = int(start.timestamp())
    if isinstance(end, datetime):
        end = int(end.timestamp())
    req = requests.get(f"{PROMETHEUS_BASE}/query_range?query=app_request_count&start={start}&end={end}&step=1")
    if req.ok:
        data = req.json()
        if data["status"] == "success":
            return data["data"]["result"][0]["values"]
    return None

def get_request_latency():
    """
    Returns the average request latency in seconds
    """
    req = requests.get(f"{PROMETHEUS_BASE}/query?query=app_request_latency_seconds")
    if req.ok:
        data = req.json()
        if data["status"] == "success":
            return data["data"]["result"][0]["value"][1]
    return None

def get_request_latency_history(start, end):
    """
    Returns the average request latency in seconds
    """
    if isinstance(start, datetime):
        start = int(start.timestamp())
    if isinstance(end, datetime):
        end = int(end.timestamp())
    req = requests.get(f"{PROMETHEUS_BASE}/query_range?query=app_request_latency_seconds&start={start}&end={end}&step=1")
    if req.ok:
        data = req.json()
        if data["status"] == "success":
            return data["data"]["result"][0]["values"]
    return None

def get_bot_latency():
    """
    Returns the average bot latency in seconds
    """
    req = requests.get(f"{PROMETHEUS_BASE}/query?query=bot_latency_seconds")
    if req.ok:
        data = req.json()
        if data["status"] == "success":
            return data["data"]["result"][0]["value"][1]
    return None

def get_bot_latency_history(start, end):
    """
    Returns the average bot latency in seconds
    """
    if isinstance(start, datetime):
        start = int(start.timestamp())
    if isinstance(end, datetime):
        end = int(end.timestamp())
    req = requests.get(f"{PROMETHEUS_BASE}/query_range?query=bot_latency_seconds&start={start}&end={end}&step=1")
    if req.ok:
        data = req.json()
        if data["status"] == "success":
            return data["data"]["result"][0]["values"]
    return None