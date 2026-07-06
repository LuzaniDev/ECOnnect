# graphify-watch.ps1
# Watches the project for file changes and auto-runs graphify update
# Ideal for real-time sync without needing git commits
# Usage: .\scripts\graphify-watch.ps1

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = "$PSScriptRoot\.."
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true
$watcher.NotifyFilter = [System.IO.NotifyFilters]::FileName -bor [System.IO.NotifyFilters]::LastWrite -bor [System.IO.NotifyFilters]::DirectoryName

$ignoreDirs = @('node_modules', '.git', '__pycache__', '.venv', 'graphify-out', '.opencode')
$changed = $false
$timer = $null

$action = {
    $path = $Event.SourceEventArgs.FullPath
    $dir = (Get-Item $path).DirectoryName
    foreach ($ignore in $ignoreDirs) {
        if ($dir -match [regex]::Escape($ignore)) { return }
        if ($path -match [regex]::Escape($ignore)) { return }
    }
    if ($path -match '\.(py|js|ts|vue|html|css|json|sql|md)$') {
        $script:changed = $true
    }
}

Register-ObjectEvent $watcher "Created" -Action $action > $null
Register-ObjectEvent $watcher "Changed" -Action $action > $null
Register-ObjectEvent $watcher "Deleted" -Action $action > $null
Register-ObjectEvent $watcher "Renamed" -Action $action > $null

Write-Host "graphify-watch: monitoring for changes... (Ctrl+C to stop)" -ForegroundColor Cyan

while ($true) {
    Start-Sleep -Seconds 5
    if ($changed) {
        Start-Sleep -Seconds 2
        $changed = $false
        Write-Host "`n[graphify] Change detected, updating graph..." -ForegroundColor Yellow
        $env:Path += ";$env:USERPROFILE\AppData\Local\Python\pythoncore-3.14-64\Scripts"
        & graphify update "$PSScriptRoot\.." 2>&1 | ForEach-Object { Write-Host $_ }
        Write-Host "[graphify] Graph updated." -ForegroundColor Green
    }
}
