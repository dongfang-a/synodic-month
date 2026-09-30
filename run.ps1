$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $taskPython -m pip install -e '.[test]'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($args.Count -eq 0) {
    & $taskPython -m synodic --help
} else {
    & $taskPython -m synodic @args
}
exit $LASTEXITCODE
