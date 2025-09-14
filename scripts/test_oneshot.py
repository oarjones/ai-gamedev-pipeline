import os
import sys

# Ensure 'gateway' is on sys.path so 'app' package is importable
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
gateway_root = os.path.join(repo_root, 'gateway')
if gateway_root not in sys.path:
    sys.path.insert(0, gateway_root)

from app.services.providers.gemini_cli import GeminiCliProvider
from app.services.providers.base import SessionCtx


def main() -> int:
    workdir = os.path.join(repo_root, 'projects', '_oneshot_test')
    os.makedirs(workdir, exist_ok=True)
    provider = GeminiCliProvider(SessionCtx(projectId='proj', sessionId='sess'))
    answer, error = provider.run_one_shot('Di hola en una palabra.', workdir)
    print('--- ONE-SHOT RESULT ---')
    print('ANSWER:\n', answer)
    print('\nSTDERR:\n', error)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

