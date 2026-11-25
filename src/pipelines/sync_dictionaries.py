"""Synchronize official GUS DBW dictionaries into Supabase Bronze (S3) and Silver (ref.*)."""

from __future__ import annotations

import re
import sys
from typing import Any

from src.clients.dbw_client import DBWClient
from src.core.db import get_pg_connection
from src.core.settings import get_settings, load_trade_config
from src.core.storage_s3 import BronzeStorageClient

ROMAN_MONTHS = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
}


def parse_period_flags(item: dict[str, Any]) -> tuple[int | None, bool, bool]:
    """Derive (month_num, is_monthly, is_cumulative) from official DBW period metadata.

    Strictly filters to monthly frequency (nazwa-czestotliwosc == 'Miesiąc') so
    quarterly/annual variants sharing M01..M12 symbols (e.g. id-okres=341) are excluded.
    """
    symbol = str(item.get("symbol") or "").strip().upper()
    opis = str(item.get("opis") or "").strip()
    nazwa_typ = str(item.get("nazwa-typ") or "").strip().lower()
    nazwa_czest = str(item.get("nazwa-czestotliwosc") or "").strip().lower()

    if nazwa_czest != "miesiąc":
        return None, False, False

    m_single = re.fullmatch(r"M(\d{2})", symbol)
    if m_single and "miesi" in nazwa_typ:
        month_num = int(m_single.group(1))
        if 1 <= month_num <= 12:
            return month_num, True, False

    if "narastaj" in nazwa_typ or "narastaj" in opis.lower():
        m_cum_sym = re.search(r"M01-(\d{2})", symbol)
        if m_cum_sym:
            m_end = int(m_cum_sym.group(1))
            # Month 1 uses id_okres=247 (M01); cumulative series use M01-02..M01-12 (259..269)
            if 2 <= m_end <= 12:
                return m_end, False, True
        m_cum_rom = re.search(r"\bI\s*[-–]\s*(XII|XI|X|IX|VIII|VII|VI|V|IV|III|II)\b", opis.upper())
        if m_cum_rom:
            return ROMAN_MONTHS[m_cum_rom.group(1)], False, True

    return None, False, False


def build_business_code_maps(
    config: dict[str, Any],
) -> tuple[dict[int, tuple[str, int]], dict[int, str], dict[tuple[int, int], str]]:
    """Build business_code lookups from YAML for variables, measures, and positions."""
    var_map: dict[int, tuple[str, int]] = {}
    measure_map: dict[int, str] = {}
    pos_map: dict[tuple[int, int], str] = {}
    for ds in config.get("dbw_datasets", []):
        var_id = int(ds["id_zmienna"])
        sec_id = int(ds["id_przekroj"])
        var_map[var_id] = (str(ds["code"]), sec_id)
        for m_id, m_code in (ds.get("measures") or {}).items():
            measure_map[int(m_id)] = str(m_code)
        for _dim_group, pos_dict in (ds.get("positions") or {}).items():
            for pos_id, biz_code in pos_dict.items():
                pos_map[(sec_id, int(pos_id))] = str(biz_code)
    return var_map, measure_map, pos_map


def sync_business_codes_only() -> None:
    """Apply business_code labels from YAML onto existing ref.* rows (0 GUS API calls)."""
    settings = get_settings()
    config = load_trade_config()
    var_biz_map, measure_biz_map, pos_biz_map = build_business_code_maps(config)

    with get_pg_connection(settings) as conn:
        with conn.cursor() as cur:
            for var_id, (biz_code, sec_id) in var_biz_map.items():
                cur.execute(
                    "UPDATE ref.dim_variable SET business_code = %s, id_przekroj = %s, updated_at = now() WHERE id_zmienna = %s",
                    (biz_code, sec_id, var_id),
                )
            for m_id, m_code in measure_biz_map.items():
                cur.execute(
                    "UPDATE ref.dim_measure SET business_code = %s, updated_at = now() WHERE id_miara = %s",
                    (m_code, m_id),
                )
            for (sec_id, pos_id), p_code in pos_biz_map.items():
                cur.execute(
                    "UPDATE ref.dim_position SET business_code = %s, updated_at = now() WHERE id_przekroj = %s AND id_pozycja = %s",
                    (p_code, sec_id, pos_id),
                )
        conn.commit()
    print(
        f"OK: Applied business_code mappings to ref.* "
        f"(variables={len(var_biz_map)}, measures={len(measure_biz_map)}, positions={len(pos_biz_map)})."
    )


