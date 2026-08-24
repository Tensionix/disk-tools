param(
    [Parameter(Mandatory = $true)]
    [string]$ResultFile,

    [string]$Description = 'Select folder'
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms

$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = $Description
$dialog.ShowNewFolderButton = $false

$result = $dialog.ShowDialog()
if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
    exit 1
}

$selectedPath = $dialog.SelectedPath
if ([string]::IsNullOrWhiteSpace($selectedPath)) {
    exit 1
}

Set-Content -LiteralPath $ResultFile -Value $selectedPath -NoNewline -Encoding ascii
exit 0
