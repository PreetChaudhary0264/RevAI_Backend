from flask import Flask, render_template, request, jsonify
from flask_cors import CORS, cross_origin
import backend

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)  # global fallback

@app.route("/")
@cross_origin()
def home():
    return "your backend is running :)"

@app.route("/test", methods=["GET"])
@cross_origin()
def test():
    return jsonify({
        "status": "success",
        "message": "Flask app is live and responding!"
    })

@app.route("/review", methods=["POST"])
@cross_origin()   # very important for POST routes
def review():
    print("Reached backend.review_repository()")
    data = request.get_json()
    repo_url = data.get("repo_url")
    pr_number = data.get("pr_number")
    print("PR number received in backend:", pr_number)

    if not repo_url:
        return jsonify({"error": "Missing repo URL"}), 400

    result = backend.review_repository(repo_url, pr_number)
    return jsonify({"review": result})

if __name__ == "__main__":
    app.run(debug=True)

