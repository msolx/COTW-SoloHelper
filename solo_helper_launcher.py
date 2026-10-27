"""COTW 单人助手独立启动入口。"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from solo_helper.main import main

if __name__ == '__main__':
    raise SystemExit(main())
