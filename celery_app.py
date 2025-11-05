from celery import Celery
from dotenv import load_dotenv
import backend
import os

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL")
celery_app = Celery(
    "revai_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

@celery_app.task(bind=True)
def run_review(self, repo_url, pr_number):
    from backend import fetch_all_files, process_file, post_pr_comment

    try:
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        self.update_state(state="STARTED", meta={"message": "Starting code review..."})

        files = fetch_all_files(owner, repo)
        total = len(files)
        reviewed_files = []

        for idx, file in enumerate(files, start=1):
            self.update_state(state="PROGRESS", meta={
                "message": f"Reviewing file {idx}/{total}: {file['name']}",
                "progress": f"{idx}/{total}"
            })
            print("STATE UPDATE → STARTED")

            result = process_file(file)
            if result:
                reviewed_files.append(result)
                if pr_number:
                    comment_body = f"### Review for `{result['file']}`\n{result['review']}"
                    post_pr_comment(owner, repo, pr_number, comment_body, os.getenv("GITHUB_TOKEN"))

        return {
            "status": "completed",
            "message": " All files reviewed successfully!",
            "result": reviewed_files
        }

    except Exception as e:
     import traceback
     tb = traceback.format_exc()
     print(f"❌ Task failed due to {type(e).__name__}: {e}")
     print(tb)

     failure_info = {
        "status": "failed",
        "message": f"Task failed due to {type(e).__name__}: {e}",
        "exc_type": type(e).__name__,  # Added this line
        "traceback": tb,
     }

     self.update_state(state="FAILURE", meta=failure_info)
     return failure_info



