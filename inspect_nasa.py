"""
NASA PCoE Battery Data Set — 全量清点脚本

用法:
    python scripts/inspect_nasa.py                  # 默认扫描 data/raw
    python scripts/inspect_nasa.py --dir data/raw --out reports

产出:
    reports/nasa_inventory.md   人类可读的总览报告（拿给 supervisor 看这个）
    reports/nasa_cells.csv      每颗电芯一行的汇总表
    reports/nasa_capacity.csv   每个放电循环一行的容量明细

依赖: scipy >= 1.5, numpy, pandas
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

NOMINAL_AH = 2.0  # NASA 这批 18650 的标称容量


def load_cell(path: Path):
    """读一个 .mat，返回 (cell_id, cycles_list)。

    simplify_cells=True 把 MATLAB 的嵌套 struct array 直接转成
    Python 的 dict / list，省掉手工拆 numpy.void 的痛苦。
    """
    m = loadmat(path, simplify_cells=True)
    keys = [k for k in m if not k.startswith("__")]
    if not keys:
        return None, []
    cell_id = keys[0]
    cycles = m[cell_id].get("cycle", [])
    if isinstance(cycles, dict):  # 只有一个循环时不是 list
        cycles = [cycles]
    return cell_id, list(cycles)


def cycle_date(cyc):
    """time 字段是 [year, month, day, hour, minute, second]。"""
    t = np.atleast_1d(cyc.get("time", []))
    if t.size < 3:
        return None
    return f"{int(t[0]):04d}-{int(t[1]):02d}-{int(t[2]):02d}"


def as_float(x):
    try:
        return float(np.atleast_1d(x).ravel()[0])
    except Exception:
        return None


def summarise(path: Path):
    cell_id, cycles = load_cell(path)
    if cell_id is None:
        return None, [], {}

    type_counts, temps, fields_by_type = {}, set(), {}
    dates, discharge_rows = [], []
    d_index = 0

    for i, cyc in enumerate(cycles):
        ctype = str(cyc.get("type", "unknown"))
        type_counts[ctype] = type_counts.get(ctype, 0) + 1

        temp = as_float(cyc.get("ambient_temperature"))
        if temp is not None:
            temps.add(int(temp))

        d = cyc.get("data", {})
        if isinstance(d, dict):
            fields_by_type.setdefault(ctype, set()).update(d.keys())

        dt = cycle_date(cyc)
        if dt:
            dates.append(dt)

        if ctype == "discharge" and isinstance(d, dict):
            d_index += 1
            cap = as_float(d.get("Capacity"))
            n_samples = np.atleast_1d(d.get("Time", [])).size
            discharge_rows.append(
                {
                    "cell_id": cell_id,
                    "raw_index": i,
                    "discharge_index": d_index,
                    "date": dt,
                    "ambient_C": temp,
                    "capacity_Ah": cap,
                    "n_samples": n_samples,
                }
            )

    caps = [r["capacity_Ah"] for r in discharge_rows if r["capacity_Ah"] is not None]
    cap_first = caps[0] if caps else None
    cap_last = caps[-1] if caps else None

    # SOH 相对各自初始容量，不是相对标称 —— 出厂离散性会污染跨电芯对比
    cycles_to_80 = None
    if caps:
        for r in discharge_rows:
            c = r["capacity_Ah"]
            if c is not None and c <= 0.8 * cap_first:
                cycles_to_80 = r["discharge_index"]
                break

    summary = {
        "cell_id": cell_id,
        "file": path.name,
        "n_cycles_total": len(cycles),
        "n_charge": type_counts.get("charge", 0),
        "n_discharge": type_counts.get("discharge", 0),
        "n_impedance": type_counts.get("impedance", 0),
        "ambient_C": "/".join(str(t) for t in sorted(temps)) if temps else None,
        "date_start": min(dates) if dates else None,
        "date_end": max(dates) if dates else None,
        "capacity_first_Ah": round(cap_first, 4) if cap_first else None,
        "capacity_last_Ah": round(cap_last, 4) if cap_last else None,
        "retention_pct": round(100 * cap_last / cap_first, 1) if caps else None,
        "cycles_to_80": cycles_to_80,  # None = 从未跌破 80%
        "n_samples_median": int(np.median([r["n_samples"] for r in discharge_rows]))
        if discharge_rows
        else None,
    }
    return summary, discharge_rows, fields_by_type


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/raw")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    src = Path(args.dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(src.glob("*.mat"))
    if not files:
        raise SystemExit(f"{src} 下没有 .mat 文件")

    summaries, all_discharges, all_fields = [], [], {}
    for f in files:
        s, rows, fields = summarise(f)
        if s is None:
            print(f"跳过 {f.name}（无法解析）")
            continue
        summaries.append(s)
        all_discharges.extend(rows)
        for k, v in fields.items():
            all_fields.setdefault(k, set()).update(v)
        print(f"{s['cell_id']}: {s['n_cycles_total']} 循环 "
              f"({s['n_discharge']} 放电), {s['ambient_C']}°C, "
              f"保持率 {s['retention_pct']}%")

    df = pd.DataFrame(summaries).sort_values("cell_id")
    dfc = pd.DataFrame(all_discharges)
    df.to_csv(out / "nasa_cells.csv", index=False)
    dfc.to_csv(out / "nasa_capacity.csv", index=False)

    # ---------- markdown 报告 ----------
    L = []
    L.append("# NASA PCoE Battery Data Set — 数据清点\n")
    L.append(f"来源目录 `{src}` · 共 {len(df)} 颗电芯 · "
             f"{int(df['n_cycles_total'].sum())} 个循环记录\n")
    L.append("引用: B. Saha and K. Goebel (2007), \"Battery Data Set\", "
             "NASA Prognostics Data Repository, NASA Ames Research Center, "
             "Moffett Field, CA\n")

    L.append("\n## 一、每颗电芯总览\n")
    show = df[["cell_id", "n_discharge", "n_impedance", "ambient_C",
               "date_start", "date_end", "capacity_first_Ah",
               "capacity_last_Ah", "retention_pct", "cycles_to_80"]]
    L.append(show.to_markdown(index=False))
    L.append("\n`cycles_to_80` 为空表示该电芯从未跌破初始容量的 80%。\n")

    L.append("\n## 二、按温度分组\n")
    for t, g in df.groupby("ambient_C", dropna=False):
        cells = ", ".join(g["cell_id"])
        L.append(f"- **{t} °C** ({len(g)} 颗): {cells}")

    L.append("\n\n## 三、每种循环类型记录了哪些量\n")
    for ctype in ("charge", "discharge", "impedance"):
        if ctype in all_fields:
            L.append(f"\n**{ctype}**\n")
            L.append("`" + "`, `".join(sorted(all_fields[ctype])) + "`\n")

    L.append("\n## 四、放电循环采样密度\n")
    if not dfc.empty:
        L.append(f"每个放电循环的采样点数中位数: "
                 f"{int(dfc['n_samples'].median())} 点\n")
        L.append("\n注意: 采样密度决定了能否做 ICA/DVA (dQ/dV) 分析。"
                 "点数偏少时微分曲线噪声会淹没特征峰。\n")

    L.append("\n## 五、这份数据里没有什么\n")
    L.append("- 无拆解/表征数据 (SEM, XRD, 三电极)，无法直接确认析锂或颗粒破裂\n")
    L.append("- 无电芯化学体系的官方确认 (标称 2 Ah 18650，文献多按 NCA/石墨处理)\n")
    L.append("- 阻抗测试与充放电循环交错，两者索引不对齐\n")
    L.append("- 容量曲线含再生尖峰，knee 检测前需平滑\n")

    (out / "nasa_inventory.md").write_text("\n".join(L), encoding="utf-8")

    print(f"\n完成 → {out/'nasa_inventory.md'}")
    print(f"      {out/'nasa_cells.csv'}")
    print(f"      {out/'nasa_capacity.csv'}")


if __name__ == "__main__":
    main()
