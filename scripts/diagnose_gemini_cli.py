import os, shutil, sys
from pathlib import Path

def find_gemini_candidates():
    candidates = []
    # PATH
    which = shutil.which('gemini')
    if which:
        candidates.append(('PATH', which))
    # Windows global npm
    appdata = os.environ.get('APPDATA')
    if appdata:
        for name in ('gemini.cmd','gemini.ps1','gemini'):
            p = Path(appdata) / 'npm' / name
            if p.exists():
                candidates.append(('APPDATA/npm', str(p)))
    # Repo-local node_modules/.bin
    repo = Path(__file__).resolve().parents[1]
    for name in ('gemini.cmd','gemini.ps1','gemini'):
        p = repo / 'node_modules' / '.bin' / name
        if p.exists():
            candidates.append(('node_modules/.bin', str(p)))
    return candidates

def main():
    print('Python:', sys.executable)
    print('CWD:', os.getcwd())
    print('Has GEMINI_API_KEY:', bool(os.environ.get('GEMINI_API_KEY')))
    print('shutil.which("gemini"):', shutil.which('gemini'))
    print('Candidates:')
    for src, path in find_gemini_candidates():
        print(' -', src, '->', path)
    # Try a quick version probe without blocking
    exe = shutil.which('gemini')
    if not exe:
        # Try first candidate
        cands = find_gemini_candidates()
        if cands:
            exe = cands[0][1]
    if exe:
        try:
            import subprocess
            print('Running version probe:', exe)
            cp = subprocess.run([exe, '--version'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=3, text=True)
            print('Exit:', cp.returncode)
            print('Output:', (cp.stdout or '').strip())
        except Exception as e:
            print('Probe failed:', e)
    else:
        print('No gemini executable found')

if __name__ == '__main__':
    main()

