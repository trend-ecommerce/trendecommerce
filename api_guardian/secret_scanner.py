import os
import re

# Regex patterns for detecting hardcoded credentials and secrets
SECRET_PATTERNS = [
    (r'(?i)(lwa_token|access_token|refresh_token)\s*=\s*["\'](?!os\.getenv|os\.environ)[^"\']{8,}["\']', "Hardcoded Token"),
    (r'(?i)(api_key|secret_key|private_key|auth_token)\s*=\s*["\'](?!os\.getenv|os\.environ)[^"\']{8,}["\']', "Hardcoded API Key"),
    (r'(?i)(aws_secret_access_key|aws_access_key_id)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded AWS Credentials"),
    (r'AKIA[0-9A-Z]{16}', "Exposed AWS Access Key ID"),
    (r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', "Exposed Bearer Token"),
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'](?!os\.getenv|os\.environ)[^"\']{4,}["\']', "Hardcoded Password"),
]


def mask_secret(text: str) -> str:
    """Masks secrets so sensitive values are never logged."""
    if not text:
        return ""
    if len(text) <= 6:
        return "********"
    return text[:2] + "********" + text[-2:]


class SecretScanner:
    def __init__(self, custom_patterns=None):
        self.patterns = custom_patterns or SECRET_PATTERNS

    def scan_file(self, filepath: str) -> list:
        """
        Scans a single file for exposed hardcoded secrets.
        Returns a list of violation dictionaries.
        """
        violations = []
        if not os.path.exists(filepath):
            return violations

        ext = os.path.splitext(filepath)[1].lower()
        if ext not in ['.py', '.yaml', '.yml', '.json', '.env']:
            return violations

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return violations

        for line_num, line_content in enumerate(lines, 1):
            stripped = line_content.strip()
            # Skip comments or empty lines
            if stripped.startswith('#') or not stripped:
                continue

            # Skip os.getenv / os.environ assignments
            if 'os.getenv' in stripped or 'os.environ' in stripped:
                continue

            for pattern, secret_type in self.patterns:
                match = re.search(pattern, line_content)
                if match:
                    matched_str = match.group(0)
                    masked = mask_secret(matched_str)
                    violations.append({
                        'file': filepath,
                        'line': line_num,
                        'secret_type': secret_type,
                        'masked_value': masked,
                        'reason': f"Hardcoded credential exposed ({secret_type}): {masked}"
                    })
                    break

        return violations

    def scan_directory(self, target_dir: str) -> list:
        all_violations = []
        for root, _, files in os.walk(target_dir):
            for file in files:
                filepath = os.path.join(root, file)
                violations = self.scan_file(filepath)
                all_violations.extend(violations)
        return all_violations
