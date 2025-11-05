from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from concurrent.futures import ThreadPoolExecutor
import requests
import time
import os

load_dotenv()

model = ChatGoogleGenerativeAI(
    model='gemini-2.5-flash-lite',
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# def fetch_repo_content(owner, repo_name, path=""):
#     url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
#     headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
#     response = requests.get(url, headers=headers)
#     response.raise_for_status()
#     return response.json()

def fetch_all_files(owner, repo_name):
    """
    Fetch all code files (.py, .js, .jsx, .ts, .tsx, .java, .cpp) from a GitHub repo,
    including nested directories, using the correct default branch.
    """
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    # Step 1: Detect default branch
    repo_info_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    repo_info_resp = requests.get(repo_info_url, headers=headers)
    repo_info_resp.raise_for_status()
    default_branch = repo_info_resp.json().get("default_branch", "main")

    # Step 2: Fetch the full tree recursively
    tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/{default_branch}?recursive=1"
    tree_resp = requests.get(tree_url, headers=headers)
    tree_resp.raise_for_status()
    tree_data = tree_resp.json().get("tree", [])

    files = []
    for item in tree_data:
        if (
            item["type"] == "blob"
            and item["path"].endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cpp"))
        ):
            download_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{default_branch}/{item['path']}"
            files.append({
                "name": os.path.basename(item["path"]),
                "path": item["path"],
                "download_url": download_url,
                "type": "file"
            })

    print(f"[INFO] Found {len(files)} code files in branch '{default_branch}'")
    return files


def download_url(file_info):
    if file_info["type"] == 'file':
        size = file_info.get("size", 0)  # Default to 0 if size not present
        if size and size > 100_000:  # Skip only if size is known and large
            print(f"Skipping large file: {file_info['name']}")
            return None

        url = file_info["download_url"]
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    return None


import os

# def get_all_code_files(repo_path, exts=(".py", ".js", ".java", ".cpp", ".ts")):
#     code_files = []
#     for root, _, files in os.walk(repo_path):
#         if any(skip in root for skip in ['node_modules', '.git', '__pycache__']):
#             continue
#         for file in files:
#             if file.endswith(exts):
#                 code_files.append(os.path.join(root, file))
#     return code_files


def code_splitter(code, chunk_size=500, chunk_overlap=50):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n"]
    )
    doc = Document(page_content=code)
    return splitter.split_text(doc.page_content)

code_review_prompt = PromptTemplate(
    template="""
           You are a senior code reviewer.

           Review this code snippet from file `{filename}`:

           {code}

           Give short, **point-to-point** feedback in bullet format.
           - Focus ONLY on logic, readability, and performance.
           - Do NOT mention naming or formatting unless it's seriously wrong.
           - Max 5 concise points.
           - If the code is clean, respond with 1 or 2 encouraging lines only.
             """,
    input_variables=["filename", "code"]
)


def process_file(file):
    # Skip irrelevant files
    skip_files = {
        "vite.config.js", "eslint.config.js", "tailwind.config.js",
        "package-lock.json", "yarn.lock", "package.json",
        "README.md", "postcss.config.js"
    }

    if file["name"] in skip_files or file["name"].endswith((".json", ".lock")):
        print(f"Skipping irrelevant file: {file['name']}")
        return None

    content = download_url(file)
    if not content:
        return None

    # Only review supported code types
    if not file["name"].endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cpp")):
        print(f"Skipping unsupported file type: {file['name']}")
        return None

    chunks = [c for c in code_splitter(content) if c.strip()]
    reviews = []
    for chunk in chunks:
        formatted_prompt = code_review_prompt.format(filename=file["name"], code=chunk)
        review = model.invoke(formatted_prompt)
        reviews.append(review.content)
        time.sleep(0.3)  # small pause between Gemini calls

    return {"file": file["name"], "review": "\n".join(reviews)}


def review_repo(owner, repo_name,pr_number=None):
    files = fetch_all_files(owner, repo_name)
    all_reviews = []

    with ThreadPoolExecutor(max_workers=1) as executor:
        results = executor.map(process_file, files)

    for res in results:
        if res:
            all_reviews.append(res)
            print(f"Reviewed {res['file']}")
            # Post comment immediately for each file
            if pr_number:
                comment_body = f"### Review for `{res['file']}`\n{res['review']}"
                post_pr_comment(owner, repo_name, pr_number, comment_body, GITHUB_TOKEN)
    return all_reviews


def post_pr_comment(owner, repo, pr_number, body, token):
    import requests
    
    print("function which adds Comments on github reached")
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",  #  use Bearer instead of 'token'
        "Accept": "application/vnd.github+json"
    }
    data = {"body": body}

    r = requests.post(url, headers=headers, json=data)
    print("GitHub API response:", r.status_code, r.text)  # 👀 See what GitHub says

    if r.status_code == 201:
        print(f"Comment posted on PR #{pr_number}")
    else:
        print(f"Failed to post comment on PR #{pr_number}")
    return r


def get_latest_pr_number(owner, repo):
    """Fetches the latest open pull request number."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&sort=created&direction=desc"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    prs = response.json()
    if prs:
        latest_pr = prs[0]
        print(f"Latest PR found: #{latest_pr['number']}")
        return latest_pr["number"]
    print(" No open PRs found.")
    return None


def review_repository(repo_url,pr_number=None):
    try:
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        
        if not pr_number:
            pr_number = get_latest_pr_number(owner, repo)

        print("PR number being used for review:", pr_number)

        # print(f"Reviewing repository: {owner}/{repo}...")
        result = review_repo(owner, repo,pr_number)
        return result
    except Exception as e:
        return {"error": str(e)}
