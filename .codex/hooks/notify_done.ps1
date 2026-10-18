# Windows sound notification for Codex's Stop event. Return JSON without blocking completion.
$ErrorActionPreference = 'Stop'
$player = $null
try {
    $soundPath = Join-Path $env:WINDIR 'Media/Windows Notify System Generic.wav'
    $player = [System.Media.SoundPlayer]::new($soundPath)
    $player.PlaySync()
} catch {
    [Console]::Error.WriteLine("Completion sound failed: $($_.Exception.Message)")
} finally {
    if ($null -ne $player) { $player.Dispose() }
}
[Console]::Out.WriteLine('{}')
exit 0
