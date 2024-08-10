from quart import request, current_app
from functools import wraps

_default_cors = {
    "allow_origin": ["*"],
    "allow_headers": ["Content-Type", "Authorization"],
    "allow_methods": ["GET", "OPTIONS"],
    "allow_credentials": False,
    "expose_headers": [],
    "max_age": 86400
}

def apply_cors(
    allow_origin: list = None,
    allow_headers: list = None,
    allow_methods: list = None,
    expose_headers: list = None,
    max_age: int = None,
    allow_credentials: bool = None,
):
    def decorator(f):
        f.required_methods = getattr(f, "required_methods", set())
        if "OPTIONS" not in f.required_methods:
            f.required_methods.add("OPTIONS")
        f.provide_automatic_options = False

        @wraps(f)
        async def decorated_function(*args, **kwargs):
            request._cors = {}
            if allow_origin != None:
                if request._cors.get("allow_origin") is None:
                    request._cors["allow_origin"] = allow_origin
                else:
                    for origin in allow_origin:
                        if origin not in request._cors["allow_origin"]:
                            request._cors["allow_origin"].append(origin)
            if allow_headers != None:
                if request._cors.get("allow_headers") is None:
                    request._cors["allow_headers"] = allow_headers
                else:
                    for header in allow_headers:
                        if header not in request._cors["allow_headers"]:
                            request._cors["allow_headers"].append(header)
            if allow_methods != None:
                if "OPTIONS" not in allow_methods:
                    allow_methods.append("OPTIONS")
                if request._cors.get("allow_methods") is None:
                    request._cors["allow_methods"] = allow_methods
                else:
                    for method in allow_methods:
                        if method not in request._cors["allow_methods"]:
                            request._cors["allow_methods"].append(method)
            if expose_headers != None:
                if request._cors.get("expose_headers") is None:
                    request._cors["expose_headers"] = expose_headers
                else:
                    for header in expose_headers:
                        if header not in request._cors["expose_headers"]:
                            request._cors["expose_headers"].append(header)
            if max_age != None:
                request._cors["max_age"] = max_age
            if allow_credentials != None:
                request._cors["allow_credentials"] = allow_credentials
            
            if request.method == "OPTIONS":
                response = await current_app.make_default_options_response()
                if len(request._cors.get("allow_origin", _default_cors["allow_origin"])) > 0:
                    response.headers["Access-Control-Allow-Origin"] = ",".join(request._cors.get("allow_origin", _default_cors["allow_origin"]))
                if len(request._cors.get("allow_headers", _default_cors["allow_headers"])) > 0:
                    response.headers["Access-Control-Allow-Headers"] = ",".join(request._cors.get("allow_headers", _default_cors["allow_headers"]))
                if len(request._cors.get("allow_methods", _default_cors["allow_methods"])) > 0:
                    response.headers["Access-Control-Allow-Methods"] = ",".join(request._cors.get("allow_methods", _default_cors["allow_methods"]))
                response.headers["Access-Control-Allow-Credentials"] = str(request._cors.get("allow_credentials", _default_cors["allow_credentials"])).lower()
                if len(request._cors.get("expose_headers", _default_cors["expose_headers"])) > 0:
                    response.headers["Access-Control-Expose-Headers"] = ",".join(request._cors.get("expose_headers", _default_cors["expose_headers"]))
                response.headers["Access-Control-Max-Age"] = str(request._cors.get("max_age", _default_cors["max_age"]))
                return response
            
            return await f(*args, **kwargs)

        return decorated_function
    return decorator