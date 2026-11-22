$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -c "import flask"
if ($LASTEXITCODE -ne 0) {
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Flask installation failed.' }
}
python -X utf8 main.py
