import os
import re
from urllib.parse import urlparse, parse_qs
from .config import GuardianConfig


def match_path_template(template: str, actual_path: str):
    """
    Matches a path template like '/items/{item_id}' against an actual path like '/items/MLB123'.
    Returns (is_match, extracted_path_params).
    """
    # Normalize paths
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


class PolicyEngine:
    def __init__(self, config: GuardianConfig = None):
        if config is None:
            config = GuardianConfig()
        self.config = config

    def evaluate(self, request: dict) -> dict:
        """
        Evaluates an HTTP request against loaded YAML policies.
        
        request = {
            'provider': optional,
            'url': 'https://api.mercadolibre.com/sites/MLB/search?q=notebook',
            'method': 'GET',
            'headers': {},
            'params': {},
            'file': 'mercadolivre.py',
            'line': 84
        }
        """
        raw_url = request.get('url', '')
        method = (request.get('method') or 'GET').upper()
        headers = request.get('headers') or {}
        params = request.get('params') or {}
        filepath = request.get('file', 'unknown')
        line = request.get('line', 0)

        # Parse URL
        parsed = urlparse(raw_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path or '/'

        # Parse query params from URL if present
        query_params = parse_qs(parsed.query)
        combined_params = {}
        for k, v in query_params.items():
            combined_params[k] = v[0] if len(v) == 1 else v
        if isinstance(params, dict):
            combined_params.update(params)

        matched_policy = None
        matched_endpoint_spec = None
        extracted_path_params = {}

        # Search for matching policy by base_url and endpoint path
        for policy in self.config.policies:
            policy_base_urls = [u.rstrip('/') for u in policy.get('base_urls', [])]
            if base_url.rstrip('/') not in policy_base_urls:
                continue

            for ep in policy.get('endpoints', []):
                ep_path = ep.get('path', '')
                is_match, path_params = match_path_template(ep_path, path)
                if is_match:
                    matched_policy = policy
                    matched_endpoint_spec = ep
                    extracted_path_params = path_params
                    break
            if matched_policy:
                break

        # UNKNOWN API OR UNKNOWN ENDPOINT -> BLOCK
        if not matched_policy or not matched_endpoint_spec:
            return {
                'decision': 'BLOCK',
                'severity': 'A — CRITICAL',
                'policy': 'unknown',
                'reason': f"Endpoint ou API não autorizada: {method} {raw_url}",
                'file': filepath,
                'line': line,
                'details': [
                    f"✗ URL {raw_url} não corresponde a nenhuma API ou endpoint configurado."
                ]
            }

        policy_name = matched_policy.get('name', matched_policy.get('id'))
        details = [f"✓ Endpoint identificado: {policy_name}"]

        # 1. Validate Method
        allowed_methods = matched_endpoint_spec.get('methods', [])
        if method not in allowed_methods:
            return {
                'decision': 'BLOCK',
                'severity': 'B — HIGH',
                'policy': matched_policy.get('id'),
                'reason': f"Método HTTP '{method}' não permitido para este endpoint. Métodos permitidos: {allowed_methods}",
                'file': filepath,
                'line': line,
                'details': details + [f"✗ Método {method} é inválido."]
            }
        details.append(f"✓ Método {method} autorizado")

        # 2. Validate Authentication
        auth_spec = matched_policy.get('authentication', {})
        if auth_spec.get('required', False):
            req_creds = matched_policy.get('required_credentials', [])
            auth_type = auth_spec.get('type', 'Bearer')

            # Check headers or env variables for required auth
            has_auth = False
            # Normalize headers keys
            norm_headers = {k.lower(): str(v) for k, v in headers.items()}
            
            if 'authorization' in norm_headers or 'x-amz-access-token' in norm_headers:
                has_auth = True
            else:
                # Check environment variables
                for cred in req_creds:
                    if os.getenv(cred) or os.getenv(cred.upper()):
                        has_auth = True
                        break

            if not has_auth:
                return {
                    'decision': 'BLOCK',
                    'severity': 'B — HIGH',
                    'policy': matched_policy.get('id'),
                    'reason': f"Autenticação obrigatória ausente ({auth_type}). Credenciais requeridas: {req_creds}",
                    'file': filepath,
                    'line': line,
                    'details': details + [f"✗ Autenticação {auth_type} ausente."]
                }
            details.append(f"✓ Autenticação {auth_type} válida")
        else:
            details.append("✓ Autenticação não requerida")

        # 3. Validate Parameters
        param_spec = matched_policy.get('parameters', {})
        req_params = param_spec.get('required', [])
        for req_p in req_params:
            if req_p not in combined_params or not combined_params[req_p]:
                return {
                    'decision': 'BLOCK',
                    'severity': 'C — HIGH',
                    'policy': matched_policy.get('id'),
                    'reason': f"Parâmetro obrigatório ausente: '{req_p}'",
                    'file': filepath,
                    'line': line,
                    'details': details + [f"✗ Parâmetro '{req_p}' ausente."]
                }
            details.append(f"✓ Parâmetro obrigatório '{req_p}' fornecido")

        # 4. Check Path Parameters
        req_path_params = param_spec.get('path', [])
        for path_p in req_path_params:
            if path_p not in extracted_path_params or not extracted_path_params[path_p]:
                return {
                    'decision': 'BLOCK',
                    'severity': 'C — HIGH',
                    'policy': matched_policy.get('id'),
                    'reason': f"Parâmetro de caminho ausente ou inválido: '{path_p}'",
                    'file': filepath,
                    'line': line,
                    'details': details + [f"✗ Parâmetro de caminho '{path_p}' inválido."]
                }

        # ALL CHECKS PASSED -> ALLOW
        return {
            'decision': 'ALLOW',
            'severity': 'INFO',
            'policy': matched_policy.get('id'),
            'reason': 'Requisição em conformidade com as políticas do API Guardian.',
            'file': filepath,
            'line': line,
            'details': details + ["✓ Todas as validações concluídas com sucesso."]
        }
