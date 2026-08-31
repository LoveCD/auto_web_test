# -*- coding: utf-8 -*-
"""便捷启动器：在真实 INTL 设备上运行 navigation 套件（规避全角括号路径的 shell 编码问题）。"""
import glob
import os
import subprocess
import sys

# 通过 glob 定位项目根（规避全角括号在 shell 中的编码问题）
hits = glob.glob(r"C:\Users\ipwan\Downloads\auto_web_test_repo*\auto_web_test_repo\qcoder-web-autotest-agent")
if not hits:
    print("ERROR: project dir not found", file=sys.stderr)
    sys.exit(2)
root = hits[0]
print("project root:", root)

args = [sys.executable, os.path.join(root, "runner", "run_suite.py"),
        "--operator", "intl", "--env", "real", "--suite", "navigation"]
print("running:", " ".join(args))
sys.exit(subprocess.call(args, cwd=root))
