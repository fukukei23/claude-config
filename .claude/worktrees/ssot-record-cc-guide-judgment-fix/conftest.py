"""pytest がリポジトリルートを import path に含めるための設定"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
