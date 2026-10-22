#!/bin/zsh
cd -- "${0:A:h}" || exit 1
# Terminal may put an older Conda Python ahead of a supported installation.
# Probe interpreters without changing the user's shell or Conda configuration.
typeset -a candidates
candidates=(python3)
for directory in "${path[@]}"; do
  candidates+=("$directory/python3")
done
candidates+=(python3.12 python3.13 python3.14 python3.11 python3.10)
for version in 3.12 3.13 3.14 3.11 3.10; do
  candidates+=("/Library/Frameworks/Python.framework/Versions/$version/bin/python3")
done
candidates+=(/usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3)

selected_python=""
for candidate in "${candidates[@]}"; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else 1)' >/dev/null 2>&1; then
    selected_python="$candidate"
    break
  fi
done
if [[ -z "$selected_python" ]]; then
  echo "No supported Python was found. Install Python 3.10–3.14 from python.org, then start again."
  read -r "reply?Press Enter to close."
  exit 1
fi
"$selected_python" --version
"$selected_python" launcher.py --desktop "$@"
result=$?
if [ "$result" -ne 0 ]; then
  read -r "reply?Press Enter to close."
fi
exit "$result"
