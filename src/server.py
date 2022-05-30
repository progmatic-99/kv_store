import os
import sys


if os.environ["TYPE"] == "master":
    import plyvel

    db = plyvel.DB(os.environ["DB"], create_if_missing=True)


def master(env, start_response):
    print(env)
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"Hello World"]


def volume(env, start_response):
    print(env)
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"Volume World"]
