import os
import json
import time
import hashlib
import socket
import random
import tempfile
import xattr


def resp(start_response, code, headers=[("Content-type", "text/plain")], body=b""):
    start_response(code, headers)
    return [body]


# *** Master Server ***

if os.environ["TYPE"] == "master":
    # check volume servers
    volumes = os.environ["VOLUMES"].split(",")

    for v in volumes:
        print(v)

    import plyvel

    db = plyvel.DB(os.environ["DB"], create_if_missing=True)


def master(env, sr):
    key = env["PATH_INFO"]
    host = env["SERVER_NAME"] + ":" + env["SERVER_PORT"]

    if env["REQUEST_METHOD"] == "POST":
        # POST called by volume servers to write to database
        flen = int(env.get("CONTENT_LENGTH", "0"))

        if flen > 0:
            db.put(key.encode("utf-8"), env["wsgi.input"].read(), sync=True)
        else:
            db.delete(key.encode("utf-8"))

        return resp(sr, "200 OK")

    metakey = db.get(key.encode("utf-8"))
    if metakey is None:
        if env["REQUEST_METHOD"] == "PUT":
            # handle put requests
            volume = random.choice(volumes)
        else:
            # key doesn't exist
            return resp(sr, "404 Not Found")
    else:
        # key found
        if env["REQUEST_METHOD"] == "PUT":
            return resp(sr, "409 Conflict")

        meta = json.loads(metakey.decode("utf-8"))
        volume = meta["volume"]

    # send the redirect for either GET or DELETE
    headers = [("Location", "http://%s%s" % (volume, key))]

    return resp(sr, "307 Temporary Redirect", headers)


class FileCache(object):
    def __init__(self, basedir):
        self.basedir = os.path.realpath(basedir)
        self.tmpdir = os.path.join(self.basedir, "tmp")
        os.makedirs(self.tmpdir, exist_ok=True)

        print(f"Filecache in {self.basedir}")

    def key_to_path(self, key, mkdir_ok=False):
        key = hashlib.md5(key).hexdigest()

        # 2 layers deep in nginx world
        path = self.basedir + "/" + key[0:2] + "/" + key[0:4]
        if not os.path.isdir(path) and mkdir_ok:
            os.makedirs(path, exist_ok=True)

        return os.path.join(path, key)

    def exists(self, key):
        return os.path.isfile(self.key_to_path(key))

    def get(self, key):
        return open(self.key_to_path(key), "rb")

    def put(self, key, stream):
        with tempfile.NamedTemporaryFile(dir=self.tmpdir, delete=False) as f:
            # anti pattern: what if the file is 1gb
            # read in chunks
            f.write(stream.read())
            xattr.setxattr(f.name, "user.key", key)
            os.rename(f.name, self.key_to_path(key, True))

    def delete(self, key):
        os.unlink(self.key_to_path(key))


if os.environ["TYPE"] == "volume":
    host = socket.gethostname()

    fc = FileCache(os.environ["VOLUME"])

# ** Volume server **


def volume(env, sr):
    key = env["PATH_INFO"]
    host = env["SERVER_NAME"] + ":" + env["SERVER_PORT"]

    if env["REQUEST_METHOD"] == "PUT":
        if fc.exists(key):
            req = requests.post('http://'+env['QUERY_STRING'])
            return resp(sr, "409 Conflict")

        flen = int(env.get("CONTENT_LENGTH", "0"))

        if flen > 0:
            fc.put(key, env["wsgi.input"])
            req = requests.post('http://'+env['QUERY_STRING'])

            # notify database
            return resp(sr, "201 Created")
        else:
            return resp(sr, "411 Length Required")

    if not fc.exists(key):
        # key not in file cache
        return resp(sr, "404 Not Found", body=b"key not found")

    if env["REQUEST_METHOD"] == "GET":
        return resp(sr, "302 Found", body=fc.get(key).read())

    if env["REQUEST_METHOD"] == "DELETE":
        fc.delete(key)
        return resp(sr, "200 OK")
