"""Validate trade_series_config.yml against ref.* dictionaries and generate docs/gus_metadata_catalog.md."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from src.core.db import get_pg_connection
from src.core.settings import DOCS_DIR, get_settings, load_trade_config


def generate_metadata_catalog() -> None:
    settings = get_settings()
    config = load_trade_config()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    errors: list[str] = []

    with get_pg_connection(settings) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id_zmienna, nazwa_zmienna, obszar_tematyczny FROM ref.dim_variable;")
            var_map = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

            cur.execute(
                """
                SELECT id_okres, symbol, nazwa_typ, month_num, is_monthly, is_cumulative, opis
                FROM ref.dim_period
                WHERE is_monthly = true OR is_cumulative = true
                ORDER BY is_monthly DESC, month_num, id_okres;
                """
            )
            period_rows = cur.fetchall()

            cur.execute("SELECT id_przekroj, id_pozycja, nazwa_wymiar, nazwa_pozycja FROM ref.dim_position;")
            pos_map = {(r[0], r[1]): (r[2], r[3]) for r in cur.fetchall()}

            cur.execute("SELECT id_miara, nazwa_miary, oznaczenie_jedn FROM ref.dim_measure;")
            measure_map = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    lines: list[str] = [
        "# Katalog metadanych GUS DBW (wygenerowany automatycznie)",
        "",
        f"> **Ostatnia weryfikacja względem API DBW GUS:** `{now_str}`  ",
        f"> **Źródłowy adres bazowy:** `{settings.gus_dbw_base_url}`  ",
        "> **Skrypt generujący:** `python -m src.pipelines.discover_metadata` (na podstawie tabel `ref.*` w Supabase PostgreSQL 16).",
        "",
        "Ten dokument stanowi audytowalny dowód pochodzenia każdego identyfikatora użytego w `config/trade_series_config.yml`.",
        "",
        "---",
        "",
        "## 1. Rozwiązane okresy (`ref.dim_period` ← `/dictionaries/periods-dictionary`)",
        "",
        "| `id_okres` | Symbol | Typ okresu | Miesiąc (`month_num`) | Tryb | Oficjalny opis GUS |",
        "|---:|---|---|---:|---|---|",
    ]

    for id_okres, symbol, nazwa_typ, month_num, is_monthly, is_cumulative, opis in period_rows:
        mode = "monthly" if is_monthly else ("cumulative" if is_cumulative else "other")
        lines.append(
            f"| `{id_okres}` | `{symbol or ''}` | {nazwa_typ or ''} | {month_num or ''} | `{mode}` | {opis or ''} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Zweryfikowane zbiory, pozycje i miary (`config/trade_series_config.yml`)",
            "",
        ]
    )

    for ds in config["dbw_datasets"]:
        code = ds["code"]
        var_id = int(ds["id_zmienna"])
        sec_id = int(ds["id_przekroj"])
        mode = ds["period_mode"]

        if var_id not in var_map:
            errors.append(f"Missing id_zmienna={var_id} ({code}) in ref.dim_variable")
            var_name, area_name = "MISSING", "MISSING"
        else:
            var_name, area_name = var_map[var_id]

        lines.append(f"### `{code}` — {var_name}")
        lines.append(
            f"- **Obszar GUS:** {area_name} · **`id_zmienna`:** `{var_id}` · **`id_przekroj`:** `{sec_id}` · **Tryb okresów:** `{mode}`"
        )
        lines.append(
            f"- **Endpoint pozycji:** `{settings.gus_dbw_base_url}/variable/variable-section-position?id-przekroj={sec_id}&lang=pl`"
        )
        lines.append("")
        lines.append("| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |")
        lines.append("|---|---:|---|---|")

        for dim_group, pos_dict in (ds.get("positions") or {}).items():
            for pos_id, biz_code in pos_dict.items():
                key = (sec_id, int(pos_id))
                if key not in pos_map:
                    errors.append(f"Missing position (sec={sec_id}, pos={pos_id}, {biz_code}) in ref.dim_position")
                    official = "MISSING"
                else:
                    dim_name, pos_name = pos_map[key]
                    official = f"{dim_name}: {pos_name}"
                lines.append(f"| Pozycja (`{dim_group}`) | `{pos_id}` | `{biz_code}` | {official} |")

        for m_id, m_code in (ds.get("measures") or {}).items():
            m_int = int(m_id)
            if m_int not in measure_map:
                errors.append(f"Missing measure id={m_int} ({m_code}) in ref.dim_measure")
                official_m = "MISSING"
            else:
                m_name, m_unit = measure_map[m_int]
                official_m = f"{m_name} [{m_unit}]"
            lines.append(f"| Miara | `{m_int}` | `{m_code}` | {official_m} |")

        lines.append("")

    catalog_path = DOCS_DIR / "gus_metadata_catalog.md"
    catalog_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated metadata catalog: {catalog_path}")

    if errors:
        print("VALIDATION ERRORS FOUND:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print("OK: All configured GUS DBW variable, position, and measure IDs verified against live dictionaries.")


if __name__ == "__main__":
    try:
        generate_metadata_catalog()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

