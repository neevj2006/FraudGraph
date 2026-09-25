import json
from pathlib import Path

from services.api.main import create_app

Path("docs").mkdir(exist_ok=True)
Path("docs/openapi.json").write_text(json.dumps(create_app().openapi(), indent=2), encoding="utf-8")
