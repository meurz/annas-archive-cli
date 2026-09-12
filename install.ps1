# Install a verified standalone release for Windows x86_64 without Python or admin rights.
param(
    [string]$Version = $(if ($env:ANNA_VERSION) { $env:ANNA_VERSION } else { 'latest' }),
    [string]$InstallDir = $(if ($env:ANNA_INSTALL_DIR) { $env:ANNA_INSTALL_DIR } else {
        Join-Path $env:LOCALAPPDATA 'Programs\anna'
    })
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = 'meurz/annas-archive-cli'
$releaseBase = if ($env:ANNA_RELEASE_BASE) { $env:ANNA_RELEASE_BASE } else {
    "https://github.com/$repo/releases/download"
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -ne 'X64') {
    throw 'Only Windows x86_64 standalone releases are currently supported.'
}
if ($Version -eq 'latest') {
    $Version = (Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest").tag_name
}
if ($Version -notmatch '^v[0-9][0-9A-Za-z.-]*$') { throw 'Invalid release tag.' }
$asset = "anna-$Version-windows-x86_64.zip"
$temporary = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
$staged = $null
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $archive = Join-Path $temporary $asset
    Invoke-WebRequest "$releaseBase/$Version/$asset" -OutFile $archive -UseBasicParsing
    $checksums = (Invoke-WebRequest "$releaseBase/$Version/SHA256SUMS" -UseBasicParsing).Content
    if ($checksums -is [byte[]]) { $checksums = [Text.Encoding]::UTF8.GetString($checksums) }
    $pattern = '(?m)^([a-f0-9]{64})\s+' + [regex]::Escape($asset) + '\r?$'
    $matchesFound = [regex]::Matches($checksums, $pattern)
    if ($matchesFound.Count -ne 1) { throw 'Missing or ambiguous checksum.' }
    $expected = $matchesFound[0].Groups[1].Value
    if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw 'SHA-256 verification failed; nothing was installed.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $entry = $zip.GetEntry('anna.exe')
        if (-not $entry) { throw 'Release does not contain anna.exe.' }
        $executable = Join-Path $temporary 'anna.exe'
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $executable)
    } finally { $zip.Dispose() }
    & $executable --version
    if ($LASTEXITCODE -ne 0) { throw 'Executable smoke test failed.' }
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $staged = Join-Path $InstallDir ('.anna-install-' + [Guid]::NewGuid() + '.exe')
    Copy-Item $executable $staged
    $destination = Join-Path $InstallDir 'anna.exe'
    if (Test-Path $destination) {
        [IO.File]::Replace($staged, $destination, [System.Management.Automation.Language.NullString]::Value)
    } else {
        [IO.File]::Move($staged, $destination)
    }
    Write-Host "Installed $destination"
    if (($env:PATH -split ';') -notcontains $InstallDir) {
        Write-Host "Add $InstallDir to your user PATH to run anna from any directory."
    }
} finally {
    if ($staged -and (Test-Path $staged)) { Remove-Item $staged -Force }
    Remove-Item $temporary -Recurse -Force
}
