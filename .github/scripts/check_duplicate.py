"""
Checks newly opened GitHub issues for semantic duplicates using OpenAI embeddings.
Posts a comment and adds a label if a likely duplicate is found.
"""

import os
import numpy as np
from openai import OpenAI
from github import Github

SIMILARITY_THRESHOLD = 0.88  # tune between 0.85–0.92
MAX_ISSUES_TO_CHECK = 200    # avoid rate limits on large repos
EMBED_MODEL = "text-embedding-3-small"


def embed(client: OpenAI, text: str) -> np.ndarray:
    text = text.strip().replace("\n", " ")[:8000]  # token safety
    response = client.embeddings.create(input=[text], model=EMBED_MODEL)
    return np.array(response.data[0].embedding)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def issue_text(issue) -> str:
    body = issue.body or ""
    return f"{issue.title}\n\n{body}"


def ensure_label(repo, label_name: str, color: str = "cfd3d7"):
    try:
        repo.get_label(label_name)
    except Exception:
        repo.create_label(name=label_name, color=color)


def main():
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    gh = Github(os.environ["GITHUB_TOKEN"])

    repo = gh.get_repo(os.environ["REPO"])
    new_issue_number = int(os.environ["ISSUE_NUMBER"])
    new_issue = repo.get_issue(new_issue_number)

    print(f"Checking issue #{new_issue_number}: {new_issue.title!r}")

    # Fetch open issues excluding the new one
    open_issues = [
        i for i in repo.get_issues(state="open")
        if i.number != new_issue_number and i.pull_request is None
    ][:MAX_ISSUES_TO_CHECK]

    if not open_issues:
        print("No other open issues to compare against.")
        return

    new_vec = embed(openai_client, issue_text(new_issue))

    duplicates = []
    for issue in open_issues:
        vec = embed(openai_client, issue_text(issue))
        score = cosine_similarity(new_vec, vec)
        print(f"  #{issue.number} similarity: {score:.3f} — {issue.title!r}")
        if score >= SIMILARITY_THRESHOLD:
            duplicates.append((score, issue))

    if not duplicates:
        print("No duplicates found.")
        return

    # Sort by similarity descending
    duplicates.sort(key=lambda x: x[0], reverse=True)

    # Build comment
    lines = [
        "**Possible duplicate issue detected** — this issue may already be tracked:\n"
    ]
    for score, issue in duplicates[:5]:
        lines.append(f"- #{issue.number} ({score:.0%} similar): [{issue.title}]({issue.html_url})")
    lines.append(
        "\nIf this is a duplicate, please close this issue and continue the discussion there. "
        "If it's not a duplicate, feel free to ignore this comment."
    )

    comment_body = "\n".join(lines)
    new_issue.create_comment(comment_body)
    print(f"Posted duplicate warning comment on #{new_issue_number}")

    # Add label
    ensure_label(repo, "possible duplicate")
    new_issue.add_to_labels("possible duplicate")
    print("Added 'possible duplicate' label")


if __name__ == "__main__":
    main()
