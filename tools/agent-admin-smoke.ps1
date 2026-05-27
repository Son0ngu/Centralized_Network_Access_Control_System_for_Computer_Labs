param(
    [string]$ServerUrl = $env:SAINT_SMOKE_SERVER_URL,
    [string]$ApiKey = $env:SAINT_SMOKE_API_KEY,
    [string]$OutputDir = "",
    [switch]$SkipBuild,
    [switch]$NoNetworkSmoke,
    [switch]$EnableFirewallSmoke,
    [switch]$EnableDefaultDenySmoke,
    [ValidateSet("auto", "netsh", "netsecurity")]
    [string]$ReadProvider = "auto",
    [ValidateSet("netsh", "powershell", "netsecurity")]
    [string]$WriteBackend = "netsh",
    [int]$TimeoutSeconds = 15,
    [int]$BuildTimeoutSeconds = 900,
    [string]$FirewallTestIp = "203.0.113.10",
    [switch]$VerboseSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    Write-Error "Run this script from an elevated PowerShell window (Run as Administrator)."
    exit 2
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Runner = Join-Path $RepoRoot "tools\agent_admin_smoke.py"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        Write-Error "Python not found. Expected $VenvPython or python on PATH."
        exit 2
    }
    $Python = $PythonCommand.Source
}

$ArgsList = @(
    $Runner,
    "--read-provider", $ReadProvider,
    "--write-backend", $WriteBackend,
    "--timeout-seconds", "$TimeoutSeconds",
    "--build-timeout-seconds", "$BuildTimeoutSeconds",
    "--firewall-test-ip", $FirewallTestIp
)

if ($ServerUrl) {
    $ArgsList += @("--server-url", $ServerUrl)
}
if ($ApiKey) {
    $ArgsList += @("--api-key", $ApiKey)
}
if ($OutputDir) {
    $ArgsList += @("--output-dir", $OutputDir)
}
if ($SkipBuild) {
    $ArgsList += "--skip-build"
}
if ($NoNetworkSmoke) {
    $ArgsList += "--no-network-smoke"
}
if ($EnableFirewallSmoke) {
    $ArgsList += "--enable-firewall-smoke"
}
if ($EnableDefaultDenySmoke) {
    $ArgsList += "--enable-default-deny-smoke"
}
if ($VerboseSmoke) {
    $ArgsList += "--verbose"
}

Write-Host "Running SAINT agent admin smoke test..."
Write-Host "Repo: $RepoRoot"
Write-Host "Python: $Python"

& $Python @ArgsList
exit $LASTEXITCODE
