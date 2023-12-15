#!/usr/bin/env python3

import argparse
import json
import os
from datetime import datetime, timedelta

import requests

CACHE_DIR = "cache"


def check_wordpress(host):
    response = make_request(host, "wp/v2/", False)
    return response.status_code == 200


def get_users(host, human_readable):
    users_cache_path = get_cache_path(host, "users.json")
    users = load_from_cache(users_cache_path)

    if users is None:
        response = make_request(host, "wp/v2/users", False)
        users = response.json()
        save_to_cache(users_cache_path, users, expiration_minutes=5 * 60)

    display_users(users, human_readable)


def get_url_paginated(host, url, page, mime=None):
    if mime:
        return make_request(host, f"{url}?page={page}", mime).json()
    else:
        return make_request(host, f"{url}?page={page}").json()


def get_files(host, verbose, mime=None):
    files_cache_path = get_cache_path(host, "files")
    files = []
    page_start = 1
    page_end = 500
    page = page_start

    while True:
        if (verbose):
            print(f"Getting page: {page}")

        page_files = get_url_paginated(host, "wp/v2/media", page)

        if not page_files:
            break

        if page == page_end:
            break

        page += 1
        if (verbose):
            display_files(page_files, [], False)
        save_to_cache(files_cache_path, page_files, expiration_minutes=5 * 60)

    return files


def get_posts(host, human_readable):
    posts_cache_path = get_cache_path(host, "posts.json")
    posts = load_from_cache(posts_cache_path)

    if posts is None:
        response = make_request(host, "wp/v2/posts", False)
        posts = response.json()
        save_to_cache(posts_cache_path, posts, expiration_minutes=5 * 60)

    display_posts(posts, human_readable)


def should_exclude(file, excluded_file_extensions):
    file_extension = os.path.splitext(file['source_url'])[1][1:]
    return file_extension in excluded_file_extensions


def display_users(users, human_readable):
    if human_readable:
        for user in users:
            print(f"User ID: {user['id']}, Username: {user['name']}")
    else:
        print(json.dumps(users, indent=2))


def display_files(files, exclude_file_extensions, human_readable):
    if not human_readable:
        print("{[")

    for file in files:
        if (isinstance(file, dict)):
            if not should_exclude(file, exclude_file_extensions):
                file_id = json.dumps(file.get("id", ""))
                file_title = json.dumps(file.get("title", {}).get("rendered", ""))
                file_url = json.dumps(file.get("source_url", ""))

                if human_readable:
                    print(f'"id": {file_id}, "title": {file_title}, "url": {file_url}')
                else:
                    print(f'"id": {file_id}, "title": {file_title}, "url": {file_url}')

    if not human_readable:
        print("]}")


def display_posts(posts, human_readable):
    if human_readable:
        for post in posts:
            print(f"Post ID: {post['id']}, Title: {post['title']['rendered']}, Content: {post['content']['rendered']}")
    else:
        print(json.dumps(posts, indent=2))


def make_request(host, endpoint, mimetype=None):
    url = f"https://{host}/wp-json/{endpoint}"
    try:
        if mimetype:
            p = "mime_type=" + mimetype
            response = requests.get(url, params=p)
        else:
            response = requests.get(url)
    except:
        response = {}
        response.status_code = 999
        return response
    return response


def load_from_cache(cache_path):
    if os.path.exists(cache_path):
        with open(cache_path, "r") as file:
            try:
                data = json.load(file)
                return data['data'] if not is_cache_expired(data) else None
            except json.JSONDecodeError:
                return None
    return None


def save_to_cache(cache_path, data, expiration_minutes):
    existing_data = load_from_cache(cache_path) or {"data": [], "expiration_time": ""}

    if isinstance(existing_data, list):
        existing_data = {"data": existing_data, "expiration_time": ""}

    existing_data["data"].extend(data)
    existing_data["expiration_time"] = (datetime.now() + timedelta(minutes=expiration_minutes)).isoformat()

    with open(cache_path, "w") as file:
        json.dump(existing_data, file)


def is_cache_expired(data):
    expiration_time = datetime.fromisoformat(data.get("expiration_time", ""))
    return datetime.now() > expiration_time


def get_cache_path(host, endpoint):
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{host}_{endpoint}.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WordPress API Explorer")
    parser.add_argument("host", help="WordPress host name")
    parser.add_argument("-u", "--users", action="store_true", help="Get all users")
    parser.add_argument("-f", "--files", action="store_true", help="Get all files")
    parser.add_argument("-p", "--posts", action="store_true", help="Get all posts")
    parser.add_argument("--detect-only", action="store_true", help="Detect if WP api is available for querying")
    parser.add_argument("--nocache", action="store_true", help="Ignore cache and make a fresh request")
    parser.add_argument("--human-readable", action="store_true", help="Display output in a human-readable format")
    parser.add_argument("--exclude-file", help="Exclude files with the specified extensions (comma-separated)")
    parser.add_argument("--mimetype", help="NOT WORKING YET? Include files with the specified mine type only (ie. application/sql)")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")

    args = parser.parse_args()

    exclude_file_extensions = [] if args.exclude_file is None else args.exclude_file.split(',')

    if not check_wordpress(args.host):
        print("WordPress not detected on the provided host.")
        exit(1)
    if args.detect_only:
        exit(0)

    if args.nocache:
        print("Cache ignored.")
    else:
        print("Cache used.")

    if args.users:
        get_users(args.host, args.human_readable)
    if args.files:
        files = []
        if not args.nocache:
            files = load_from_cache(get_cache_path(args.host, "files"))
        if not files:
            files = get_files(args.host, args.verbose)
        display_files(files, exclude_file_extensions, args.human_readable)

    if args.posts:
        get_posts(args.host, args.human_readable)

