from flask import Flask

from server.config import WEB_ROOT
from server.routes import register_routes


app = Flask(__name__, static_folder=str(WEB_ROOT), static_url_path="")
register_routes(app)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