def sync_all_dictionaries() -> None:
    settings = get_settings()
    config = load_trade_config()
    storage = BronzeStorageClient(settings)
    var_biz_map, measure_biz_map, pos_biz_map = build_business_code_maps(config)

    target_vars = {int(ds["id_zmienna"]) for ds in config["dbw_datasets"]}
    target_sections = sorted({int(ds["id_przekroj"]) for ds in config["dbw_datasets"]})

    with DBWClient(settings) as dbw, get_pg_connection(settings) as conn:
        with conn.cursor() as cur:
            print("[1/5] Fetching DBW periods dictionary...")
            periods = dbw.get_periods_dictionary()
            storage.put_json_gz(storage.dbw_dict_key("periods"), periods)
            for item in periods:
                month_num, is_monthly, is_cumulative = parse_period_flags(item)
                cur.execute(
                    """
                    INSERT INTO ref.dim_period (
                        id_okres, symbol, opis, id_czestotliwosc, nazwa_czestotliwosc,
                        id_typ, nazwa_typ, month_num, is_monthly, is_cumulative, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (id_okres) DO UPDATE SET
                        symbol = EXCLUDED.symbol,
                        opis = EXCLUDED.opis,
                        id_czestotliwosc = EXCLUDED.id_czestotliwosc,
                        nazwa_czestotliwosc = EXCLUDED.nazwa_czestotliwosc,
                        id_typ = EXCLUDED.id_typ,
                        nazwa_typ = EXCLUDED.nazwa_typ,
                        month_num = EXCLUDED.month_num,
                        is_monthly = EXCLUDED.is_monthly,
                        is_cumulative = EXCLUDED.is_cumulative,
                        updated_at = now()
                    """,
                    (
                        int(item["id-okres"]),
                        item.get("symbol"),
                        item.get("opis"),
                        item.get("id-czestotliwosc"),
                        item.get("nazwa-czestotliwosc"),
                        item.get("id-typ"),
                        item.get("nazwa-typ"),
                        month_num,
                        is_monthly,
                        is_cumulative,
                    ),
                )
            print(f"      Upserted {len(periods)} rows into ref.dim_period")

            print("[2/5] Fetching DBW measures (way-of-presentation) dictionary...")
            measures = dbw.get_measures_dictionary()
            storage.put_json_gz(storage.dbw_dict_key("measures"), measures)
            for item in measures:
                m_id = int(item["id-sposob-prezentacji-miara"])
                cur.execute(
                    """
                    INSERT INTO ref.dim_measure (
                        id_miara, nazwa_miary, sposob_prezentacji, oznaczenie_jedn, nazwa_jedn, business_code, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (id_miara) DO UPDATE SET
                        nazwa_miary = EXCLUDED.nazwa_miary,
                        sposob_prezentacji = EXCLUDED.sposob_prezentacji,
                        oznaczenie_jedn = EXCLUDED.oznaczenie_jedn,
                        nazwa_jedn = EXCLUDED.nazwa_jedn,
                        business_code = COALESCE(EXCLUDED.business_code, ref.dim_measure.business_code),
                        updated_at = now()
                    """,
                    (
                        m_id,
                        item.get("nazwa") or "",
                        item.get("nazwa-sposob-prezentacji"),
                        item.get("oznaczenie-jednostki"),
                        item.get("nazwa-jednostki"),
                        measure_biz_map.get(m_id),
                    ),
                )
            print(f"      Upserted {len(measures)} rows into ref.dim_measure")

            print("[3/5] Fetching DBW flags dictionary...")
            flags = dbw.get_flags_dictionary()
            storage.put_json_gz(storage.dbw_dict_key("flags"), flags)
            for item in flags:
                cur.execute(
                    """
                    INSERT INTO ref.dim_flag (id_flaga, oznaczenie, opis_flagi, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (id_flaga) DO UPDATE SET
                        oznaczenie = EXCLUDED.oznaczenie,
                        opis_flagi = EXCLUDED.opis_flagi,
                        updated_at = now()
                    """,
                    (
                        int(item["id-flaga"]),
                        item.get("oznaczenie"),
                        item.get("nazwa") or "",
                    ),
                )
            print(f"      Upserted {len(flags)} rows into ref.dim_flag")

            print("[4/5] Fetching DBW variable names for configured areas (13, 46, 100)...")
            areas = dbw.get_areas()
            area_name_map = {int(a["id"]): a.get("nazwa", "") for a in areas}
            var_rows: list[dict[str, Any]] = []
            for area_id in (13, 46, 100):
                for v in dbw.get_area_variables(area_id):
                    v_id = int(v["id-zmienna"])
                    if v_id in target_vars:
                        var_rows.append(
                            {
                                "id_zmienna": v_id,
                                "id_obszaru": area_id,
                                "nazwa_zmienna": v.get("nazwa-zmienna") or "",
                                "obszar_tematyczny": area_name_map.get(area_id, ""),
                            }
                        )
            storage.put_json_gz(storage.dbw_dict_key("variables_configured"), var_rows)
            for row in var_rows:
                biz_code, sec_id = var_biz_map.get(row["id_zmienna"], (None, None))
                cur.execute(
                    """
                    INSERT INTO ref.dim_variable (
                        id_zmienna, id_obszaru, nazwa_zmienna, obszar_tematyczny, business_code, id_przekroj, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (id_zmienna) DO UPDATE SET
                        id_obszaru = EXCLUDED.id_obszaru,
                        nazwa_zmienna = EXCLUDED.nazwa_zmienna,
                        obszar_tematyczny = EXCLUDED.obszar_tematyczny,
                        business_code = COALESCE(EXCLUDED.business_code, ref.dim_variable.business_code),
                        id_przekroj = COALESCE(EXCLUDED.id_przekroj, ref.dim_variable.id_przekroj),
                        updated_at = now()
                    """,
                    (
                        row["id_zmienna"],
                        row["id_obszaru"],
                        row["nazwa_zmienna"],
                        row["obszar_tematyczny"],
                        biz_code,
                        sec_id,
                    ),
                )
            print(f"      Upserted {len(var_rows)} rows into ref.dim_variable")

            print(f"[5/5] Fetching DBW section positions for sections {target_sections}...")
            total_pos = 0
            for sec_id in target_sections:
                positions = dbw.get_section_positions(sec_id)
                storage.put_json_gz(storage.dbw_dict_key(f"positions_sec_{sec_id}"), positions)
                for p in positions:
                    pos_id = int(p["id-pozycja"])
                    cur.execute(
                        """
                        INSERT INTO ref.dim_position (
                            id_przekroj, id_wymiar, id_pozycja, nazwa_wymiar, nazwa_pozycja, business_code, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (id_przekroj, id_wymiar, id_pozycja) DO UPDATE SET
                            nazwa_wymiar = EXCLUDED.nazwa_wymiar,
                            nazwa_pozycja = EXCLUDED.nazwa_pozycja,
                            business_code = EXCLUDED.business_code,
                            updated_at = now()
                        """,
                        (
                            sec_id,
                            int(p["id-wymiar"]),
                            pos_id,
                            p.get("nazwa-wymiar") or "",
                            p.get("nazwa-pozycja") or "",
                            pos_biz_map.get((sec_id, pos_id)),
                        ),
                    )
                total_pos += len(positions)
            print(f"      Upserted {total_pos} rows into ref.dim_position")

        conn.commit()
    print("OK: All GUS DBW dictionaries synced to Supabase Bronze (S3) and Silver (ref.*).")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync GUS DBW dictionaries into Supabase.")
    parser.add_argument("--codes-only", action="store_true", help="Only update business_code labels from YAML (0 API calls).")
    args = parser.parse_args()
    try:
        if args.codes_only:
            sync_business_codes_only()
        else:
            sync_all_dictionaries()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

