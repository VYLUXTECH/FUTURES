# Wipes C:\thedisciple, clones fresh, and runs local setup-vps.ps1

$ROOT = "C:\thedisciple"
$REPO = "https://github.com/VYLUXTECH/FUTURES.git"

# Clean old dirs
Remove-Item -Recurse -Force "C:\thedisciple-bot" -ErrorAction SilentlyContinue
if (Test-Path $ROOT) {
    $retries = 5
        while ($retries -gt 0 -and (Test-Path $ROOT)) {
                try { Remove-Item -Recurse -Force $ROOT -ErrorAction Stop; break } catch {}
                        try { cmd /c "rmdir /S /Q $ROOT 2>nul" } catch {}
                                Start-Sleep -Seconds 3
                                        $retries--
                                            }
                                            }
                                            git clone $REPO $ROOT
                                            & "$ROOT\scripts\setup-vps.ps1"
                                            