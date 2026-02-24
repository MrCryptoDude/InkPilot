$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = $ws.CreateShortcut("$desktop\Inkpilot.lnk")
$shortcut.TargetPath = "C:\Users\georg\Foundry-projects\Inkpilot\dist\Inkpilot\Inkpilot.exe"
$shortcut.IconLocation = "C:\Users\georg\Foundry-projects\Inkpilot\assets\inkpilot.ico"
$shortcut.Description = "Inkpilot - Claude x Inkscape"
$shortcut.Save()
Write-Host "Shortcut created on Desktop!"
