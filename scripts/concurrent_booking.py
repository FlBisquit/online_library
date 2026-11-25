#!/usr/bin/env python3
"""Send ten concurrent issue requests for one copy and verify the result.

The script is intentionally dependency-free so it can be run against any
running backend with the standard library only. It exits with code 0 only when
there is exactly one 201, nine 409 responses and one Issue row for the copy.
"""
import argparse
import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter

THREADS = 10
READER_PASSWORD = "Str0ngPass!2026"


def request(base_url, method, path, payload=None, token=None):
    """Perform one JSON request and return ``(status_code, parsed_body)``."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = base_url + path
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body) if body else {}
        except json.JSONDecodeError:
            return exc.code, {"detail": body}
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Network error for {method} {url}: {exc}", file=sys.stderr)
        return 0, {}


def get_results(base_url, path, token):
    code, body = request(base_url, "GET", path, token=token)
    if code != 200 or not isinstance(body, dict):
        raise RuntimeError(f"GET {path} failed: {code} {body}")
    return body.get("results", [])


def find_or_create_readers(base_url, token):
    readers = [
        row
        for row in get_results(base_url, "/readers/search/?limit=100", token)
        if row.get("role") == "reader" and row.get("status") == "ACTIVE"
    ]
    index = 1
    while len(readers) < THREADS:
        email = f"concurrent{index}@library.local"
        code, body = request(
            base_url,
            "POST",
            "/auth/register/",
            {
                "full_name": f"Concurrent Reader {index}",
                "email": email,
                "password": READER_PASSWORD,
            },
        )
        if code not in (200, 201):
            raise RuntimeError(f"Could not register {email}: {code} {body}")
        index += 1
        readers = [
            row
            for row in get_results(base_url, "/readers/search/?limit=100", token)
            if row.get("role") == "reader" and row.get("status") == "ACTIVE"
        ]
    return readers[:THREADS]


def find_or_create_copy(base_url, token):
    for book in get_results(base_url, "/books/?limit=100", token):
        for copy in get_results(base_url, f"/books/{book['id']}/copies/?limit=100", token):
            if copy.get("status") != "AVAILABLE":
                continue
            # A copy with issue history would make the final count ambiguous.
            if count_issues(base_url, token, copy["inventory_number"]) == 0:
                return book, copy

    suffix = uuid.uuid4().hex[:12]
    code, book = request(
        base_url,
        "POST",
        "/books/",
        {"title": f"Concurrency test book {suffix}", "isbn": f"9785{suffix}1"},
        token=token,
    )
    if code != 201:
        raise RuntimeError(f"Could not create test book: {code} {book}")
    code, copy = request(
        base_url,
        "POST",
        f"/books/{book['id']}/copies/",
        {"inventory_number": f"CONC-{suffix}", "status": "AVAILABLE"},
        token=token,
    )
    if code not in (200, 201):
        raise RuntimeError(f"Could not create test copy: {code} {copy}")
    return book, copy


def count_issues(base_url, token, inventory_number):
    query = urllib.parse.quote(inventory_number)
    rows = get_results(base_url, f"/issues/?search={query}&limit=100", token)
    return sum(row.get("copy", {}).get("inventory_number") == inventory_number for row in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        help="Backend URL, e.g. http://127.0.0.1:8000 or http://127.0.0.1:8000/api",
    )
    parser.add_argument("--email", required=True, help="Librarian email")
    parser.add_argument("--password", required=True, help="Librarian password")
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    if not base_url.endswith("/api"):
        base_url += "/api"

    code, body = request(
        base_url,
        "POST",
        "/token/",
        {"email": args.email, "password": args.password},
    )
    if code != 200 or "access" not in body:
        print(f"Librarian login failed: {code} {body}", file=sys.stderr)
        return 2
    token = body["access"]

    try:
        readers = find_or_create_readers(base_url, token)
        book, copy = find_or_create_copy(base_url, token)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Book: {book.get('title')} ({book.get('id')})")
    print(f"Copy: {copy.get('inventory_number')} ({copy.get('id')})")

    barrier = threading.Barrier(THREADS)
    results = [None] * THREADS

    def worker(index, reader_id):
        barrier.wait()
        code, _body = request(
            base_url,
            "POST",
            "/issues/",
            {"reader_id": reader_id, "copy_id": copy["id"]},
            token=token,
        )
        results[index] = code

    threads = [
        threading.Thread(target=worker, args=(index, reader["id"]))
        for index, reader in enumerate(readers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    if any(thread.is_alive() for thread in threads):
        print("Some requests hung; aborting.", file=sys.stderr)
        return 1

    codes = Counter(results)
    print("Response codes:", ", ".join(f"{code}: {count}" for code, count in sorted(codes.items())))
    issue_count = count_issues(base_url, token, copy["inventory_number"])
    print(f"Issue rows for this copy: {issue_count}")

    success = codes.get(201) == 1 and codes.get(409) == 9 and issue_count == 1
    print("Result:", "1x201, 9x409, 1 issue row — OK" if success else "protection check FAILED")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
