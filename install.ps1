<#
  gm-llm — one-shot Windows installer.

  Run it straight from PowerShell (no download, no cloning first):

      irm https://raw.githubusercontent.com/KarlJussila/gm-llm/main/install.ps1 | iex

  It installs everything gm-llm needs and leaves a ready-to-play campaign folder.
  The ONE thing it can't do for you is log opencode in to a model provider — that's
  interactive — so it prints the exact command to run at the end.

  Idempotent: safe to re-run. Anything already installed is skipped.
  No admin needed for the per-user installs; winget may pop a UAC prompt for git/python/node.
#>

$ErrorActionPreference = 'Stop'

# Bypass the machine's script-execution policy for THIS process (no admin, nothing persisted)
# so this run can call Node's unsigned `npm.ps1` shim.
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force } catch {}
# Also relax the *persistent* CurrentUser policy to RemoteSigned (still no admin) so the
# npm-installed shims the player later runs by hand — notably `opencode auth login` — aren't
# blocked as unsigned. RemoteSigned allows local scripts, still blocks unsigned web downloads.
try { Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force } catch {}

$RepoUrl     = 'https://github.com/KarlJussila/gm-llm.git'
$RepoDir     = Join-Path $HOME 'gm-llm'          # the tool's source checkout
$CampaignDir = Join-Path $HOME 'my-campaign'     # the playable project it scaffolds

function Say  ($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "    $([char]0x2713) $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "    ! $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host "`nX  $m" -ForegroundColor Red; throw $m }

# Pull the current Machine+User PATH into this session so tools installed a moment ago
# (winget, pipx, npm -g) are callable without restarting the terminal.
function Sync-Path {
  $parts = @(
    [Environment]::GetEnvironmentVariable('Path','Machine'),
    [Environment]::GetEnvironmentVariable('Path','User')
  ) | Where-Object { $_ }
  $env:Path = ($parts -join ';')
}

# Install a winget package only if its command isn't already on PATH. winget's "already
# installed / no update" exit codes are not failures, so we judge success by the command
# reappearing, not by winget's exit code.
function Ensure-WingetPackage($Command, $Id, $Label) {
  Sync-Path
  if (Get-Command $Command -ErrorAction SilentlyContinue) { Ok "$Label already present"; return }
  Say "Installing $Label (winget: $Id)"
  winget install --id $Id -e --source winget `
    --accept-source-agreements --accept-package-agreements | Out-Host
  Sync-Path
  if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
    Die "$Label still isn't on PATH after install. Close this window, open a NEW PowerShell, and re-run the installer."
  }
  Ok "$Label installed"
}

Write-Host "gm-llm installer" -ForegroundColor Magenta

# --- 0. winget must exist (Windows 11, or Windows 10 with App Installer) ---
Sync-Path
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Die "winget not found. Install 'App Installer' from the Microsoft Store (search: App Installer), then re-run this."
}

# --- 1. base tools ---
Ensure-WingetPackage 'git'    'Git.Git'            'Git'
Ensure-WingetPackage 'python' 'Python.Python.3.12' 'Python 3.12'
Ensure-WingetPackage 'node'   'OpenJS.NodeJS'      'Node.js'
# Nicer terminal for the TUI (cmd.exe renders it poorly). Optional — don't fail if it won't install.
if (-not (Get-Command wt -ErrorAction SilentlyContinue)) {
  Say "Installing Windows Terminal (best for the game UI)"
  try {
    winget install --id Microsoft.WindowsTerminal -e --source winget `
      --accept-source-agreements --accept-package-agreements | Out-Host
    Ok "Windows Terminal installed"
  } catch { Warn "couldn't install Windows Terminal — not required, continuing" }
}

# --- 2. opencode (the model runtime gm-llm drives) ---
# Call npm.cmd, not npm: the bare name resolves to Node's unsigned npm.ps1, which a locked-down
# execution policy blocks; the .cmd shim sidesteps that entirely.
Say "Installing opencode"
npm.cmd install -g --allow-scripts=opencode-ai opencode-ai | Out-Host
Sync-Path
if (Get-Command opencode -ErrorAction SilentlyContinue) { Ok "opencode installed" }
else { Warn "opencode not on PATH yet — a new terminal will pick it up" }

# --- 3. pipx + the gm-llm command ---
Say "Installing pipx"
python -m pip install --user --upgrade pipx | Out-Host
python -m pipx ensurepath | Out-Host
Sync-Path

Say "Fetching gm-llm"
if (Test-Path (Join-Path $RepoDir '.git')) {
  git -C $RepoDir pull --ff-only | Out-Host
  Ok "updated $RepoDir"
} else {
  git clone $RepoUrl $RepoDir | Out-Host
  Ok "cloned to $RepoDir"
}

Say "Installing the gm-llm command"
python -m pipx install $RepoDir --force | Out-Host
Sync-Path

# Resolve the gm-llm executable. PATH may not reflect pipx's bin dir in THIS session even
# after ensurepath, so if it's not on PATH, ask pipx itself where it puts app binaries
# (authoritative — never guess the directory).
$gmllm = (Get-Command gm-llm -ErrorAction SilentlyContinue).Source
if (-not $gmllm) {
  $cands = @()
  $binDir = (python -m pipx environment --value PIPX_BIN_DIR 2>$null)
  if ($binDir) { $cands += (Join-Path $binDir.Trim() 'gm-llm.exe') }
  $cands += (Join-Path $HOME '.local\bin\gm-llm.exe')
  foreach ($cand in $cands) {
    if (Test-Path $cand) { $gmllm = $cand; break }
  }
}

# --- 4. scaffold a playable campaign folder (also installs the .opencode plugin deps) ---
if ($gmllm) {
  Ok "gm-llm ready"
  Say "Creating your campaign folder"
  & $gmllm init $CampaignDir | Out-Host
  Ok "campaign scaffolded at $CampaignDir"
} else {
  # gm-llm is installed (pipx succeeded) but its bin dir isn't visible in this session.
  # A fresh terminal will have it on PATH — don't fail the whole install; guide the last step.
  Warn "gm-llm installed, but not callable in this window yet."
  Warn "Open a NEW terminal and run:  gm-llm init $CampaignDir"
}

# --- done: the one manual, interactive step remains ---
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " gm-llm is installed. Two commands left to start playing:" -ForegroundColor Green
Write-Host "============================================================`n" -ForegroundColor Green
Write-Host "  1. Log opencode in to a model provider (one time):" -ForegroundColor White
Write-Host "       opencode auth login`n" -ForegroundColor Yellow
Write-Host "  2. Start your campaign:" -ForegroundColor White
Write-Host "       cd $CampaignDir" -ForegroundColor Yellow
Write-Host "       gm-llm play`n" -ForegroundColor Yellow
Write-Host "  (If either command isn't found, open a NEW terminal window first —" -ForegroundColor DarkGray
Write-Host "   for the best display use Windows Terminal, not the old cmd.exe.)`n" -ForegroundColor DarkGray
