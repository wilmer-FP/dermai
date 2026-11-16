# Run from an authenticated Windows terminal. No tokens are printed or written to disk.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location -LiteralPath $repoRoot
try {
    gh auth status --hostname github.com
    if ($LASTEXITCODE -ne 0) { throw 'Authenticate first: gh auth login --hostname github.com --git-protocol https --web' }
    $visibility = gh repo view wilmer-FP/dermai --json visibility --jq '.visibility'
    if ($LASTEXITCODE -ne 0 -or $visibility -ne 'PUBLIC') { throw 'Requires the public repository; private/paid deployment is not allowed.' }
    $changes = git status --porcelain
    if ($changes) { throw 'Commit and review the intended changes before publication. Worktree must be clean.' }
    npm.cmd ci --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    npm.cmd test --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'Frontend verification failed' }
    $env:VITE_BASE_PATH = '/dermai/'
    $env:VITE_ANALYSIS_MODE = 'browser'
    npm.cmd run build --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'Production build failed' }
    git fetch origin main
    if ($LASTEXITCODE -ne 0) { throw 'Cannot fetch remote branch' }
    git merge-base --is-ancestor origin/main HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Remote main changed; integrate and revalidate it. Never force-push.' }
    $hasPages = gh api repos/wilmer-FP/dermai --jq '.has_pages'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read repository Pages configuration.' }
    if ($hasPages -eq 'true') {
        gh api --method PUT repos/wilmer-FP/dermai/pages -f build_type=workflow --silent
    } else {
        gh api --method POST repos/wilmer-FP/dermai/pages -f build_type=workflow --silent
    }
    if ($LASTEXITCODE -ne 0) { throw 'Cannot configure Pages; requires repository administration permission.' }
    git push origin HEAD:main
    if ($LASTEXITCODE -ne 0) { throw 'Push failed. Nothing is force-pushed.' }
    $sha = git rev-parse HEAD
    gh workflow run deploy-frontend.yml --ref main
    if ($LASTEXITCODE -ne 0) { throw 'Cannot start deployment. Check Actions permissions.' }
    $runId = $null
    for ($attempt = 0; $attempt -lt 24 -and -not $runId; $attempt++) {
        Start-Sleep -Seconds 5
        $runs = gh run list --workflow deploy-frontend.yml --commit $sha --limit 1 --json databaseId | ConvertFrom-Json
        if ($runs.Count -gt 0) { $runId = $runs[0].databaseId }
    }
    if (-not $runId) { throw 'No deployment run found. Inspect GitHub Actions.' }
    gh run watch $runId --exit-status
    if ($LASTEXITCODE -ne 0) { throw 'Deployment failed. Inspect the run logs.' }
    $url = 'https://wilmer-fp.github.io/dermai/'
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    if ($response.StatusCode -ne 200) { throw 'Public URL is not responding with HTTP 200.' }
    $remoteModel = Invoke-RestMethod -Uri ($url + 'models/dermai/manifest.json')
    $localModel = Get-Content frontend/public/models/dermai/manifest.json -Raw | ConvertFrom-Json
    if ($remoteModel.sha256 -ne $localModel.sha256) { throw 'Public model manifest differs from the verified model.' }
    Write-Host "Published: $url"
    Write-Host "Model: $($remoteModel.name) v$($remoteModel.version) | SHA-256 $($remoteModel.sha256)"
    Write-Host 'Final check: select the experimental model in the public web and analyze a synthetic image.'
} finally {
    Pop-Location
}
