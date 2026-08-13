import os
import glob
import re

try:
    import yaml
except ImportError:
    yaml = None


def _simple_yaml_parse(content: str) -> dict:
    """Robust fallback parser for policy YAML files if PyYAML is not installed."""
    import re
    doc = {}
    current_key = None
    current_list = None
    current_dict_in_list = None

    lines = content.splitlines()
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        # List item
        if stripped.startswith('- '):
            item_content = stripped[2:].strip()
            if ':' in item_content:
                # Key-value inside list item, e.g. - path: /catalog/items
                k, v = item_content.split(':', 1)
                k, v = k.strip(), v.strip()
                current_dict_in_list = {k: v}
                if current_key and isinstance(doc.get(current_key), list):
                    doc[current_key].append(current_dict_in_list)
            else:
                # Plain list item, e.g. - GET
                if current_dict_in_list is not None and current_key:
                    # Could be nested inside current dict in list
                    pass
                if current_key:
                    if not isinstance(doc.get(current_key), list):
                        doc[current_key] = []
                    doc[current_key].append(item_content)
            continue

        if ':' in stripped:
            k, v = stripped.split(':', 1)
            k = k.strip()
            v = v.strip()

            if current_dict_in_list is not None and indent > 2:
                # Property of dict in list, e.g. methods: [GET]
                if v.startswith('[') and v.endswith(']'):
                    v_list = [x.strip() for x in v[1:-1].split(',') if x.strip()]
                    current_dict_in_list[k] = v_list
                elif v == '':
                    current_key = k
                    current_dict_in_list[k] = []
                else:
                    if v.lower() == 'true': v = True
                    elif v.lower() == 'false': v = False
                    current_dict_in_list[k] = v
            else:
                current_dict_in_list = None
                current_key = k
                if v == '':
                    doc[k] = []
                elif v.startswith('[') and v.endswith(']'):
                    doc[k] = [x.strip() for x in v[1:-1].split(',') if x.strip()]
                else:
                    if v.lower() == 'true': v = True
                    elif v.lower() == 'false': v = False
                    doc[k] = v

    return doc


def load_yaml_file(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if yaml is not None:
        try:
            return yaml.safe_load(content)
        except Exception:
            pass
    return _simple_yaml_parse(content)


class GuardianConfig:
    def __init__(self, policies_dir: str = None):
        if policies_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            policies_dir = os.path.join(base_dir, 'policies')
        self.policies_dir = policies_dir
        self.policies = []
        self.load_policies()

    def load_policies(self):
        self.policies = []
        if os.path.exists(self.policies_dir):
            pattern = os.path.join(self.policies_dir, '*.yaml')
            for filepath in glob.glob(pattern):
                try:
                    data = load_yaml_file(filepath)
                    if data and isinstance(data, dict):
                        self.policies.append(data)
                except Exception as e:
                    print(f"[API Guardian Warning] Failed to load policy file {filepath}: {e}")
        return self.policies
