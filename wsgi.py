import eventlet
eventlet.monkey_patch()

# eventlet monkey_patch is handled by gunicorn worker class if -k eventlet is used.
# Manual patching here can cause RuntimeError in the master process on some Python versions (like 3.13).

from app import create_app  # noqa
from dotenv import load_dotenv  # noqa
import os  # noqa

load_dotenv()

app = create_app(os.getenv("FLASK_ENV", "production"))
