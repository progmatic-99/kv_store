import os
import sys
import time
import hashlib
import socket


# *** Master Server ***

if os.environ["TYPE"] == "master":
    import plyvel

    db = plyvel.DB(os.environ["DB"], create_if_missing=True)


def master(env, start_response):
    key = env["REQUEST_URI"].encode("utf-8")

    metakey = db.get(key)
    if metakey is None:
        if env["REQUEST_METHOD"] in ["PUT"]:
            # handle put requests
            pass

        # key doesn't exist
        start_response("404 Not found", [("Content-Type", "text/html")])
        return [b"key not found"]

    # key found: 'volume'
    meta = json.loads(metakey)

    # send the redirect for either GET or DELETE
    headers = [("location", "http://%s%s" % (meta["volume"], key)), ("expires", "0")]
    start_response("302 Found", headers)
    return [b""]


class FileCache(object):
    def __init__(self, basedir):
        self.basedir = os.path.realpath(basedir)
        os.makedirs(basedir, exist_ok=True)

        print(f"Filecache in {self.basedir}")

    def key_to_path(self, key, mkdir_ok=False):
        # must be md5 hash
        assert len(key) == 32

        # 2 layers deep in nginx world
        path = self.basedir + "/" + key[0:2] + "/" + key[0:4]
        print(path)
        if not os.path.isdir(path) and mkdir_ok:
            os.makedirs(path, exist_ok=True)
        print(os.path.join(path, key))

        return os.path.join(path, key)

    def exists(self, key):
        return os.path.isfile(self.key_to_path(key))

    def get(self, key):
        return open(self.key_to_path(key), "rb")

    def put(self, key, value):
        with open(self.key_to_path(key, True), "wb") as f:
            f.write(value)

    def delete(self, key):
        os.path.unlink(self.key_to_path(key))


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
            start_response("404 Not found", [("Content-Type", "text/html")])
            return [b"key not found"]

        return fc.get(hkey)

    if env["REQUEST_METHOD"] == "PUT":
        fc.put(hkey, env["wsgi.input"].read(int(env["CONTENT_LENGTH"])))
