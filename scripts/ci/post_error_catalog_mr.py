"""Keep a GitLab merge request's error-number threads in step with the current conflicts.

Error numbers are handed out per branch, so two open MRs can both take the next free number and
only find out when the second of them merges. This job runs on the rebased branch -- the rebase
is what brings the already-merged call sites into the tree -- asks ``plan_renumbering`` which of
the colliding sites this branch owns, and mirrors that answer into review threads:

* an unchanged conflict keeps its thread, untouched and with no new notification;
* a conflict whose suggested number moved has its note edited in place;
* a conflict that is gone has its thread deleted, or resolved if somebody replied to it;
* a new conflict opens a thread on the ``error_number=`` line, carrying a suggestion the author
  can apply from the UI.

Needs a full clone (``GIT_DEPTH: "0"``) so the target branch resolves, and a technical-user
token with ``api`` scope. Reads the working tree; never writes to it. Stdlib only.
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flync_cli.utils.error_renumber import REPO_ROOT, Renumbering, RenumberPlan, plan_renumbering, resolve_base_ref
from flync_cli.utils.errors import CATALOG_PATH, ErrorRecord, scan_error_calls

MARKER = "flync-error-catalog"
KEY_PATTERN = re.compile(rf"<!--\s*{MARKER}:key=(\S+)\s*-->")
UNFIXABLE_KEY = "needs-a-human"
TIMEOUT = 30


@dataclass(frozen=True)
class Comment(object):
    """One thread the bot wants the MR to carry, identified by a key that survives a force-push."""

    key: str
    body: str
    position: dict | None = None


@dataclass(frozen=True)
class Thread(object):
    """One bot-authored thread as the MR currently carries it."""

    key: str
    discussion_id: str
    note_id: int
    body: str
    anchor: tuple[str, int] | None  # where the diff still holds it, or None if it never had one
    answered: bool  # somebody other than the bot has replied in it


class MergeRequest(object):
    """The slice of the GitLab API this bot talks to."""

    def __init__(self, api_url: str, token: str, project: str, iid: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.path = f"/projects/{quote(project, safe='')}/merge_requests/{iid}"

    def _call(self, method: str, path: str, payload: dict | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"PRIVATE-TOKEN": self.token}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.api_url}{path}", data=data, headers=headers, method=method)
        with urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None

    def whoami(self) -> str:
        """Username the token belongs to -- how the bot recognises its own threads."""

        return self._call("GET", "/user")["username"]

    def diff_refs(self) -> dict:
        return self._call("GET", self.path)["diff_refs"]

    def discussions(self) -> list[dict]:
        collected: list[dict] = []
        page = 1
        while True:
            batch = self._call("GET", f"{self.path}/discussions?per_page=100&page={page}")
            if not batch:
                return collected
            collected.extend(batch)
            if len(batch) < 100:
                return collected
            page += 1

    def threads_by(self, author: str) -> dict[str, Thread]:
        """Every thread this bot opened, keyed by the conflict it stands for."""

        found: dict[str, Thread] = {}
        for discussion in self.discussions():
            notes = discussion.get("notes") or []
            if not notes or _author(notes[0]) != author:
                continue
            key = _key_of(notes[0].get("body", ""))
            if key is None:
                continue
            found[key] = Thread(
                key=key,
                discussion_id=discussion["id"],
                note_id=notes[0]["id"],
                body=notes[0].get("body", ""),
                anchor=anchor_of(notes[0].get("position")),
                answered=any(_author(note) != author for note in notes[1:]),
            )
        return found

    def open_thread(self, comment: Comment) -> None:
        """Post a new thread, falling back to an unanchored one if the diff rejects the anchor."""

        if comment.position:
            try:
                self._call("POST", f"{self.path}/discussions", {"body": comment.body, "position": comment.position})
                return
            except HTTPError as error:
                print(f"  anchor refused ({error.code}): {_detail(error)} -- posting unanchored", file=sys.stderr)
        self._call("POST", f"{self.path}/discussions", {"body": comment.body})

    def edit(self, note_id: int, body: str) -> None:
        self._call("PUT", f"{self.path}/notes/{note_id}", {"body": body})

    def resolve(self, discussion_id: str) -> None:
        self._call("PUT", f"{self.path}/discussions/{discussion_id}?resolved=true")

    def drop(self, discussion_id: str) -> None:
        self._call("DELETE", f"{self.path}/discussions/{discussion_id}")


def _author(note: dict) -> str:
    return (note.get("author") or {}).get("username", "")


def _detail(error: HTTPError) -> str:
    """Whatever GitLab said about a rejected call, on one line."""

    try:
        return error.read().decode("utf-8", "replace").strip().replace("\n", " ")[:300]
    except OSError:
        return str(error)


def _key_of(body: str) -> str | None:
    """The conflict key a note was tagged with, or ``None`` for a note the bot did not write."""

    match = KEY_PATTERN.search(body)
    return match.group(1) if match else None


def conflict_keys(items: list[Renumbering]) -> list[str]:
    """A thread key per conflict: stable across pushes, unique within one MR.

    Line numbers move with every edit, so the key names the number and the function raising it.
    Two sites in one function sharing a number are told apart by an ordinal -- the plan is
    ordered by file and line, so that stays put too.
    """

    keys: list[str] = []
    seen: Counter = Counter()
    for item in items:
        key = f"{item.old_number}@{item.record.file}:{item.record.location}"
        seen[key] += 1
        keys.append(key if seen[key] == 1 else f"{key}#{seen[key]}")
    return keys


def suggested_line(record: ErrorRecord, new_number: str) -> str | None:
    """The call site's line as it will read once renumbered, or ``None`` if it cannot be spliced.

    A GitLab suggestion replaces the whole line it is anchored to, so it has to carry the
    original indentation and everything else on that line -- not just the keyword argument. The
    literal's span is in UTF-8 byte offsets, so the splice happens on bytes.
    """

    if record.number_pos is None:
        return None
    lineno, col, end_col = record.number_pos
    try:
        line = (REPO_ROOT / record.file).read_bytes().splitlines()[lineno - 1]
    except (OSError, IndexError):
        return None
    quote_char = line[col : col + 1] if line[col : col + 1] in (b'"', b"'") else b'"'
    return (line[:col] + quote_char + new_number.encode("utf-8") + quote_char + line[end_col:]).decode("utf-8")


def anchor_of(position: dict | None) -> tuple[str, int] | None:
    """Where a note sits in the diff, without the shas -- those move on every push, the line does not.

    GitLab re-points a diff note as long as it can still follow the line. When it cannot, the note
    stays behind on the line the code used to occupy and the thread goes outdated, which is the one
    case the bot has to notice.
    """

    if not position or position.get("new_line") is None:
        return None
    return (position.get("new_path", ""), int(position["new_line"]))


def _position(record: ErrorRecord, diff_refs: dict) -> dict | None:
    """Anchor on the ``error_number=`` line itself, which is rarely the line the call starts on."""

    if record.number_pos is None:
        return None
    return {
        "position_type": "text",
        "base_sha": diff_refs["base_sha"],
        "start_sha": diff_refs["start_sha"],
        "head_sha": diff_refs["head_sha"],
        "old_path": record.file,
        "new_path": record.file,
        "new_line": record.number_pos[0],
    }


def _branch(base_ref: str | None) -> str:
    """The base ref as a reviewer knows it -- ``origin/`` is plumbing, not a branch name."""

    return base_ref.removeprefix("origin/") if base_ref else "the target branch"


def conflict_comment(item: Renumbering, key: str, base_ref: str | None, diff_refs: dict) -> Comment:
    """The thread for one conflict: what collided, what to use instead, and a one-click fix."""

    line = suggested_line(item.record, item.new_number)
    body = [
        f"Error number `{item.old_number}` is already taken on `{_branch(base_ref)}`.",
        f"Renumber `{item.record.location}` to the next free number, `{item.new_number}` (`{item.new_error_id}`).",
    ]
    if line is not None:
        body += ["", "```suggestion:-0+0", line, "```"]
    body += ["", f"<!-- {MARKER}:key={key} -->"]
    return Comment(key=key, body="\n".join(body), position=_position(item.record, diff_refs))


def unfixable_comment(plan: RenumberPlan) -> Comment | None:
    """One unanchored note for the duplicates the fixer refuses to resolve on its own."""

    if not plan.unfixable:
        return None
    body = ["Duplicate error numbers that need a human:", ""]
    for duplicate in plan.unfixable:
        sites = ", ".join(f"`{record.file}:{record.lineno}`" for record in duplicate.records)
        body.append(f"* `{duplicate.number}` -- {duplicate.reason} ({sites})")
    body += ["", f"<!-- {MARKER}:key={UNFIXABLE_KEY} -->"]
    return Comment(key=UNFIXABLE_KEY, body="\n".join(body))


def wanted_comments(plan: RenumberPlan, diff_refs: dict) -> list[Comment]:
    """Every thread the MR should carry for the current plan."""

    keys = conflict_keys(plan.renumberings)
    comments = [conflict_comment(item, key, plan.base_ref, diff_refs) for item, key in zip(plan.renumberings, keys, strict=True)]
    summary = unfixable_comment(plan)
    return [*comments, summary] if summary else comments


def _has_drifted(thread: Thread, comment: Comment) -> bool:
    """Whether the thread is stranded on a line the call site has since left.

    Only threads that carry an anchor and that nobody has replied to are worth re-pinning. One
    that never got an anchor was posted unanchored because the diff refused it, and re-posting
    would only refuse it again; one somebody replied to is a conversation, not a bot artefact.
    """

    if thread.anchor is None or thread.answered:
        return False
    return anchor_of(comment.position) != thread.anchor


def reconcile(mr: MergeRequest, author: str, wanted: list[Comment]) -> None:
    """Make the MR's bot threads agree with ``wanted``, leaving the ones that already do alone."""

    existing = mr.threads_by(author)
    for comment in wanted:
        thread = existing.get(comment.key)
        if thread is None:
            mr.open_thread(comment)
            print(f"posted   {comment.key}")
        elif _has_drifted(thread, comment):
            # A note's position is fixed at creation, so following the code means starting over.
            mr.drop(thread.discussion_id)
            mr.open_thread(comment)
            print(f"moved    {comment.key} (was pinned to {thread.anchor})")
        elif thread.body.strip() != comment.body.strip():
            mr.edit(thread.note_id, comment.body)
            print(f"updated  {comment.key}")
        else:
            print(f"kept     {comment.key}")

    for key, thread in existing.items():
        if any(comment.key == key for comment in wanted):
            continue
        if thread.answered:
            mr.resolve(thread.discussion_id)
            print(f"resolved {key} (someone replied, so the thread stays)")
        else:
            mr.drop(thread.discussion_id)
            print(f"removed  {key}")


