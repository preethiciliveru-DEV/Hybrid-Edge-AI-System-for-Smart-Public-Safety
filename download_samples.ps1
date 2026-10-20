# Download small sample images from Wikimedia Commons into a local folder for review
# Usage: Open PowerShell and run: .\download_samples.ps1

$outRoot = "C:\Users\preethi ciliveru\OneDrive\Documents\PlatformIO\Projects\HybridSafetyESP32\dataset_samples"
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

$classes = @{
    'kitchen_knife' = @('kitchen knife','chef knife')
    'scissors' = @('scissors','hair scissors')
    'pistol' = @('pistol','handgun')
    'rifle' = @('rifle','hunting rifle')
}
$negQueries = @('spoon','fork','phone','remote control','screwdriver','toy gun')
$perClassTarget = 50
$negTarget = 200

function Get-WikiImageUrls($query, $limit) {
    $api = 'https://commons.wikimedia.org/w/api.php'
    $params = @{ action='query'; generator='search'; gsrsearch=$query; gsrlimit=$limit; prop='imageinfo'; iiprop='url|mime|size'; format='json' }
    $pairs = $params.GetEnumerator() | ForEach-Object { $_.Key + '=' + [uri]::EscapeDataString($_.Value.ToString()) }
    $uri = $api + '?' + ($pairs -join '&')
    try {
        $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 30 -Headers @{ 'User-Agent' = 'DatasetDownloader/1.0 (your-email@example.com)'}
        $urls = @()
        if ($r.query -and $r.query.pages) {
            $pages = $r.query.pages
            foreach ($prop in $pages.PSObject.Properties) {
                $page = $prop.Value
                if ($page.imageinfo) {
                    foreach ($ii in $page.imageinfo) {
                        if ($ii.mime -and $ii.mime -like 'image/*' -and $ii.size -gt 10000) {
                            $urls += $ii.url
                        }
                    }
                }
            }
        }
        return $urls | Select-Object -Unique
    } catch {
        Write-Host ("Wiki search failed for {0}: {1}" -f $query, $_) -ForegroundColor Yellow
        return @()
    }
}

function Download-Image($url, $outPath) {
    try {
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add('User-Agent','DatasetDownloader/1.0 (your-email@example.com)')
        $wc.DownloadFile($url, $outPath)
        return $true
    } catch {
        Write-Host ("Download failed: {0}" -f $url) -ForegroundColor Red
        return $false
    }
}

# IMPORTANT: Wikimedia enforces rate limits. This script waits between requests. Do not run many concurrent copies.

foreach ($cls in $classes.Keys) {
    $clsDir = Join-Path $outRoot $cls
    New-Item -ItemType Directory -Force -Path $clsDir | Out-Null
    $col = 0
    foreach ($q in $classes[$cls]) {
        if ($col -ge $perClassTarget) { break }
        Write-Host ("Searching Wikimedia for '{0}'..." -f $q)
        $urls = Get-WikiImageUrls $q 60
        Start-Sleep -Seconds 2
        foreach ($u in $urls) {
            if ($col -ge $perClassTarget) { break }
            if ($null -eq $u) { continue }
            $lower = $u.ToLower()
            if ($cls -in @('pistol','rifle')) {
                if ($lower -match 'toy' -or $lower -match 'replica' -or $lower -match 'airsoft') { continue }
            }
            if ($cls -eq 'kitchen_knife') {
                if ($lower -match 'butter' -or $lower -match 'spoon' -or $lower -match 'plastic') { continue }
            }
            $fname = [System.IO.Path]::GetFileName($u.Split('?')[0])
            $out = Join-Path $clsDir ($col.ToString('D4') + '_' + $fname)
            if (Test-Path $out) { continue }
            Start-Sleep -Milliseconds 800
            $ok = Download-Image $u $out
            if ($ok) { $col++ ; if ($col % 10 -eq 0) { Write-Host ("Downloaded {0}/{1} for {2}" -f $col, $perClassTarget, $cls) } }
            Start-Sleep -Milliseconds 800
        }
    }
    Write-Host ("Class {0} download finished: {1} images" -f $cls, (Get-ChildItem -Path $clsDir -File).Count)
}

# Negatives
$negDir = Join-Path $outRoot 'negatives'
New-Item -ItemType Directory -Force -Path $negDir | Out-Null
$negCollected = 0
foreach ($q in $negQueries) {
    if ($negCollected -ge $negTarget) { break }
    Write-Host ("Searching Wikimedia for negative query '{0}'..." -f $q)
    $urls = Get-WikiImageUrls $q 80
    Start-Sleep -Seconds 2
    foreach ($u in $urls) {
        if ($negCollected -ge $negTarget) { break }
        if ($null -eq $u) { continue }
        $lower = $u.ToLower()
        if ($lower -match 'pistol' -or $lower -match 'rifle' -or $lower -match 'gun') { continue }
        $fname = [System.IO.Path]::GetFileName($u.Split('?')[0])
        $out = Join-Path $negDir ($negCollected.ToString('D5') + '_' + $fname)
        if (Test-Path $out) { continue }
        Start-Sleep -Milliseconds 800
        $ok = Download-Image $u $out
        if ($ok) { $negCollected++ ; if ($negCollected % 50 -eq 0) { Write-Host ("Downloaded {0} negatives" -f $negCollected) } }
        Start-Sleep -Milliseconds 800
    }
}
Write-Host ("Negative download finished: {0} images" -f (Get-ChildItem -Path $negDir -File).Count)
Write-Host "Sample download complete. Root: $outRoot"
