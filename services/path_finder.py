"""自动定位 COTW 游戏安装目录与存档目录；不硬编码个人用户名与 Steam 路径。"""
import os
import re
from pathlib import Path


def detect_steam_cotw_dir() -> Path:
    """自动通过运行中进程、Steam 注册表/库清单及常见目录探测 theHunterCotW 真实安装路径。"""
    # 0. 优先检测规范持久化位置的自定义游戏路径（无论以何种工作目录启动均优先命中）
    try:
        import sys, json
        # 规范配置位置（Canonical persistent locations）具有最高优先级
        candidates = []
        if getattr(sys, 'frozen', False):
            exe_parent = Path(sys.executable).resolve().parent
            candidates.extend([
                exe_parent / "solo_helper" / "settings.json",
                exe_parent / "settings.json",
            ])
        else:
            proj_root = Path(__file__).resolve().parent.parent
            candidates.extend([
                proj_root / "solo_helper" / "settings.json",
                proj_root / "settings.json",
            ])

        appdata = Path.home() / 'AppData' / 'Local' / 'COTW_Toolkit'
        candidates.extend([
            appdata / 'solo_helper' / 'settings.json',
            appdata / 'settings.json',
        ])

        # 兼容旧版本或当前工作目录（CWD / Legacy locations）排在规范位置之后
        candidates.extend([
            Path("solo_helper") / "settings.json",
            Path("settings.json"),
        ])

        seen = set()
        for s_path in candidates:
            try:
                resolved_s = s_path.resolve()
            except Exception:
                continue
            if resolved_s in seen:
                continue
            seen.add(resolved_s)

            try:
                if resolved_s.is_file():
                    cfg = json.loads(resolved_s.read_text(encoding="utf-8"))
                    custom = cfg.get("game_dir")
                    if custom:
                        custom_path = Path(custom).resolve()
                        if (custom_path / "theHunterCotW_F.exe").is_file():
                            return custom_path
            except Exception:
                # 单个候选文件解析失败（损坏 JSON），继续检查下一个候选，不中断流程
                continue
    except Exception:
        pass

    # 1. 检测当前是否正在运行游戏，若是则直接返回其真实所在目录
    try:
        import ctypes
        from memory.process_reader import ProcessReader, PROCESSENTRY32W, MODULEENTRY32W
        mem = ProcessReader()
        snap = mem._snapshot(2)
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            found = mem._enumeration_call(mem.api.Process32FirstW, snap, entry, 'p_first')
            while found:
                if entry.szExeFile.casefold() == "thehuntercotw_f.exe":
                    snap_m = mem._snapshot(0x18, entry.th32ProcessID)
                    try:
                        m = MODULEENTRY32W()
                        m.dwSize = ctypes.sizeof(m)
                        f_m = mem._enumeration_call(mem.api.Module32FirstW, snap_m, m, 'm_first')
                        while f_m:
                            if m.szModule.casefold() == "thehuntercotw_f.exe":
                                p = Path(m.szExePath).resolve().parent
                                if (p / "theHunterCotW_F.exe").exists():
                                    return p
                            f_m = mem._enumeration_call(mem.api.Module32NextW, snap_m, m, 'm_next')
                    finally:
                        mem.api.CloseHandle(snap_m)
                found = mem._enumeration_call(mem.api.Process32NextW, snap, entry, 'p_next')
        finally:
            mem.api.CloseHandle(snap)
    except Exception:
        pass

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

    # 3. 常见盘符与Epic/通用路径后备遍历
    for drive in ("C", "D", "E", "F", "G", "H"):
        for prefix in (
            "Steam/steamapps/common/theHunterCotW",
            "SteamLibrary/steamapps/common/theHunterCotW",
            "Program Files (x86)/Steam/steamapps/common/theHunterCotW",
            "Games/Steam/steamapps/common/theHunterCotW",
            "Program Files/Epic Games/theHunterCallOfTheWild",
            "Epic Games/theHunterCallOfTheWild",
            "Games/theHunterCotW",
            "Games/theHunter Call of the Wild",
        ):
            cand = Path(f"{drive}:/{prefix}")
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
