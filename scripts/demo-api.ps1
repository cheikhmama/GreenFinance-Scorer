Set-Location "C:\Users\mdalo\pfe\GreenFinance-Scorer"
$url = ((Get-Content .env | Select-String '^DATABASE_URL=').Line -replace '^DATABASE_URL=', '') -replace '/greenfinance$', '/greenfinance_demo'
$env:DATABASE_URL = $url
$env:STORAGE_BACKEND = 'local'
$env:STORAGE_PATH = './storage/demo'
$Host.UI.RawUI.WindowTitle = 'GreenFinance - API demo (port 8000)'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
