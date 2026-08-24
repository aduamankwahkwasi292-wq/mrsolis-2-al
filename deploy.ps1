# Deploys the current state of main to GitHub Pages (gh-pages branch).
# Usage:  powershell -ExecutionPolicy Bypass -File deploy.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if ((git rev-parse --abbrev-ref HEAD) -ne 'main') { throw "Switch to main before deploying." }
if (git status --porcelain) { Write-Warning "Uncommitted changes detected - deploying the last COMMITTED state of main." }

$wt = Join-Path (Split-Path $PSScriptRoot -Parent) 'mrsolis-site-deploy'
try {
    # Fresh gh-pages worktree (create the branch if this clone lacks it)
    git worktree prune
    if (-not (Test-Path $wt)) {
        if (git show-ref --verify --quiet refs/heads/gh-pages) { git worktree add $wt gh-pages | Out-Null }
        else { git worktree add -b gh-pages $wt | Out-Null }
    }

    # Wipe previous bundle, copy exactly what the site serves
    Set-Location $wt
    if (Test-Path .git) { } # keep .git
    Get-ChildItem -Force | Where-Object Name -ne '.git' | Remove-Item -Recurse -Force
    Copy-Item "$PSScriptRoot\mrsolis-2-al.html" .\index.html
    Copy-Item "$PSScriptRoot\mrsolis-2-al.html" .
    Copy-Item "$PSScriptRoot\qgen" .\qgen -Recurse
    New-Item -ItemType File .nojekyll -Force | Out-Null

    # Never ship build junk / local data
    Remove-Item .\qgen\__pycache__ -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item .\qgen\*.sqlite3 -Force -ErrorAction SilentlyContinue

    git add -A
    if (git diff --cached --quiet) {
        Write-Output "Site already up to date - nothing to deploy."
    } else {
        $sha = git rev-parse --short HEAD
        git commit -m "Deploy site from main@$sha"
        git push origin gh-pages
        Write-Output "Deployed. Live in ~1 min at https://aduamankwahkwasi292-wq.github.io/mrsolis-2-al/"
    }
}
finally {
    Set-Location $PSScriptRoot
    git worktree remove $wt --force 2>$null
    git worktree prune
}
