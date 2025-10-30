from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import backend  # your backend.py file

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/review", methods=["POST"])
def review():
    print("Reached backend.review_repository()")
    data = request.get_json()
    repo_url = data.get("repo_url")
    pr_number = data.get("pr_number") 
    print("PR number received in backend:", pr_number)  #add this

    if not repo_url:
        return jsonify({"error": "Missing repo URL"}), 400

    #call the correct backend function
    result = backend.review_repository(repo_url,pr_number)

    return jsonify({"review": result})

if __name__ == "__main__":
    app.run(debug=True)
