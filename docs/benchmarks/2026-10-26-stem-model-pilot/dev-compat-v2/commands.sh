# HOLD root review: no generation command in this file has been executed.
# CPU-only regression, compilation and frozen-fixture verification:
'/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/.venv/bin/python' -m unittest discover -s '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-v2' -p test_compat_cpu.py -v
'/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/.venv/bin/python' -m py_compile '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-v2/diagnostic.py' '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-v2/native_probe_helpers.py' '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-v2/test_compat_cpu.py'
'/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/.venv/bin/python' '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-v2/diagnostic.py'
# Only after review and a subsequent explicit ROOT_GO; exclusive GPU ownership required.
/usr/bin/caffeinate -i '/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/.venv/bin/python' '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-v2/diagnostic.py' --execute --root-go ROOT_GO --output '/Volumes/External SSD TB4/LocalAI/stem-tutor-training/native-development-compat-results-v2'
