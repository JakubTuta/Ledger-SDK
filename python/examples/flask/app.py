import os

from flask import Flask, jsonify, request
from ledger import LedgerClient
from ledger.integrations.flask import LedgerMiddleware

app = Flask(__name__)

app.config["LEDGER_CLIENT"] = LedgerClient(
    api_key=os.getenv("LEDGER_API_KEY", "ledger_proj_1_your_api_key"),
    base_url=os.getenv("LEDGER_BASE_URL", "https://ledger-server.jtuta.cloud"),
)

LedgerMiddleware(app, exclude_paths=["/health"])


@app.route("/")
def index():
    return jsonify({"message": "Hello from Ledger Flask Example"})


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy",
            "ledger": app.config["LEDGER_CLIENT"].is_healthy(),
        }
    )


@app.route("/users/<int:user_id>")
def get_user(user_id):
    app.config["LEDGER_CLIENT"].log_info(
        f"Fetching user {user_id}", attributes={"user_id": user_id}
    )
    return jsonify({"user_id": user_id, "name": f"User {user_id}"})


@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    name = data.get("name", "Unknown")
    app.config["LEDGER_CLIENT"].log_info(f"Creating user: {name}", attributes={"name": name})
    return jsonify({"id": 123, "name": name}), 201


@app.route("/posts/<int:post_id>")
def get_post(post_id):
    return jsonify({"post_id": post_id, "title": f"Post {post_id}"})


@app.route("/posts/<int:post_id>/comments/<int:comment_id>")
def get_comment(post_id, comment_id):
    return jsonify(
        {
            "post_id": post_id,
            "comment_id": comment_id,
            "text": f"Comment {comment_id} on post {post_id}",
        }
    )


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Ledger SDK Flask Example")
    print("=" * 60)
    print("Server running on: http://localhost:5000")
    print("=" * 60)
    print("\nExample endpoints:")
    print("  GET  /              - Hello world")
    print("  GET  /health        - Health check (not logged)")
    print("  GET  /users/123     - Get user (with logging)")
    print('  POST /users         - Create user (JSON: {"name": "John"})')
    print("  GET  /posts/456     - Get post")
    print("  GET  /posts/456/comments/789 - Get comment")
    print()

    app.run(debug=True, port=5000)
