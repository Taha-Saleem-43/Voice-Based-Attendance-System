"""Build a source-only deployment archive with an explicit allowlist."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent

def package():
    files = [ROOT / name for name in ('app.py','requirements.txt','packages.txt','README.md','VALIDATION.md','CONTRIBUTING.md','Dockerfile','.dockerignore','.gitignore')]
    files += list((ROOT/'backend').glob('*.py')) + list((ROOT/'backend').glob('*.sql'))
    files += list((ROOT/'pages').glob('*.py'))
    files += list((ROOT/'ui').glob('*.py'))
    files += list((ROOT/'static').glob('*.css'))
    files += list((ROOT/'.github/workflows').glob('*.yml'))
    files += [ROOT/'.streamlit/config.toml', ROOT/'.streamlit/secrets.toml.example']
    files += list((ROOT/'scripts').glob('*.py')) + list((ROOT/'tests').glob('*.py'))
    output = ROOT/'deploy-dist/VBAS-deploy.zip'
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f'Created {output} ({len(set(files))} files)')
    return output

if __name__ == '__main__':
    package()
