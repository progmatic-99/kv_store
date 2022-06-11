import os
import json
import sys
import time
import hashlib
import socket
import random


# *** Master Server ***

if os.environ["TYPE"] == "master":
    # check volume servers
    volumes = os.environ["VOLUMES"].split(",")

    for v in volumes:
        print(v)

    import plyvel

    db = plyvel.DB(os.environ["DB"], create_if_missing=True)


def master(env, start_response):
    key = env["REQUEST_URI"]
    metakey = db.get(key.encode("utf-8"))

    if metakey is None:
        if env["REQUEST_METHOD"] == "PUT":
            # handle put requests
            volume = random.choice(volumes)

            meta = {"volume": volume}
            db.put(key.encode("utf-8"), json.dumps(meta).encode("utf-8"))
        else:
            # key doesn't exist
            start_response("404 Not found", [("Content-Type", "text/plain")])
            return [b"key not found"]
    else:
        # key found
        """
        if env["REQUEST_METHOD"] == "PUT":
            start_response("409 Conflict", [("Content-Type", "text/plain")])
            return [b"key already exists"]

        """
        meta = json.loads(metakey.decode("utf-8"))

    volume = meta["volume"]
    # send the redirect for either GET or DELETE
    headers = [("Location", "http://%s%s" % (volume, key))]
    start_response("307 Temporary Redirect", headers)
    return [b""]


class FileCache(object):
    def __init__(self, basedir):
        self.basedir = os.path.realpath(basedir)
        os.makedirs(self.basedir, exist_ok=True)

        print(f"Filecache in {self.basedir}")

    def key_to_path(self, key, mkdir_ok=False):
        # must be md5 hash
        assert len(key) == 32

        # 2 layers deep in nginx world
        path = self.basedir + "/" + key[0:2] + "/" + key[0:4]
        if not os.path.isdir(path) and mkdir_ok:
            os.makedirs(path, exist_ok=True)

        return os.path.join(path, key)

    def exists(self, key):
        return os.path.isfile(self.key_to_path(key))

    def get(self, key):
        return open(self.key_to_path(key), "rb")

    def put(self, key, value):
        with open(self.key_to_path(key, True), "wb") as f:
            f.write(value)

    def delete(self, key):
        os.unlink(self.key_to_path(key))


if os.environ["TYPE"] == "volume":
    host = socket.gethostname()

    fc = FileCache(os.environ["VOLUME"])

# ** Volume server **


def volume(env, start_response):
    key = env["REQUEST_URI"].encode("utf-8")
    hkey = hashlib.md5(key).hexdigest()

    if env["REQUEST_METHOD"] == "GET":
        if not fc.exists(hkey):
            # key not in file cache
            start_response("404 Not found", [("Content-Type", "text/plain")])
            return [b"key not found"]

        start_response("302 Found", [("Content-Type", "text/plain")])
        return fc.get(hkey)

    if env["REQUEST_METHOD"] == "PUT":
        flen = int(env.get("CONTENT_LENGTH", "0"))

        if flen > 0:
            fc.put(hkey, env["wsgi.input"].read(flen))
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b""]
        else:
            start_response("411 Length Required", [("Content-Type", "text/plain")])
            return [b""]

    if env["REQUEST_METHOD"] == "DELETE":
        fc.delete(hkey)
