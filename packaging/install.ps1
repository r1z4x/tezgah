<#
.SYNOPSIS
  Install tezgah on Windows - the only Windows entry point.

.DESCRIPTION
  Fetches one release version, checks its SHA256 against the release's .sha256,
  unpacks it under <Prefix>\<Version> and points <Prefix>\current at it, then
  runs the installer from that tree (bin\tezgah-setup --install).

  It assumes no `sh`, no `python3` and no symlinks:

    * unpacking uses the `tar.exe` that ships with Windows 10 1803+ (bsdtar),
      which reads .tar.gz; there is no Expand-Archive path for this archive.
    * `current` is a directory junction, not a symlink: a symlink needs
      SeCreateSymbolicLinkPrivilege (admin or Developer Mode), a junction does
      not. If the junction is refused anyway (a redirected or read-only profile
      folder, a network path), the tree is copied instead, and a later install
      or upgrade re-materialises it - so `current` is always a directory that
      resolves, link or copy.
    * the installer is started with the first Python found: `py -3`, `python`,
      then `python3`.

  The `irm ... | iex` shape takes no arguments - a piped script cannot bind
  parameters - so set the environment first:

      $env:TEZGAH_VERSION = '0.16.1'; irm https://raw.githubusercontent.com/r1z4x/tezgah/main/packaging/install.ps1 | iex

.EXAMPLE
  .\install.ps1 -Version 0.16.1 -Prefix D:\tezgah
#>
[CmdletBinding()]
param(
    [string]$Version,
    [string]$Prefix,
    [string]$Repo = 'r1z4x/tezgah'
)

$ErrorActionPreference = 'Stop'

# A junction target must be a local absolute path, so resolve once, here.
function Resolve-Full([string]$Path) {
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Path))
}

# Replacing `current`: the junction is deleted as the link it is. -Recurse on a
# reparse point would follow it and delete the version tree it points at.
function Remove-Current([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        [IO.Directory]::Delete($Path, $false)
    } else {
        [IO.Directory]::Delete($Path, $true)      # a copy from an earlier fallback
    }
}

if ($env:TEZGAH_REPO) { $Repo = $env:TEZGAH_REPO }
if (-not $Version) { $Version = $env:TEZGAH_VERSION }
if (-not $Prefix) { $Prefix = $env:TEZGAH_PREFIX }
if (-not $Prefix) { $Prefix = Join-Path $env:LOCALAPPDATA 'tezgah' }   # Windows' data dir
$Prefix = Resolve-Full $Prefix
if (-not $Version) {
    try {
        $rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
        $Version = "$($rel.tag_name)".TrimStart('v')
    } catch {
        throw "tezgah: cannot read the newest release of $Repo (no release yet, or no network): $_"
    }
}
if (-not $Version -or $Version -match '[\\/]' -or $Version -in @('.', '..')) {
    throw "tezgah: bad version '$Version' (want X.Y.Z)"
}

$name = "tezgah-$Version.tar.gz"
New-Item -ItemType Directory -Force -Path $Prefix | Out-Null
$work = Join-Path ([IO.Path]::GetTempPath()) ("tezgah-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
    $archive = Join-Path $work $name
    # TEZGAH_DIST is the offline seam upgrade.sh has too: a directory holding the
    # artifacts build.sh wrote, in place of the release URL.
    if ($env:TEZGAH_DIST) {
        $archive = Join-Path (Resolve-Full $env:TEZGAH_DIST) $name
        if (-not (Test-Path -LiteralPath $archive)) { throw "tezgah: no $archive" }
    } else {
        $base = "https://github.com/$Repo/releases/download/v$Version"
        try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
        Invoke-WebRequest -UseBasicParsing "$base/$name" -OutFile $archive
    }
    $sidecar = "$archive.sha256"
    if (-not $env:TEZGAH_DIST) {
        Invoke-WebRequest -UseBasicParsing "$base/$name.sha256" -OutFile $sidecar
    }

    $want = ((Get-Content -LiteralPath $sidecar -Raw).Trim() -split '\s+')[0]
    if (-not $want) { throw "tezgah: $name.sha256 carries no digest" }
    $got = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower()
    if ($want.ToLower() -ne $got) {
        throw "tezgah: checksum mismatch for $name`: recorded $want, downloaded $got"
    }
    Write-Output "ok      verified $name ($got)"

    $dest = Join-Path $Prefix $Version
    if (Test-Path -LiteralPath $dest) {
        Write-Output "ok      kept $dest (already unpacked)"
    } else {
        if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
            throw "tezgah: tar.exe is required (Windows 10 1803+ ships it) - cannot unpack $name"
        }
        # Unpack beside the destination and rename it into place: a failed unpack
        # leaves no half tree where a version is expected, and `current` is only
        # touched after this point.
        $part = Join-Path $Prefix ".$Version.part"
        Remove-Item -LiteralPath $part -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $part | Out-Null
        & tar.exe -xzf $archive -C $part
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -LiteralPath $part -Recurse -Force -ErrorAction SilentlyContinue
            throw "tezgah: cannot unpack $name"
        }
        Move-Item -LiteralPath $part -Destination $dest
        Write-Output "ok      unpacked $dest"
    }

    $current = Join-Path $Prefix 'current'
    $old = $null
    if (Test-Path -LiteralPath $current) {
        $old = (Get-Item -LiteralPath $current -Force).Target
    }
    Remove-Current $current
    try {
        New-Item -ItemType Junction -Path $current -Target $dest | Out-Null
    } catch {
        # No privilege, no junction: a copy needs none, and the next install or
        # upgrade replaces it with a junction when one can be made.
        Write-Output "note    junction refused ($($_.Exception.Message.Trim())) - copied instead"
        Copy-Item -LiteralPath $dest -Destination $current -Recurse -Force
    }
    if ($old) { Write-Output "ok      current -> $Version (was $old, still installed)" }
    else { Write-Output "ok      current -> $Version" }

    $setup = Join-Path $current 'bin\tezgah-setup'
    $py = $null
    foreach ($cand in @('py', 'python', 'python3')) {
        if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
    }
    if (-not $py) { throw "tezgah: no python on PATH (py, python or python3) to run $setup" }
    if ($py -eq 'py') { & py -3 $setup --install } else { & $py $setup --install }
    exit $LASTEXITCODE
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
