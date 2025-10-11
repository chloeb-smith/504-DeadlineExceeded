import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me")

    CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGIN", "http://localhost:5173")}},
         supports_credentials=True)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/hello")
    def hello():
        return jsonify({"message": "Hello from Flask API"})

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
