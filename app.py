import json
import os
import queue
import threading
import uuid
from dataclasses import dataclass, field

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    stream_with_context,
    url_for,
    Response,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# In-memory job store  { job_id: Job }
_jobs: dict[str, "Job"] = {}
_jobs_lock = threading.Lock()


@dataclass
class Job:
    id: str
    status: str = "running"          # running | done | error
    progress: list[str] = field(default_factory=list)
    articles: list[dict] = field(default_factory=list)  # [{topic, path, content}]
    error: str = ""
    usage: dict = field(default_factory=dict)
    _queue: queue.Queue = field(default_factory=queue.Queue)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if not _has_keys():
        return redirect(url_for("setup"))
    return render_template("index.html")


@app.route("/setup", methods=["GET", "POST"])
def setup():
    error = ""
    if request.method == "POST":
        x_token = request.form.get("x_bearer_token", "").strip()
        anthropic_key = request.form.get("anthropic_api_key", "").strip()
        if not x_token or not anthropic_key:
            error = "両方のAPIキーを入力してください。"
        else:
            session["x_bearer_token"] = x_token
            session["anthropic_api_key"] = anthropic_key
            return redirect(url_for("index"))
    return render_template("setup.html", error=error)


@app.route("/generate", methods=["POST"])
def generate():
    if not _has_keys():
        return redirect(url_for("setup"))

    topic = request.form.get("topic", "").strip()
    lang = request.form.get("lang", "ja").strip()
    max_tweets = int(request.form.get("max_tweets", "50"))

    if not topic:
        return render_template("index.html", error="トピックを入力してください。")

    job_id = str(uuid.uuid4())
    job = Job(id=job_id)
    with _jobs_lock:
        _jobs[job_id] = job

    # Build query
    query = f"{topic} -is:retweet"
    if lang:
        query += f" lang:{lang}"

    # Snapshot keys from session before spawning thread
    x_token = session["x_bearer_token"]
    anthropic_key = session["anthropic_api_key"]

    thread = threading.Thread(
        target=_run_pipeline,
        args=(job, query, max_tweets, x_token, anthropic_key),
        daemon=True,
    )
    thread.start()

    return redirect(url_for("progress", job_id=job_id))


@app.route("/progress/<job_id>")
def progress(job_id):
    job = _get_job(job_id)
    if job is None:
        return "ジョブが見つかりません", 404
    return render_template("progress.html", job_id=job_id)


@app.route("/stream/<job_id>")
def stream(job_id):
    """SSE endpoint — pushes progress lines to the browser."""
    job = _get_job(job_id)
    if job is None:
        return "not found", 404

    def generate_events():
        # Replay already-logged messages first
        for msg in job.progress:
            yield f"data: {json.dumps({'msg': msg})}\n\n"

        # Then wait for new messages from the queue
        while True:
            try:
                item = job._queue.get(timeout=30)
            except queue.Empty:
                # Send keepalive
                yield ": keepalive\n\n"
                if job.status != "running":
                    break
                continue

            if item is None:  # sentinel — pipeline finished
                yield f"data: {json.dumps({'done': True, 'status': job.status})}\n\n"
                break
            yield f"data: {json.dumps({'msg': item})}\n\n"

    return Response(
        stream_with_context(generate_events()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/results/<job_id>")
def results(job_id):
    job = _get_job(job_id)
    if job is None:
        return "ジョブが見つかりません", 404
    if job.status == "running":
        return redirect(url_for("progress", job_id=job_id))
    return render_template("results.html", job=job)


# ── Pipeline (runs in background thread) ─────────────────────────────────────

def _run_pipeline(job: Job, query: str, max_tweets: int, x_token: str, anthropic_key: str):
    try:
        from config import Config
        from fetcher.twitter_client import TwitterClient
        from generator.article_writer import ArticleWriter
        from processor.topic_extractor import TopicExtractor
        from processor.tweet_grouper import TweetGrouper
        from utils.file_writer import save_article
        from utils.usage import UsageTracker

        config = Config(
            x_bearer_token=x_token,
            anthropic_api_key=anthropic_key,
            max_tweets=max_tweets,
        )
        tracker = UsageTracker()

        _log(job, f"🔍 X APIでツイートを検索中: {query}")
        tweets = TwitterClient(config, tracker).search_recent(query, max_results=max_tweets)
        if not tweets:
            raise ValueError("一致するツイートが見つかりませんでした。クエリを変えてお試しください。")
        _log(job, f"✅ {len(tweets)} 件のツイートを取得しました")

        _log(job, "🧠 トピックを抽出中…")
        topics = TopicExtractor(config, tracker).extract(tweets)
        if not topics:
            raise ValueError("トピックを抽出できませんでした。")
        _log(job, f"✅ {len(topics)} 個のトピックを抽出: " + "、".join(t.name for t in topics))

        _log(job, "📂 ツイートをトピックに分類中…")
        groups = TweetGrouper(config, tracker).group(tweets, topics)
        _log(job, f"✅ {len(groups)} グループに分類しました")

        writer = ArticleWriter(config, tracker)
        for i, group in enumerate(groups, 1):
            _log(job, f"✍️  [{i}/{len(groups)}] 「{group.topic.name}」の記事を生成中…")
            markdown = writer.generate(group)
            path = save_article(group.topic.name, markdown)
            job.articles.append({
                "topic": group.topic.name,
                "description": group.topic.description,
                "path": str(path),
                "content": markdown,
                "tweet_count": len(group.tweets),
            })
            _log(job, f"✅ 「{group.topic.name}」の記事を保存: {path}")

        job.usage = tracker.to_dict()
        job.status = "done"
        _log(job, f"🎉 完了！{len(job.articles)} 件の記事を生成しました")

    except Exception as e:
        job.status = "error"
        job.error = str(e)
        _log(job, f"❌ エラー: {e}")

    finally:
        job._queue.put(None)  # sentinel


def _log(job: Job, msg: str):
    job.progress.append(msg)
    job._queue.put(msg)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_keys() -> bool:
    return bool(session.get("x_bearer_token") and session.get("anthropic_api_key"))


def _get_job(job_id: str) -> "Job | None":
    with _jobs_lock:
        return _jobs.get(job_id)


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
