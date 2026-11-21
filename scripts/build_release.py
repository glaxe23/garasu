"""Package the public Garasu checkout into a Windows installer and ZIP."""
import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from exe_icon import set_icon


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"install.ps1", "uninstall.ps1", "theme/ryoku.py", "zebar/clock.html"}
PRIVATE_NAMES = {
    ".env", "settings.json", "state.json", "panel_pos.json", "theme.json",
    "widgets.json", "nowplaying.json", "tasks.json", "photos.json",
    "calendar_notes.json", "schedule.json", "pomodoro_state.json", "zpack.json",
    "claude_status.txt", "bar_focus.txt", "classic.on", "classic.off", "classic.tried",
}
PRIVATE_DIRS = {"backup", "profiles", "__pycache__", "thumbs", "pylib"}
PRIVATE_PATTERN = re.compile(
    rb"(?i)(?:[A-Z]:[/\\]+Users[/\\]+[^/\\\s]+[/\\]"
    rb"|[A-Z]:[/\\]+Obsidian Vault\b|gh[pousr]_[a-z0-9]{25,}"
    rb"|github_pat_[a-z0-9_]{25,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
LAUNCHER = r"""@echo off
if not exist "%~dp0files\install.ps1" (
    echo Unpack all files before running Install.bat.
    pause
    exit /b 1
)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0files\install.ps1"
"""
SETUP = r"""@echo off
set "D=%TEMP%\Garasu-setup-%RANDOM%-%RANDOM%"
mkdir "%D%" || exit /b 1
set "Z=%~dp0payload.zip"
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Expand-Archive -LiteralPath $env:Z -DestinationPath $env:D -Force -ErrorAction Stop"
if errorlevel 1 tar -xf "%Z%" -C "%D%"
if not exist "%D%\install.ps1" (
    powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [void][System.Windows.Forms.MessageBox]::Show('Could not unpack the installer. Download Garasu.zip and run Install.bat after unpacking it.', 'Garasu')"
    exit /b 1
)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%D%\install.ps1"
"""
SED = r"""[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName={target}
FriendlyName=Garasu
AppLaunched=cmd /c setup.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0={work}\
[SourceFiles0]
payload.zip=
setup.cmd=
"""


def windows_batch(text):
    return text.replace("\n", "\r\n").encode("ascii")


def package_files(root):
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "files/"], cwd=root
    ).decode("utf-8").split("\0")
    files = {}
    for name in filter(None, names):
        relative = PurePosixPath(name).relative_to("files")
        lower_name = relative.name.lower()
        if (
            lower_name in PRIVATE_NAMES
            or lower_name.startswith(".env.")
            or lower_name.endswith((".before-clean", ".bak", ".log", ".tmp", ".pyc"))
            or PRIVATE_DIRS.intersection(part.lower() for part in relative.parts[:-1])
        ):
            raise ValueError(f"Remove local state from the tracked package: {name}")
        source = root / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Expected a regular file: {name}")
        data = source.read_bytes()
        if (lower_name == "scratch.txt" and data.strip()) or PRIVATE_PATTERN.search(data):
            raise ValueError(f"Personal data or a local path in tracked package: {name}")
        files[relative.as_posix()] = data
    missing = REQUIRED.difference(files)
    if missing:
        raise ValueError(f"Missing package files: {', '.join(sorted(missing))}")
    return files


def write_zip(path, files):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)


def verify_zip(path, files):
    with ZipFile(path) as archive:
        if (
            archive.testzip() is not None
            or len(archive.infolist()) != len(files)
            or {name: archive.read(name) for name in archive.namelist()} != files
        ):
            raise ValueError(f"Unexpected contents in {path.name}")


def verify_installer(exe, work, files):
    data = exe.read_bytes()
    for match in re.finditer(b"MSCF", data):
        offset = match.start()
        if offset + 36 > len(data) or data[offset + 24:offset + 26] != b"\x03\x01":
            continue
        size = struct.unpack_from("<I", data, offset + 8)[0]
        if 36 < size <= len(data) - offset:
            break
    else:
        raise ValueError("Installer is missing its embedded cabinet")
    extracted = work / "verification"
    extracted.mkdir()
    cabinet = work / "setup.cab"
    cabinet.write_bytes(data[offset:offset + size])
    subprocess.run(["expand.exe", "-F:*", str(cabinet), str(extracted)], check=True)
    verify_zip(extracted / "payload.zip", files)
    if (extracted / "setup.cmd").read_bytes() != windows_batch(SETUP):
        raise ValueError("Installer contains an unexpected launcher")


def build(root, output):
    files = package_files(root)
    readme = (
        "Garasu для Windows\r\n\r\n"
        "Распакуй весь архив и запусти Install.bat.\r\n"
        "Для установки нужен интернет.\r\n"
    ).encode("utf-8-sig")
    package = {f"Garasu/files/{name}": data for name, data in files.items()}
    package["Garasu/Install.bat"] = windows_batch(LAUNCHER)
    package["Garasu/README.txt"] = readme
    with TemporaryDirectory(prefix="garasu-build-") as temp:
        work = Path(temp)
        exe = work / "Garasu-Setup.exe"
        archive = work / "Garasu.zip"
        write_zip(work / "payload.zip", files)
        (work / "setup.cmd").write_bytes(windows_batch(SETUP))
        sed = work / "setup.sed"
        sed.write_text(SED.format(target=exe, work=work), encoding="ascii")
        subprocess.run(["iexpress.exe", "/N", "/Q", str(sed)], check=True)
        print(set_icon(str(exe), str(work / "garasu.ico")))
        verify_installer(exe, work, files)
        write_zip(archive, package)
        verify_zip(archive, package)
        output.mkdir(parents=True, exist_ok=True)
        for artifact in (exe, archive):
            shutil.copyfile(artifact, output / artifact.name)
    print(f"Verified Garasu-Setup.exe and Garasu.zip ({len(files)} package files)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    build(args.root.resolve(), args.output.resolve())

