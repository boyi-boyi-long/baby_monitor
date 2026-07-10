"""
校準分析工具（階段4用）— 讀取 cry_scores.csv / motion_scores.csv，
統計分數分布，給門檻（CRY_SCORE_THRESHOLD 等）一個有資料依據的建議值。

用法：
  1. config.py 設 LOG_ONLY = True，讓 audio_monitor.py 正常生活幾天收集資料
  2. 跑：python analyze_calibration.py
  3. 看輸出的「建議門檻」，回頭改 config.py 的門檻值，再把 LOG_ONLY 改回 False

結果同時印在終端機、也存成 calibration_report.txt（UTF-8），
終端機字碼頁顯示亂碼的話可以改用記事本開那個檔案看。
"""
import csv
import os
import sys

import numpy as np

import config

if sys.platform == "win32":
    # Windows 主控台預設字碼頁常常不是 UTF-8，中文會變亂碼，這裡強制切成 UTF-8。
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    sys.stdout.reconfigure(encoding="utf-8")

REPORT_FILE = "calibration_report.txt"
_report_lines = []


def out(line: str = ""):
    print(line)
    _report_lines.append(line)


def out_percentiles(name: str, values: np.ndarray):
    if len(values) == 0:
        out(f"  {name}：沒有資料")
        return
    out(f"  {name}：{len(values)} 筆")
    out(
        f"    最小 {values.min():.3f}／中位數 {np.median(values):.3f}／"
        f"90% {np.percentile(values, 90):.3f}／95% {np.percentile(values, 95):.3f}／"
        f"99% {np.percentile(values, 99):.3f}／最大 {values.max():.3f}"
    )


def analyze_cry():
    out("=" * 50)
    out("哭聲分數分析（cry_scores.csv）")
    out("=" * 50)
    if not os.path.exists(config.LOG_CSV):
        out(f"找不到 {config.LOG_CSV}，請先讓 audio_monitor.py 跑一段時間收集資料。")
        return

    cry_scores = []
    top_classes = []
    with open(config.LOG_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                cry_scores.append(float(row["cry_score"]))
                top_classes.append(row["top_class"])
            except (KeyError, ValueError):
                continue

    if not cry_scores:
        out("資料是空的。")
        return

    cry_scores = np.array(cry_scores)
    is_cry_top = np.array([c in config.CRY_CLASSES for c in top_classes])

    out(f"總筆數：{len(cry_scores)}")
    out()
    out("【全部資料】")
    out_percentiles("cry_score", cry_scores)

    noise = cry_scores[~is_cry_top]
    cry_like = cry_scores[is_cry_top]

    out()
    out(f"【背景/非哭聲時刻】（YAMNet 最強類別不是哭聲相關，共 {len(noise)} 筆）")
    out_percentiles("cry_score", noise)

    out()
    out(f"【疑似哭聲時刻】（YAMNet 最強類別是哭聲相關，共 {len(cry_like)} 筆）")
    out_percentiles("cry_score", cry_like)

    out()
    out("【建議門檻】")
    if len(noise) == 0 or len(cry_like) == 0:
        out("  兩組其中一組沒有資料（可能收集期間都沒有真的哭，或一直都在哭），")
        out("  樣本不足以給建議，請延長收集天數，確保有涵蓋到真實哭聲片段。")
    else:
        noise_p95 = np.percentile(noise, 95)
        cry_p10 = np.percentile(cry_like, 10)
        out(f"  背景噪音 95百分位：{noise_p95:.3f}（代表 95% 的日常噪音分數都低於這個值）")
        out(f"  疑似哭聲 10百分位：{cry_p10:.3f}（代表 90% 的疑似哭聲時刻分數都高於這個值）")
        if cry_p10 > noise_p95:
            suggested = (noise_p95 + cry_p10) / 2
            out(f"  → 兩者有明顯區隔，建議 CRY_SCORE_THRESHOLD 設在 {suggested:.2f} 附近")
        else:
            out("  → 兩者分數有重疊，不建議直接套用中間值，可能是樣本不夠、或環境噪音")
            out("    跟哭聲聲學特徵接近，建議延長收集天數，或人工抽查重疊時段對應的錄音。")
    out(f"  目前設定值：CRY_SCORE_THRESHOLD = {config.CRY_SCORE_THRESHOLD}")


def analyze_motion():
    out()
    out("=" * 50)
    out("活動量分析（motion_scores.csv）")
    out("=" * 50)
    if not os.path.exists(config.MOTION_LOG_CSV):
        out(f"找不到 {config.MOTION_LOG_CSV}，請先讓 audio_monitor.py 跑一段時間收集資料。")
        return

    ratios = []
    actives = []
    with open(config.MOTION_LOG_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ratios.append(float(row["motion_ratio"]))
                actives.append(int(row["active"]))
            except (KeyError, ValueError):
                continue

    if not ratios:
        out("資料是空的（ESP32-CAM 可能還沒連線過，video_monitor 沒收到畫面就不會寫入）。")
        return

    ratios = np.array(ratios)
    actives = np.array(actives, dtype=bool)

    out(f"總筆數：{len(ratios)}")
    out()
    out("【全部資料】")
    out_percentiles("motion_ratio", ratios)
    out(
        f"  「有在動」比例：{actives.mean():.2%}"
        f"（單一秒用 MOTION_PIXEL_RATIO_THRESHOLD={config.MOTION_PIXEL_RATIO_THRESHOLD} 判斷）"
    )

    out()
    out(f"  目前設定值：MOTION_PIXEL_RATIO_THRESHOLD = {config.MOTION_PIXEL_RATIO_THRESHOLD}")
    out(f"             MOTION_ALERT_RATIO = {config.MOTION_ALERT_RATIO}")
    out(f"             MOTION_STILL_RATIO = {config.MOTION_STILL_RATIO}")
    out()
    out("提醒：活動量沒有像哭聲那樣「YAMNet 最強類別」可以自動分組真假，")
    out("建議搭配你自己記得的『寶寶醒著活動』跟『睡著』的大概時段，")
    out("回頭對照那幾段時間的 motion_ratio 數值，人工抓分界點。")


def main():
    analyze_cry()
    analyze_motion()
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(_report_lines) + "\n")
    print(f"\n（報告已存成 {REPORT_FILE}，終端機顯示亂碼可以改用記事本開這個檔案）")


if __name__ == "__main__":
    main()
