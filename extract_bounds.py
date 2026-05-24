import re

with open("testing.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith("class ") or "======" in line or line.startswith("def main"):
        print(f"Line {i+1}: {line.strip()}")
