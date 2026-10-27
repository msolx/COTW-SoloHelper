"""自动定位 COTW 游戏安装目录与存档目录；不硬编码个人用户名与 Steam 路径。"""
import os
import re
from pathlib import Path


def detect_steam_cotw_dir() -> Path:
    """自动通过 Steam 注册表与库清单探测 theHunterCotW 真实安装路径。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            raw_steam = winreg.QueryValueEx(key, "SteamPath")[0]
            steam_path = Path(raw_steam.replace("/", "\\"))
            # 1. 默认库路径
            default_candidate = steam_path / "steamapps" / "common" / "theHunterCotW"
            if (default_candidate / "theHunterCotW_F.exe").exists():
                return default_candidate
            # 2. libraryfolders.vdf 多盘库目录
            vdf = steam_path / "steamapps" / "libraryfolders.vdf"
            if vdf.exists():
                text = vdf.read_text(encoding="utf-8", errors="ignore")
                for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                    lib_candidate = Path(match.group(1).replace("\\\\", "\\")) / "steamapps" / "common" / "theHunterCotW"
                    if (lib_candidate / "theHunterCotW_F.exe").exists():
                        return lib_candidate
    except Exception:
        pass

    # 3. 常见盘符后备遍历
    for drive in ("C", "D", "E", "F", "G", "H"):
        for prefix in ("Steam", "SteamLibrary", "Program Files (x86)/Steam", "Games/Steam"):
            cand = Path(f"{drive}:/{prefix}/steamapps/common/theHunterCotW")
            if (cand / "theHunterCotW_F.exe").exists():
                return cand

    # 4. 默认后备路径
    return Path(r"C:\Program Files (x86)\Steam\steamapps\common\theHunterCotW")


def get_documents_dir() -> Path:
    """获取 Windows 系统的真实文档目录（自动支持 OneDrive 重定向及自定义盘符）。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            val, _ = winreg.QueryValueEx(key, "Personal")
            expanded = os.path.expandvars(str(val))
            p = Path(expanded)
            if p.exists():
                return p
    except Exception:
        pass
    return Path.home() / "Documents"


def detect_cotw_save_dir() -> Path:
    """自动探测当前 Windows 用户的 COTW 存档路径（Documents/Avalanche Studios/COTW/Saves/<SteamID>/）。"""
    docs_save = get_documents_dir() / "Avalanche Studios" / "COTW" / "Saves"
    if docs_save.exists():
        candidates = [p for p in docs_save.iterdir() if p.is_dir() and p.name.isdigit()]
        if candidates:
            # 优先选择最近修改过的 Steam 账号存档目录
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
    return docs_save


def detect_crash_dir() -> Path:
    """自动探测 CrashRpt 目录（如有）。"""
    return Path.home() / "AppData" / "Local" / "CrashRpt" / "UnsentCrashReports" / "theHunterCotW_F_1.0.0"
