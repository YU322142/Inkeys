param([string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$fixRepo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $fixRepo 'Build/PptCloseFix' }
$fixOut = [IO.Path]::GetFullPath($OutputDirectory)
if ($fixOut -eq (Join-Path $fixRepo 'Inkeys')) { throw 'Use a separate build output directory.' }
New-Item -ItemType Directory -Path $fixOut -Force | Out-Null
$fixDotnet = (Get-Command dotnet -ErrorAction Stop).Source
$fixSdkRoot = Join-Path (Split-Path -Parent $fixDotnet) 'sdk'
$fixCompiler = Get-ChildItem -LiteralPath $fixSdkRoot -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'Roslyn/bincore/csc.dll') } |
    Sort-Object { [version]($_.Name.Split('-')[0]) } -Descending |
    Select-Object -First 1
if (-not $fixCompiler) { throw 'A .NET SDK with Roslyn csc.dll is required.' }
$fixCsc = Join-Path $fixCompiler.FullName 'Roslyn/bincore/csc.dll'
$fixFramework = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319'
if (-not (Test-Path -LiteralPath $fixFramework)) { $fixFramework = Join-Path $env:WINDIR 'Microsoft.NET/Framework/v4.0.30319' }
$fixRefs = @('/nologo','/unsafe','/optimize+')
foreach ($name in @('mscorlib','System','System.Core','Microsoft.CSharp','System.Windows.Forms','System.Web.Extensions')) {
    $path = Join-Path $fixFramework ($name + '.dll')
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing .NET Framework dependency: $path" }
    $fixRefs += '/r:' + $path
}
foreach ($name in @('Microsoft.Office.Interop.PowerPoint','office')) {
    $gac = Join-Path $env:WINDIR ('assembly/GAC_MSIL/' + $name)
    $interop = Get-ChildItem -LiteralPath $gac -Filter ($name + '.dll') -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $interop) { throw "Missing installed Office interop assembly: $name; restore the upstream project's interop packages for a project build instead." }
    $fixRefs += '/link:' + $interop.FullName
}
$fixSources = (Get-ChildItem (Join-Path $fixRepo 'PptCOM') -Filter '*.cs').FullName
& $fixDotnet $fixCsc @fixRefs /target:library "/out:$fixOut/PptCOM.dll" @fixSources (Join-Path $fixRepo 'PptCOM/Properties/AssemblyInfo.cs')
if ($LASTEXITCODE -ne 0) { throw 'PptCOM compilation failed.' }
$fixTests = (Get-ChildItem (Join-Path $fixRepo 'PptCOM.Tests') -Filter '*.cs').FullName
& $fixDotnet $fixCsc @fixRefs /target:exe "/out:$fixOut/PptCOM.Tests.exe" "/r:$fixOut/PptCOM.dll" @fixTests
if ($LASTEXITCODE -ne 0) { throw 'Managed test compilation failed.' }
'<configuration><startup><supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.0"/></startup></configuration>' |
    Set-Content -LiteralPath (Join-Path $fixOut 'PptCOM.Tests.exe.config') -Encoding UTF8
& (Join-Path $fixOut 'PptCOM.Tests.exe')
if ($LASTEXITCODE -ne 0) { throw 'Managed tests failed.' }
Write-Output "PASS: managed build and test suite; outputs: $fixOut"