def _warn_if_not_rebased(base_ref: str) -> None:
    """A branch behind its target hides the very collisions this job looks for."""

    behind = subprocess.run(
        ("git", "merge-base", "--is-ancestor", base_ref, "HEAD"),
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if behind.returncode != 0:
        print(f"Note: this branch is not rebased onto {_branch(base_ref)}, so numbers merged since it was cut are invisible here.")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    fail_on_conflict = "--fail-on-conflict" in args

    iid = os.environ.get("CI_MERGE_REQUEST_IID")
    if not iid:
        print("Not a merge-request pipeline; nothing to comment on.")
        return 0

    token = os.environ.get("GITLAB_TOKEN", "")
    project = os.environ.get("CI_PROJECT_ID", "")
    missing = [name for name, value in (("GITLAB_TOKEN", token), ("CI_PROJECT_ID", project)) if not value]
    if missing:
        print(f"Missing required environment: {', '.join(missing)}", file=sys.stderr)
        return 2

    base_ref = resolve_base_ref()
    if base_ref is None:
        print("Cannot resolve the target branch -- this job needs a full clone (GIT_DEPTH: 0).", file=sys.stderr)
        return 2
    _warn_if_not_rebased(base_ref)

    catalog_text = CATALOG_PATH.read_text(encoding="utf-8") if CATALOG_PATH.exists() else None
    plan = plan_renumbering(scan_error_calls(), base_ref=base_ref, catalog_text=catalog_text)

    api_url = os.environ.get("CI_API_V4_URL") or "https://gitlab.com/api/v4"
    mr = MergeRequest(api_url, token, project, iid)
    author = os.environ.get("ERROR_CATALOG_BOT_USERNAME") or mr.whoami()

    wanted = wanted_comments(plan, mr.diff_refs()) if (plan.renumberings or plan.unfixable) else []
    reconcile(mr, author, wanted)
    if not wanted:
        print(f"No error-number conflicts with {_branch(base_ref)}.")
    return 1 if wanted and fail_on_conflict else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HTTPError as error:
        print(f"GitLab API call failed ({error.code}): {_detail(error)}", file=sys.stderr)
        sys.exit(2)
    except URLError as error:
        print(f"GitLab API unreachable: {error.reason}", file=sys.stderr)
        sys.exit(2)
