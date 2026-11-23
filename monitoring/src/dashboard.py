"""Paso 4 · Dashboard operativo (una imagen) a partir de todas las ventanas guardadas en outputs/runs/.

Cada panel responde a una DECISIÓN (ver subtítulo de cada gráfica). Cada punto es una ventana de
500 solicitudes; su marcador indica el estado frente al umbral (círculo = ok, triángulo = warning,
rombo = critical), así el estado nunca depende solo del color.

Uso (desde la raíz del repo):
  python monitoring/src/dashboard.py
  python monitoring/src/dashboard.py --last 8          # solo las últimas 8 ventanas
Genera: monitoring/outputs/dashboard.png
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

# Paleta (valores validados del método de visualización): una sola serie en azul, estado con colores reservados
SUPERFICIE, TINTA, TINTA_2, TINTA_3, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#74736e", "#e4e3df"
SERIE = "#2a78d6"
ESTADO = {"ok": ("#0ca30c", "o"), "warning": ("#fab219", "^"), "critical": ("#d03b3b", "D")}


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config" / "monitoring_config.json"))
    ap.add_argument("--reference", default=str(ROOT / "data" / "reference_stats.json"))
    ap.add_argument("--runs", default=str(OUT / "runs"))
    ap.add_argument("--out", default=str(OUT / "dashboard.png"))
    ap.add_argument("--last", type=int, default=None, help="Mostrar solo las últimas N ventanas")
    return ap.parse_args()


def severidad(valor, regla):
    w, c = regla["warning"], regla["critical"]
    if regla.get("direction", "max") == "max":
        return "critical" if valor >= c else "warning" if valor >= w else "ok"
    return "critical" if valor <= c else "warning" if valor <= w else "ok"


def estilo_ejes(ax, titulo, decision):
    ax.set_facecolor(SUPERFICIE)
    ax.set_title(titulo, loc="left", fontsize=11, fontweight="bold", color=TINTA, pad=22)
    ax.text(0, 1.04, decision, transform=ax.transAxes, fontsize=8.5, color=TINTA_2, va="bottom")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(REJILLA)
    ax.tick_params(colors=TINTA_2, labelsize=8.5, length=0)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)


def serie(ax, etiquetas, valores, regla, fmt="{:.0f}"):
    """Línea de 2 px con marcadores de estado y umbrales como líneas discontinuas rotuladas."""
    x = list(range(len(valores)))
    ax.plot(x, valores, color=SERIE, linewidth=2, zorder=2)
    for xi, v in zip(x, valores):
        color, marca = ESTADO[severidad(v, regla)]
        ax.scatter([xi], [v], s=62, color=color, marker=marca, edgecolor=SUPERFICIE, linewidth=1.5, zorder=3)
    for nivel, texto in ((regla["warning"], "warning"), (regla["critical"], "critical")):
        ax.axhline(nivel, color=TINTA_3, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
        ax.text(len(valores) - 0.5, nivel, f" {texto} {nivel:g}", color=TINTA_2, fontsize=8, va="bottom", ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas, rotation=35, ha="right")
    ax.set_xlim(-0.4, len(valores) - 0.4)
    tope = max(max(valores), regla["critical"]) * 1.15
    ax.set_ylim(0, tope)
    # etiqueta directa solo en el último punto
    ax.annotate(fmt.format(valores[-1]), (x[-1], valores[-1]), textcoords="offset points", xytext=(0, 9),
                ha="center", fontsize=9, color=TINTA, fontweight="bold")


def main():
    a = parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    ref = json.loads(Path(a.reference).read_text(encoding="utf-8"))
    th = cfg["thresholds"]
    archivos = sorted(Path(a.runs).glob("*.json"), key=lambda p: p.name.rsplit("_", 2)[-2:])
    corridas = [json.loads(p.read_text(encoding="utf-8")) for p in archivos]
    corridas.sort(key=lambda c: c["generated_at"])
    if a.last:
        corridas = corridas[-a.last:]
    if not corridas:
        raise SystemExit("No hay corridas en outputs/runs/. Corre monitor.py al menos una vez.")

    et = [c["window_label"] for c in corridas]
    m = lambda k: [c["metrics"].get(k, 0.0) for c in corridas]  # noqa: E731
    ultima = corridas[-1]

    fig = plt.figure(figsize=(17, 11.5), facecolor=SUPERFICIE)
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.9], hspace=0.95, wspace=0.28,
                          left=0.05, right=0.98, top=0.86, bottom=0.04)
    fig.text(0.05, 0.955, "Sierra Móvil · API de predicción de churn · Panel operativo", fontsize=16,
             fontweight="bold", color=TINTA, va="center")
    fig.text(0.05, 0.925, f"{len(corridas)} ventanas de {cfg['service']['window_size']} solicitudes · "
             f"SLO de éxito ≥ {cfg['service']['success_rate_target']:.0%} (error budget "
             f"{1 - cfg['service']['success_rate_target']:.0%}) · última ventana: '{ultima['window_label']}' → "
             f"{ultima['status'].upper()}", fontsize=10.5, color=TINTA_2, va="center")
    # leyenda de estado (marcador + texto)
    x0 = 0.62
    for i, (nombre, (color, marca)) in enumerate(ESTADO.items()):
        fig.add_artist(plt.Line2D([x0 + i * 0.12], [0.955], marker=marca, color=color, markersize=9,
                                  markeredgecolor=SUPERFICIE, linestyle="", transform=fig.transFigure))
        fig.text(x0 + i * 0.12 + 0.008, 0.955, nombre, fontsize=10, color=TINTA_2, va="center")

    # 1 · latencia
    ax = fig.add_subplot(gs[0, 0])
    estilo_ejes(ax, "Latencia p95 de /predict (ms)", "Decisión: escalar, reiniciar o hacer rollback del servicio")
    serie(ax, et, m("latency_p95_ms"), th["latency_p95_ms"])

    # 2 · error budget
    ax = fig.add_subplot(gs[0, 1])
    estilo_ejes(ax, "Error budget: burn rate", "Decisión: reiniciar o hacer rollback (1.0 = presupuesto de 5% agotado)")
    serie(ax, et, m("error_budget_burn_rate"), th["error_budget_burn_rate"], fmt="{:.2f}")

    # 3 · drift
    ax = fig.add_subplot(gs[0, 2])
    estilo_ejes(ax, "Data drift: PSI máximo entre variables", "Decisión: cuarentena del lote o evaluar reentrenamiento")
    serie(ax, et, m("drift_psi"), th["drift_psi"], fmt="{:.2f}")

    # 4 · % a contactar
    ax = fig.add_subplot(gs[1, 0])
    estilo_ejes(ax, "% de clientes marcados «contactar»", "Decisión: revisar umbral y costo de campaña ($46 por contacto)")
    base = ref["contact_rate"] * 100
    vals = [v * 100 for v in m("contact_rate")]
    x = list(range(len(vals)))
    r = th["contact_rate_shift_pts"]
    ax.axhspan(base - r["warning"], base + r["warning"], color=REJILLA, alpha=0.7, zorder=0)
    ax.axhline(base, color=TINTA_3, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(len(vals) - 0.5, base - r["warning"], f" referencia {base:.1f}% ± {r['warning']:g} pts", color=TINTA_2,
            fontsize=8, va="top", ha="right")
    ax.plot(x, vals, color=SERIE, linewidth=2, zorder=2)
    for xi, v in zip(x, vals):
        color, marca = ESTADO[severidad(abs(v - base), r)]
        ax.scatter([xi], [v], s=62, color=color, marker=marca, edgecolor=SUPERFICIE, linewidth=1.5, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(et, rotation=35, ha="right")
    ax.set_xlim(-0.4, len(vals) - 0.4)
    ax.set_ylim(0, 100)
    ax.annotate(f"{vals[-1]:.0f}%", (x[-1], vals[-1]), textcoords="offset points", xytext=(0, 9), ha="center",
                fontsize=9, color=TINTA, fontweight="bold")

    # 5 · PSI por variable (última ventana)
    ax = fig.add_subplot(gs[1, 1])
    estilo_ejes(ax, f"PSI por variable · ventana '{ultima['window_label']}'", "Decisión: saber qué variable causa el drift")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=REJILLA, linewidth=0.8)
    pv = ultima.get("drift_by_feature", {})
    nombres = sorted(pv, key=pv.get)
    ax.barh(nombres, [pv[k] for k in nombres], color=SERIE, height=0.55, zorder=2)
    for lvl in (th["drift_psi"]["warning"], th["drift_psi"]["critical"]):
        ax.axvline(lvl, color=TINTA_3, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    for i, k in enumerate(nombres):
        ax.text(pv[k] + 0.01, i, f"{pv[k]:.2f}", va="center", fontsize=9, color=TINTA)
    ax.set_xlim(0, max(max(pv.values(), default=0), th["drift_psi"]["critical"]) * 1.2)
    ax.set_ylim(-0.95, len(nombres) - 0.4)
    ax.text(th["drift_psi"]["warning"], -0.9, " warning 0.10", fontsize=8, color=TINTA_2, va="bottom")
    ax.text(th["drift_psi"]["critical"], -0.9, " critical 0.25", fontsize=8, color=TINTA_2, va="bottom")

    # 6 · p95 por etapa (última ventana)
    ax = fig.add_subplot(gs[1, 2])
    estilo_ejes(ax, f"Traza: p95 por etapa · ventana '{ultima['window_label']}'",
                "Decisión: ubicar qué etapa del servicio causa la lentitud")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=REJILLA, linewidth=0.8)
    et_p95 = {k: v for k, v in ultima.get("stage_p95_ms", {}).items()}
    orden = [k for k in ("validation", "inference", "decision", "total") if k in et_p95]
    ax.barh(orden[::-1], [et_p95[k] for k in orden[::-1]], color=SERIE, height=0.55, zorder=2)
    for i, k in enumerate(orden[::-1]):
        ax.text(et_p95[k], i, f" {et_p95[k]:.1f} ms", va="center", fontsize=9, color=TINTA)
    ax.set_xlim(0, max(et_p95.values(), default=1) * 1.25)

    # 7 · tabla de ventanas
    ax = fig.add_subplot(gs[2, :])
    ax.set_facecolor(SUPERFICIE)
    ax.axis("off")
    ax.text(0, 1.08, "Ventanas, alertas activas y acción recomendada", fontsize=11, fontweight="bold",
            color=TINTA, transform=ax.transAxes, va="bottom")
    ax.text(0.0, 1.0, "Decisión: priorizar qué atender primero (P1 antes que P2 y P3)", fontsize=8.5,
            color=TINTA_2, transform=ax.transAxes, va="top")
    cols = [("Ventana", 0.0), ("Estado", 0.14), ("Alertas activas (prioridad · métrica)", 0.24),
            ("Suprimidas", 0.62), ("Acción recomendada", 0.72)]
    y = 0.74
    for texto, xc in cols:
        ax.text(xc, y, texto, fontsize=8.5, color=TINTA_2, fontweight="bold", transform=ax.transAxes)
    filas = corridas[-8:][::-1]
    paso = 0.80 / max(len(filas), 1)
    for i, c in enumerate(filas):
        yy = y - 0.10 - i * 0.085
        color, marca = ESTADO[c["status"]]
        ax.scatter([0.14], [yy + 0.012], s=48, color=color, marker=marca, transform=ax.transAxes, clip_on=False)
        ax.text(0.0, yy, c["window_label"][:20], fontsize=9, color=TINTA, transform=ax.transAxes)
        ax.text(0.155, yy, c["status"], fontsize=9, color=TINTA, transform=ax.transAxes)
        act = ", ".join(f"{x['priority']} {x['metric']}" for x in c.get("alerts", [])) or "—"
        ax.text(0.24, yy, act[:62], fontsize=9, color=TINTA, transform=ax.transAxes)
        ax.text(0.62, yy, str(len(c.get("suppressed_alerts", []))), fontsize=9, color=TINTA, transform=ax.transAxes)
        ax.text(0.72, yy, c["recommended_action"][:48], fontsize=9, color=TINTA, transform=ax.transAxes)

    fig.savefig(a.out, dpi=150, facecolor=SUPERFICIE)
    print(f"Dashboard guardado en {a.out}")


if __name__ == "__main__":
    main()
