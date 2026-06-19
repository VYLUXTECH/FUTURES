Write-Host "=== Fixing .env AI variables ===" -ForegroundColor Yellow
$envFile = "C:\futures\.env"
$content = Get-Content $envFile -Raw

$content = $content -replace '(?<=AI_BASE_URL=).*', 'https://api.nexray.eu.cc/ai/gemini'
$content = $content -replace '(?<=AI_MODEL=).*', 'gemini'

Set-Content $envFile $content
Write-Host "AI vars updated. Restart bot for changes to take effect." -ForegroundColor Green
