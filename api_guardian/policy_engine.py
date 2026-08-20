import os
import re
from urllib.parse import urlparse, parse_qs, urlencode
from .config import GuardianConfig


def match_path_template(template: str, actual_path: str):
    template = template.rstrip('/')
    actual_path = actual_path.rstrip('/')

    param_names = re.findall(r'\{([a-zA-Z0-9_]+)\}', template)
    regex_pattern = '^' + re.sub(r'\{[a-zA-Z0-9_]+\}', r'([^/]+)', template) + '$'

    match = re.match(regex_pattern, actual_path)
    if not match:
        return False, {}

    extracted_params = {}
    for name, value in zip(param_names, match.groups()):
        extracted_params[name] = value

    return True, extracted_params


class PolicyResult(dict):
    """Dict subclass allowing attribute access for .status and .decision"""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


class PolicyEngine:
    def __init__(self, config: GuardianConfig = None):
        if config is None:
            config = GuardianConfig()
        self.config = config

    def evaluate(self, method_or_request, url: str = None, headers: dict = None, params: dict = None) -> PolicyResult:
        if isinstance(method_or_request, dict):
            request = method_or_request
        else:
            request = {
                "method": method_or_request,
                "url": url,
                "headers": headers or {},
                "params": params or {}
            }

        raw_url = request.get('url', '')
        req_params = request.get('params') or {}
        if req_params and '?' not in raw_url:
            raw_url = f"{raw_url}?{urlencode(req_params)}"

        method = (request.get('method') or 'GET').upper()
        headers = request.get('headers') or {}
        filepath = request.get('file', '')
        line = request.get('line', 0)

        parsed_url = urlparse(raw_url)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        matched_policy = None
        matched_endpoint_spec = None
        extracted_path_params = {}

        for policy in self.config.policies:
            endpoints = policy.get('endpoints', [])
            if endpoints:
                for ep in endpoints:
                    tmpl = ep.get('path', '')
                    is_match, p_params = match_path_template(tmpl, path)
                    if is_match:
                        matched_policy = policy
                        matched_endpoint_spec = ep
                        extracted_path_params = p_params
                        break
                if matched_policy:
                    break
            else:
                endpoint_pattern = policy.get('endpoint_pattern')
                if endpoint_pattern and re.search(endpoint_pattern, path):
                    matched_policy = policy
                    break
                tmpl = policy.get('path_template', '')
                if tmpl:
                    is_match, p_params = match_path_template(tmpl, path)
                    if is_match:
                        matched_policy = policy
                        extracted_path_params = p_params
                        break

        if not matched_policy:
            return PolicyResult({
                'status': 'BLOCK',
                'decision': 'BLOCK',
                'severity': 'C — HIGH',
                'reason': f"Endpoint '{path}' não autorizado. Nenhum esquema correspondente encontrado em policies/.",
                'file': filepath,
                'line': line,
                'details': [f"✗ Endpoint não cadastrado em policies/: {path}"]
            })

        details = [f"OK Endpoint identificado: {matched_policy.get('name', matched_policy.get('id'))}"]

        allowed_methods = matched_policy.get('allowed_methods')
        if not allowed_methods and matched_endpoint_spec:
            allowed_methods = matched_endpoint_spec.get('methods', ['GET'])
        if not allowed_methods:
            allowed_methods = ['GET']

        if method not in allowed_methods:
            return PolicyResult({
                'status': 'BLOCK',
                'decision': 'BLOCK',
                'severity': 'C — HIGH',
                'policy': matched_policy.get('id'),
                'reason': f"Método HTTP '{method}' não é permitido para o endpoint '{path}'. Permitidos: {allowed_methods}",
                'file': filepath,
                'line': line,
                'details': details + [f"✗ Método '{method}' não permitido."]
            })
        details.append(f"OK Método {method} autorizado")

        auth_required = matched_policy.get('auth_required')
        if auth_required is None:
            auth_spec = matched_policy.get('authentication', {})
            auth_required = auth_spec.get('required', False)

        if auth_required:
            auth_header = headers.get('Authorization') or headers.get('authorization') or headers.get('x-amz-access-token')
            if not auth_header:
                return PolicyResult({
                    'status': 'BLOCK',
                    'decision': 'BLOCK',
                    'severity': 'C — HIGH',
                    'policy': matched_policy.get('id'),
                    'reason': f"Autenticação obrigatoria ausente para endpoint '{path}'",
                    'file': filepath,
                    'line': line,
                    'details': details + ["✗ Cabeçalho de autenticação ausente."]
                })
            details.append("OK Autenticação fornecida")
        else:
            details.append("OK Autenticação não requerida")

        param_spec = matched_policy.get('parameters', {})
        req_query_params = param_spec.get('required', [])
        for req_p in req_query_params:
            if req_p not in query_params or not query_params[req_p]:
                return PolicyResult({
                    'status': 'BLOCK',
                    'decision': 'BLOCK',
                    'severity': 'C — HIGH',
                    'policy': matched_policy.get('id'),
                    'reason': f"Parametro obrigatorio ausente: '{req_p}'",
                    'file': filepath,
                    'line': line,
                    'details': details + [f"✗ Parâmetro '{req_p}' ausente."]
                })
            details.append(f"OK Parâmetro '{req_p}' fornecido")

        return PolicyResult({
            'status': 'ALLOW',
            'decision': 'ALLOW',
            'severity': 'INFO',
            'policy': matched_policy.get('id'),
            'reason': 'Requisição em conformidade com as políticas do API Guardian.',
            'file': filepath,
            'line': line,
            'details': details + ["OK Todas as validações concluídas com sucesso."]
        })
