import sys
import inspect
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .policy_engine import PolicyEngine
from .reporter import GuardianReporter


class APIGuardianBlockedError(Exception):
    """Exception raised when API Guardian blocks an HTTP request."""
    def __init__(self, result: dict):
        self.result = result
        self.report = GuardianReporter.format_request_result(result)
        super().__init__(self.report)


# Default global policy engine instance
_engine = PolicyEngine()
# Optional custom transport hook for mocking network calls in tests
_network_executor = None


def set_network_executor(executor_fn):
    """Sets a custom network executor for testing (e.g., mock function)."""
    global _network_executor
    _network_executor = executor_fn


def get_caller_location():
    """Inspects stack to find caller file and line number outside api_guardian package."""
    frame = inspect.currentframe()
    try:
        while frame:
            filename = frame.f_code.co_filename
            if 'api_guardian' not in filename and not filename.endswith('inspect.py'):
                return filename, frame.f_lineno
            frame = frame.f_back
    finally:
        del frame
    return "unknown", 0


def guarded_request(method: str, url: str, headers: dict = None, params: dict = None, **kwargs):
    """
    Guarded HTTP request wrapper.
    Evaluates request against API Guardian Policy Engine before attempting network connection.
    If decision is BLOCK, raises APIGuardianBlockedError and DOES NOT perform network call.
    """
    file_path, line_num = get_caller_location()
    headers = headers or {}
    params = params or {}

    request_info = {
        'url': url,
        'method': method.upper(),
        'headers': headers,
        'params': params,
        'file': file_path,
        'line': line_num
    }

    # Evaluate Policy Engine
    result = _engine.evaluate(request_info)

    if result.get('decision') == 'BLOCK':
        # PRINT REPORT & RAISE EXCEPTION - NETWORK IS NEVER EXECUTED
        print(GuardianReporter.format_request_result(result), file=sys.stderr)
        raise APIGuardianBlockedError(result)

    # Decision is ALLOW - Print approval log
    print(GuardianReporter.format_request_result(result))

    # Construct final URL with params if query params supplied
    final_url = url
    if params:
        parsed = urlparse(url)
        # Combine existing query string with params dict
        query_dict = {}
        if parsed.query:
            for pair in parsed.query.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    query_dict[k] = v
        query_dict.update({k: str(v) for k, v in params.items()})
        encoded_query = urlencode(query_dict)
        final_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            encoded_query,
            parsed.fragment
        ))

    # Execute network call via custom executor or urllib.request
    if _network_executor is not None:
        return _network_executor(method=method, url=final_url, headers=headers, **kwargs)

    req = Request(url=final_url, headers=headers, method=method.upper())
    return urlopen(req, **kwargs)
