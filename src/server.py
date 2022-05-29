def master(env, start_response):
    print(env)
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"Hello World"]


def volume(env, start_response):
    print(env)
    start_response("200 OK", [("Content-Type", "text/html")])
    return [b"Volume World"]
