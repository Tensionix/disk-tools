param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('main', 'pairs', 'profiles', 'tools', 'builder', 'path_input')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$FzfExe,

    [Parameter(Mandatory = $true)]
    [string]$ResultFile,

    [string]$PythonCmd,
    [string]$PythonArgs,
    [string]$MainPy,
    [string]$PairsConfig
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $FzfExe)) {
    exit 1
}

function Save-Result {
    param(
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    Set-Content -LiteralPath $ResultFile -Value $Value -NoNewline -Encoding ascii
}

function Invoke-FzfSelection {
    param(
        [string[]]$Lines,
        [string]$Prompt
    )

    if (-not $Lines -or $Lines.Count -eq 0) {
        return $null
    }

    $selection = $Lines | & $FzfExe `
        --prompt $Prompt `
        --with-nth 2.. `
        --layout reverse `
        --border rounded `
        --info inline `
        --height 100%
    if ([string]::IsNullOrWhiteSpace($selection)) {
        return $null
    }

    return ($selection -split "`t", 2)[0].Trim()
}

switch ($Mode) {
    'main' {
        $lines = @(
            "manifest`t[01] Create manifest"
            "manifest_nocloud`t[02] Create manifest no cloud roots"
            "verify`t[03] Verify manifest"
            "compare_quick`t[04] Compare one-way quick"
            "compare_safe`t[05] Compare one-way safe"
            "backup_safe`t[06] Backup mirror safe"
            "backup_dry`t[07] Dry run backup mirror safe"
            "sync_safe`t[08] Sync one-way safe"
            "sync_dry`t[09] Dry run sync one-way safe"
            "sync2_safe`t[10] Full sync two-way safe"
            "sync2_dry`t[11] Dry run full sync two-way safe"
            "profiles`t[12] Configured profiles launcher"
            "open_output`t[13] Open output folder"
            "open_logs`t[14] Open logs folder"
            "open_config`t[15] Open config folder"
            "tools`t[16] Tools launcher"
            "builder`t[17] Builder main"
            "exit`t[00] Exit"
        )

        $result = Invoke-FzfSelection -Lines $lines -Prompt 'Select action: '
        if ($result) {
            Save-Result -Value $result
        }
    }

    'profiles' {
        $lines = @(
            "list_profiles`t[01] List configured profiles"
            "compare_profile`t[02] Compare configured profile"
            "sync_profile`t[03] Run profile-defined mode"
            "dry_profile`t[04] Dry run profile-defined mode"
            "back`t[00] Back"
        )

        $result = Invoke-FzfSelection -Lines $lines -Prompt 'Select profile action: '
        if ($result) {
            Save-Result -Value $result
        }
    }

    'tools' {
        $lines = @(
            "doctor`t[01] Env doctor"
            "info`t[02] Show project info"
            "open_core`t[03] Open system_core"
            "open_install`t[04] Open install"
            "open_output`t[05] Open output"
            "open_logs`t[06] Open logs"
            "open_release`t[07] Open release"
            "back`t[00] Back"
        )

        $result = Invoke-FzfSelection -Lines $lines -Prompt 'Select tool: '
        if ($result) {
            Save-Result -Value $result
        }
    }

    'builder' {
        $lines = @(
            "build_cmd`t[01] Build portable env CMD builder"
            "build_ps`t[02] Build portable env PS"
            "install_offline`t[03] Install portable offline"
            "verify`t[04] Verify portable env"
            "update_fzf`t[05] Update fzf"
            "release`t[06] Make release archive"
            "open_install`t[07] Open install"
            "open_runtime`t[08] Open runtime"
            "open_wheels`t[09] Open wheelhouse"
            "open_release`t[10] Open release"
            "project`t[11] Project launcher"
            "exit`t[00] Exit"
        )

        $result = Invoke-FzfSelection -Lines $lines -Prompt 'Select step: '
        if ($result) {
            Save-Result -Value $result
        }
    }

    'path_input' {
        $lines = @(
            "manual`t[01] Type paths manually"
            "picker`t[02] Pick folders with dialog"
        )

        $result = Invoke-FzfSelection -Lines $lines -Prompt 'Select path input: '
        if ($result) {
            Save-Result -Value $result
        }
    }

    'pairs' {
        if ([string]::IsNullOrWhiteSpace($PythonCmd) -or
            [string]::IsNullOrWhiteSpace($MainPy) -or
            [string]::IsNullOrWhiteSpace($PairsConfig)) {
            exit 1
        }

        $pyArgs = @()
        if (-not [string]::IsNullOrWhiteSpace($PythonArgs)) {
            $pyArgs += $PythonArgs
        }
        $pyArgs += @($MainPy, 'pairs', '--pairs-config', $PairsConfig, '--names-only')

        $lines = & $PythonCmd @pyArgs 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $lines) {
            exit 1
        }

        $displayLines = @()
        $index = 1
        foreach ($line in @($lines)) {
            if (-not [string]::IsNullOrWhiteSpace($line)) {
                $displayLines += ("{0}`t[{1:D2}] {2}" -f $line, $index, $line)
                $index++
            }
        }

        $result = Invoke-FzfSelection -Lines $displayLines -Prompt 'Select profile: '
        if ($result) {
            Save-Result -Value $result
        }
    }
}
