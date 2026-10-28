import os
import sys

# Ensure project root, backend, and frontend are on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, ".."))
_backend_dir = os.path.join(_project_root, "backend")

for _p in (_project_root, _backend_dir, _current_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)
