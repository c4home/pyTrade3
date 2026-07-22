import os
import sys
import smtplib
import re
import time
import csv
import threading
import collections
import sqlite3
import logging
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
from contextlib import contextmanager        
from email.mime.text import MIMEText

from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.tag_value import TagValue

from concurrent.futures import ThreadPoolExecutor

load_dotenv()
def _load_env_config():
    """Return a dict with all env vars the app needs."""
    return {
        "IBKR_HOST"        : os.getenv("IBKR_HOST"),
        "IBKR_PORT"        : os.getenv("IBKR_PORT"),
        "IBKR_CLIENT_ID"   : os.getenv("IBKR_CLIENT_ID"),
        "SMTP_SERVER"      : os.getenv("SMTP_SERVER"),
        "SMTP_PORT"        : os.getenv("SMTP_PORT"),
        "SENDER_EMAIL"     : os.getenv("SENDER_EMAIL"),
        "SENDER_EMAIL_PASS": os.getenv("SENDER_EMAIL_PASS"),
        "RECEIVER_EMAIL"   : os.getenv("RECEIVER_EMAIL"),
    }
ENV = _load_env_config()

executor = ThreadPoolExecutor(max_workers=8)

# Configure logging at module level
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler('trading_bot.log')
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

def clean_company_name(name):
    if not name:
        return ""
    name = re.sub(r',\s*(inc|ltd|co|plc|llc|corp|ag|sa|nv|se|group|gmbh|n\.v\.|s\.a\.).*$', '', name, flags=re.IGNORECASE)
    pattern = r'\b(inc|incorporated|corporation|corp|limited|ltd|llc|plc|co|company|holdings|holding|ag|sa|nv|se|gmbh|n\.v\.|s\.a\.|group)\b\.?'
    name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip(' ,.-&')
    return name

def format_currency_short(val, sym="€"):
    if val is None:
        return "--"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1000:
        val_str = f"{abs_val/1000:.1f}k" if abs_val % 1000 != 0 else f"{abs_val/1000:.0f}k"
        return f"{sign}{sym}{val_str}"
    return f"{sign}{sym}{abs_val:.0f}"
