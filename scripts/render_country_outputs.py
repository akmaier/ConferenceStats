#!/usr/bin/env python3

import argparse
import csv
import os
import tempfile
from pathlib import Path

os.environ.setdefault("XDG_CACHE_HOME", tempfile.mkdtemp(prefix="fontconfig-"))
os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="matplotlib-"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def render_table_png(title: str, headers, rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig_height = max(2.5, 0.45 * (len(rows) + 2))
    fig_width = max(10, 1.6 * len(headers))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.35)
    for (row_idx, col_idx), cell in table.get_celld().items():
        if row_idx == 0:
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#D9E8F5")
        elif row_idx % 2 == 0:
            cell.set_facecolor("#F7F9FC")
    ax.set_title(title, fontsize=12, weight="bold", pad=16)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def render_overview_graph(title: str, rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    years = [key for key in rows[0].keys() if key != "conference"] if rows else []
    fig, ax = plt.subplots(figsize=(12, 7))
    for row in rows:
        y_values = []
        for year in years:
            value = row.get(year, "")
            y_values.append(float(value) if value else float("nan"))
        ax.plot(years, y_values, marker="o", linewidth=2, label=row["conference"])
    ax.set_title(title)
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of Papers (%)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def render_stats_graph(title: str, rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conferences = sorted({row["conference"] for row in rows}, key=str.casefold)
    fig, ax = plt.subplots(figsize=(12, 7))
    for conference in conferences:
        conference_rows = sorted(
            [row for row in rows if row["conference"] == conference], key=lambda row: int(row["year"])
        )
        ax.plot(
            [row["year"] for row in conference_rows],
            [float(row["share_percent_all_papers"]) for row in conference_rows],
            marker="o",
            linewidth=2,
            label=f"{conference} (all)",
        )
        ax.plot(
            [row["year"] for row in conference_rows],
            [float(row["share_percent_known_country_papers"]) for row in conference_rows],
            marker="x",
            linestyle="--",
            linewidth=1.5,
            label=f"{conference} (known)",
        )
    ax.set_title(title)
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of Papers (%)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def render_stats_table(rows, country: str, output_path: Path):
    headers = [
        "Conference",
        "Year",
        "Total",
        "Known Country",
        f"Papers With {country}",
        "Unknown-Only",
        "% All",
        "% Known Only",
    ]
    cells = [
        [
            row["conference"],
            row["year"],
            row["total_papers"],
            row["papers_with_known_country"],
            row["papers_with_country"],
            row["papers_with_unknown_only"],
            row["share_percent_all_papers"],
            row["share_percent_known_country_papers"],
        ]
        for row in rows
    ]
    render_table_png(f"Country Statistics: {country}", headers, cells, output_path)


def render_overview_table(rows, title: str, output_path: Path):
    headers = list(rows[0].keys()) if rows else ["conference"]
    cells = [[row.get(header, "") for header in headers] for row in rows]
    render_table_png(title, headers, cells, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Render PNG table and graph outputs from country statistics CSV files."
    )
    parser.add_argument("--country", required=True, help="Country name for titles.")
    parser.add_argument("--stats-csv", required=True, help="country_stats.csv path.")
    parser.add_argument("--stats-table-png", required=True, help="Output PNG for stats table.")
    parser.add_argument("--stats-graph-png", required=True, help="Output PNG for stats graph.")
    parser.add_argument(
        "--overview-all-csv",
        required=True,
        help="Overview CSV for share over all papers.",
    )
    parser.add_argument(
        "--overview-all-table-png",
        required=True,
        help="Output PNG for all-papers overview table.",
    )
    parser.add_argument(
        "--overview-all-graph-png",
        required=True,
        help="Output PNG for all-papers overview graph.",
    )
    parser.add_argument(
        "--overview-known-csv",
        required=True,
        help="Overview CSV for share over papers with any known country.",
    )
    parser.add_argument(
        "--overview-known-table-png",
        required=True,
        help="Output PNG for known-country overview table.",
    )
    parser.add_argument(
        "--overview-known-graph-png",
        required=True,
        help="Output PNG for known-country overview graph.",
    )
    args = parser.parse_args()

    stats_rows = load_csv(Path(args.stats_csv))
    overview_all_rows = load_csv(Path(args.overview_all_csv))
    overview_known_rows = load_csv(Path(args.overview_known_csv))

    render_stats_table(stats_rows, args.country, Path(args.stats_table_png))
    render_stats_graph(
        f"Country Share by Conference: {args.country} (All vs Known-Country Denominators)",
        stats_rows,
        Path(args.stats_graph_png),
    )
    render_overview_table(
        overview_all_rows,
        f"Overview Table: {args.country} (All Papers)",
        Path(args.overview_all_table_png),
    )
    render_overview_graph(
        f"Overview Graph: {args.country} (All Papers)",
        overview_all_rows,
        Path(args.overview_all_graph_png),
    )
    render_overview_table(
        overview_known_rows,
        f"Overview Table: {args.country} (Known-Country Papers Only)",
        Path(args.overview_known_table_png),
    )
    render_overview_graph(
        f"Overview Graph: {args.country} (Known-Country Papers Only)",
        overview_known_rows,
        Path(args.overview_known_graph_png),
    )


if __name__ == "__main__":
    main()
