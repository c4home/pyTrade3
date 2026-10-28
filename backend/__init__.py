import os
import sys

# Ensure project root, backend, and frontend are on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, ".."))
_frontend_dir = os.path.join(_project_root, "frontend")
_services_dir = os.path.join(_current_dir, "services")

for _p in (_project_root, _current_dir, _services_dir, _frontend_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)
