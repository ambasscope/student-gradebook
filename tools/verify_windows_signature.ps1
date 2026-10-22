param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][string]$ExpectedPublisher
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    if ([string]::IsNullOrWhiteSpace($ExpectedPublisher)) {
        throw 'Configure the exact validated certificate subject before packaging a signed release.'
    }
    $path = (Resolve-Path -LiteralPath $FilePath).Path
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    if ($signature.Status.ToString() -ne 'Valid') {
        throw "Signature is not trusted: $($signature.Status)."
    }
    if ($signature.SignatureType.ToString() -ne 'Authenticode') {
        throw 'An embedded Authenticode signature is required.'
    }
    if ($null -eq $signature.SignerCertificate -or $signature.SignerCertificate.Subject -cne $ExpectedPublisher) {
        throw 'The signing certificate does not match the configured publisher.'
    }
    if ($null -eq $signature.TimeStamperCertificate) {
        throw 'A trusted timestamp is required.'
    }
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        $tool = $command.Source
    } else {
        $sdk = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin\*\x64\signtool.exe'
        $tool = Get-ChildItem -Path $sdk -ErrorAction SilentlyContinue |
            Sort-Object { [version]$_.Directory.Parent.Name } -Descending |
            Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $tool) { throw 'Windows SDK SignTool is required to verify a signed release.' }
    $verification = & $tool verify /pa /all /tw /v $path 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool verification failed or reported warnings: $verification"
    }
    [ordered]@{
        status = 'Valid'
        signature_type = 'Authenticode'
        publisher = $signature.SignerCertificate.Subject
        certificate_thumbprint = $signature.SignerCertificate.Thumbprint
        timestamp_publisher = $signature.TimeStamperCertificate.Subject
        executable_sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    } | ConvertTo-Json -Compress
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
