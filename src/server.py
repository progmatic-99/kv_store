import os
import sys
import time
import hashlib


if os.environ["TYPE"] == "master":
    import plyvel

    db = plyvel.DB(os.environ["DB"], create_if_missing=True)


def master(env, start_response):
    key = env["REQUEST_URI"].encode("utf-8")

    metakey = db.get(key)
    if metakey is None:
        # key doesn't exist
        start_response("404 Not found", [("Content-Type", "text/html")])
        return [b"key not found"]

    # key found: 'volume'
    meta = json.loads(metakey)

    # send the redirect
    headers = [("location", "http://%s%s" % (meta["volume"], key)), ("expires", "0")]
    start_response("302 Found", headers)
    return [b""]


if os.environ["TYPE"] == "volume":
    host = socket.gethostname()


def volume(env, start_response):
    print(env)
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"Volume World"]
