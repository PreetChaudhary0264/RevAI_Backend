from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from celery_app import run_review,celery_app  # import the task from celery_app.py
import os

app = Flask(__name__)
CORS(app)  # enable global CORS

@app.route("/")
@cross_origin()
def home():
    return " Your backend is running :)"

@app.route("/test", methods=["GET"])
@cross_origin()
def test():
    return jsonify({
        "status": "success",
        "message": "Flask app is live and responding!"
    })

@app.route("/review", methods=["POST"])
@cross_origin()  # CORS for frontend requests
def review():
    data = request.get_json()
    repo_url = data.get("repo_url")
    pr_number = data.get("pr_number")

    print(" Received review request for:", repo_url, "PR:", pr_number)

    if not repo_url:
        return jsonify({"error": "Missing repo URL"}), 400

    #  Queue the background task
    task = run_review.delay(repo_url, pr_number)

    return jsonify({
        "status": "queued",
        "task_id": task.id,
        "message": "Your PR review has been started in the background."
    }), 202

@app.route("/status/<task_id>", methods=["GET"])
@cross_origin()
def check_status(task_id):
    task = celery_app.AsyncResult(task_id)
    info = task.info if isinstance(task.info, dict) else {}
    
    print(f"[STATUS] Task {task_id} -> {task.state}, info: {info}")


    if task.state == "PENDING":
        response = {"status": "pending"}
    elif task.state == "PROGRESS":
        response = {
            "status": "in_progress",
            "message": info.get("message", "Working..."),
            "progress": info.get("progress", "0/0")
        }
    elif task.state == "SUCCESS":
        response = {
            "status": "completed",
            "message": info.get("message", "Review completed successfully."),
            "result": info.get("result")
        }
    elif task.state == "FAILURE":
        response = {
            "status": "failed",
            "message": str(task.info)
        }
    else:
        response = {
            "status": str(task.state),
            "message": info.get("message", "Review in progress...")
        }

    return jsonify(response)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
