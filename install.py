from pathlib import Path
import os
import pip
import sys
import venv
import subprocess

print("Install orwell/shooter")

script_path = Path(__file__)
script_dir = script_path.parent
os.chdir(script_dir)
venv_dir = Path(".venv")
if venv_dir.exists():
    print("{} allready exists".format(venv_dir))
else:
    print("Create virtual environment")
    venv.create(venv_dir, with_pip=True)

python_bin = venv_dir / "bin" / "python"
if not python_bin.exists():
    python_bin = venv_dir / "Scripts" / "python.exe"
    if not python_bin.exists():
        print("Could not locate python binary in virtualenv")
        sys.exit(1)
print("Install dependencies if needed")
subprocess.check_call(
        [python_bin, '-m', 'pip', 'install', '-r', 'requirements.txt'])

print("Get submodules")
subprocess.check_call(["git", "submodule", "update", "--init"])

print("Generate protobuf code")
subprocess.check_call(["git", "submodule", "update", "--init"])
command = [python_bin, script_dir / "messages" / "generate.py", script_dir.absolute()]
#print(command)
subprocess.check_call(command)
