import os

with open("testing.py", "r") as f:
    lines = f.readlines()

def write_module(filename, start_line, end_line, extra_imports=""):
    with open(filename, "w") as f:
        f.write("from config import *\n")
        if extra_imports:
            f.write(extra_imports + "\n")
        f.write("".join(lines[start_line-1:end_line]))

# database.py: 90 - 562
write_module("database.py", 90, 562)

# exchange.py: 563 - 628
write_module("exchange.py", 563, 628)

# ib_api.py: 629 - 708
write_module("ib_api.py", 629, 708)

# trading_bot.py: 709 - 1994
write_module("trading_bot.py", 709, 1994)

# pdt_protector.py: 1995 - 2052
write_module("pdt_protector.py", 1995, 2052)

# gui.py: 2053 - 3210
extra_gui = '''
from database import DatabaseManager, CSVManager
from exchange import ExchangeRateManager
from ib_api import IBApi
from trading_bot import TradingBot
from pdt_protector import PDTProtector
'''
write_module("gui.py", 2053, 3210, extra_gui)

# main.py: 3211 - EOF
extra_main = '''
from gui import TradingApp
'''
write_module("main.py", 3211, len(lines), extra_main)

print("Files successfully split.")
