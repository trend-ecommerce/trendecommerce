"""Script de atualização e recalibração histórica 100% determinística até 30/11/2026.

1. Localiza dinamicamente o banco da API (API_Historico_Vendas/data/historico_vendas.db)
   em qualquer computador Windows via Path.home() (Desktop, OneDrive/Desktop,
   OneDrive/Área de Trabalho, Downloads) ou fallback local/Render (data/catalog_500_products.json
   + data/trendcommerce_dev.db).
2. Estende o histórico de vendas até 2026-11-30 para todos os 500 produtos e recalibra
   toda a série de forma 100% determinística (baseada apenas em vol_base, perfil_sazonal
   e seed=20261201 + pid * 97), independente do estado anterior do arquivo .db,
   preservando o pico explícito de 1133 un do Produto 124 em 29/10/2026 e Black Friday em 27/11/2026.
   Processa gravações em lotes de 50 produtos (chunked) para operar com segurança abaixo de 512 MB RAM (Render Free Tier).
3. Sincroniza 100% dos registros (2020-01-01 a 2026-11-30) para data/trendcommerce_dev.db
   via VendasApiClient.sync_to_trendecommerce.
"""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Adiciona a raiz do projeto ao sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import get_engine, get_session  # noqa: E402
from src.database.models import Base, Product, SalesHistory  # noqa: E402
from src.services.vendas_api_client import vendas_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("UpdateHistoricalData")

LOCAL_DB_PATH = PROJECT_ROOT / "data" / "trendcommerce_dev.db"
CATALOG_JSON_PATH = PROJECT_ROOT / "data" / "catalog_500_products.json"
CHUNK_SIZE_PRODUCTS = 50

CICLO_A_EXPLICIT_IDS = {366, 319, 337, 389, 106, 114}
CICLO_A_PROFILES = {"FITNESS_ANO_NOVO", "VERAO_CALOR", "REGULAR"}
CICLO_B_PROFILES = {"VERAO_CALOR", "VOLTA_AS_AULAS", "FITNESS_ANO_NOVO"}
CICLO_C_PROFILES = {"DIA_DAS_MAES", "DIA_DOS_NAMORADOS", "INVERNO_FRIO"}
CICLO_D_PROFILES = {"NATAL_FIM_DE_ANO", "BLACK_FRIDAY_TECH"}


def _load_catalog_products() -> list[dict]:
    """Carrega metadados dos 500 produtos oficiais de data/catalog_500_products.json."""
    if not CATALOG_JSON_PATH.exists():
        return []
    try:
        with open(CATALOG_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as err:
        logger.warning(f"Falha ao ler {CATALOG_JSON_PATH}: {err}")
        return []


def _get_target_local_sqlite_path(engine=None) -> Optional[Path]:
    """Resolve o caminho SQLite ativo a partir da URL configurada no SQLAlchemy."""
    eng = engine or get_engine()
    url_str = str(eng.url)
    if not url_str.startswith("sqlite:///"):
        return None
    url_db = getattr(eng.url, "database", None)
    if url_db and url_db != ":memory:":
        p = Path(url_db)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return LOCAL_DB_PATH


def _infer_perfil_from_title(nome: str) -> str:
    t = str(nome).lower()
    if "natal" in t or "pisca-pisca" in t:
        return "NATAL_FIM_DE_ANO"
    if any(k in t for k in ("whey", "creatina", "faixas", "corda", "fitness")):
        return "FITNESS_ANO_NOVO"
    if any(k in t for k in ("protetor solar", "ventilador", "ar-condicionado", "squeeze")):
        return "VERAO_CALOR"
    if any(k in t for k in ("notebook", "tablet", "escolar")):
        return "VOLTA_AS_AULAS"
    if any(k in t for k in ("edredom", "aquecedor", "moletom")):
        return "INVERNO_FRIO"
    return "REGULAR"


def _find_inflation_csv(api_db_path: Optional[Path] = None) -> Optional[Path]:
    """Localiza dinamicamente inflacao_historica.csv em qualquer computador Windows."""
    candidates: list[Path] = []
    if api_db_path is not None:
        candidates.append(api_db_path.parent / "inflacao_historica.csv")

    home = Path.home()
    roots = [
        PROJECT_ROOT.parent,
        home / "Desktop",
        home / "Área de Trabalho",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Área de Trabalho",
        home / "Downloads",
        home / "OneDrive" / "Downloads",
    ]
    try:
        for od_dir in home.glob("OneDrive*"):
            if od_dir.is_dir():
                for sub in ("Desktop", "Área de Trabalho", "Downloads"):
                    roots.append(od_dir / sub)
    except Exception:
        pass

    for root in roots:
        candidates.append(root / "API_Historico_Vendas" / "data" / "inflacao_historica.csv")
        candidates.append(root / "API_Historico_Vendas" / "API_Historico_Vendas" / "data" / "inflacao_historica.csv")

    candidates.append(PROJECT_ROOT / "data" / "inflacao_historica.csv")

    for p in candidates:
        if p and p.exists():
            return p
    return None


def _seed_float_from_key(pid: int, salt: str) -> float:
    h = hashlib.md5(f"{pid}:{salt}".encode("utf-8")).digest()
    return int.from_bytes(h[:4], "little") / 0xFFFFFFFF


def _build_seasonal_curve(
    pid: int,
    perfil: str,
    months: np.ndarray,
    days: np.ndarray,
    days_in_month: np.ndarray,
) -> np.ndarray:
    """Constrói multiplicador sazonal diário (2020-2026) combinando ciclos reais de Alta -> Queda."""
    n = len(months)
    prog = np.clip((days - 1) / np.maximum(1, days_in_month - 1), 0.0, 1.0)
    mult = np.ones(n, dtype=np.float64)

    in_ciclo_a = (pid in CICLO_A_EXPLICIT_IDS) or (
        (pid % 3 == 0) and (perfil in CICLO_A_PROFILES)
    )
    in_ciclo_b = perfil in CICLO_B_PROFILES
    in_ciclo_c = perfil in CICLO_C_PROFILES
    in_ciclo_d = perfil in CICLO_D_PROFILES

    if perfil == "INVERNO_FRIO":
        base_map = {1: 0.62, 2: 0.65, 3: 0.72, 4: 1.05, 5: 1.55, 6: 1.75, 7: 1.70, 8: 0.78, 9: 0.80, 10: 0.82, 11: 0.78, 12: 0.68}
    elif perfil == "VERAO_CALOR":
        base_map = {1: 1.75, 2: 1.72, 3: 0.82, 4: 0.78, 5: 0.82, 6: 0.78, 7: 0.78, 8: 0.88, 9: 1.05, 10: 1.18, 11: 1.32, 12: 1.58}
    elif perfil == "NATAL_FIM_DE_ANO":
        base_map = {1: 0.56, 2: 0.58, 3: 0.58, 4: 0.58, 5: 0.60, 6: 0.58, 7: 0.62, 8: 0.64, 9: 0.72, 10: 1.35, 11: 1.88, 12: 2.45}
    elif perfil == "BLACK_FRIDAY_TECH":
        base_map = {1: 0.88, 2: 0.86, 3: 0.90, 4: 0.92, 5: 0.94, 6: 0.94, 7: 0.96, 8: 0.96, 9: 1.00, 10: 1.35, 11: 1.85, 12: 1.65}
    elif perfil == "DIA_DOS_PAIS":
        base_map = {1: 0.90, 2: 0.92, 3: 0.92, 4: 0.94, 5: 0.98, 6: 1.02, 7: 1.28, 8: 1.48, 9: 0.92, 10: 0.96, 11: 1.05, 12: 1.22}
    elif perfil == "MULTISSAZONAL_TECH":
        base_map = {1: 0.96, 2: 1.15, 3: 0.94, 4: 0.92, 5: 0.95, 6: 0.96, 7: 1.18, 8: 1.02, 9: 0.96, 10: 1.02, 11: 1.22, 12: 1.42}
    else:
        base_map = {m: 0.98 for m in range(1, 13)}
        base_map[12] = 1.12

    for m, v in base_map.items():
        mult[months == m] = v

    if in_ciclo_b:
        m1 = months == 1
        m2 = months == 2
        m3 = months == 3
        m4 = months == 4
        mult[m1] = 1.62 + 0.23 * np.sin(prog[m1] * np.pi * 0.7)
        mult[m2] = 1.82 - 0.22 * prog[m2]
        mult[m3] = 0.85 - 0.08 * prog[m3]
        mult[m4] = 0.76 + 0.05 * np.sin(prog[m4] * np.pi)

    if in_ciclo_c:
        m5 = months == 5
        m6 = months == 6
        m7 = months == 7
        m8 = months == 8
        if perfil == "DIA_DAS_MAES":
            mult[m5] = 1.64 + 0.16 * np.sin(prog[m5] * np.pi)
            mult[m6] = 1.65 - 0.06 * prog[m6]
            mult[m7] = 1.60 - 0.05 * prog[m7]
        elif perfil == "DIA_DOS_NAMORADOS":
            mult[m5] = 1.56 + 0.12 * prog[m5]
            mult[m6] = 1.68 + 0.12 * np.sin(prog[m6] * np.pi)
            mult[m7] = 1.62 - 0.07 * prog[m7]
        else:
            mult[m5] = 1.55 + 0.15 * prog[m5]
            mult[m6] = 1.70 + 0.10 * prog[m6]
            mult[m7] = 1.78 - 0.18 * prog[m7]
        mult[m8] = 0.81 - 0.06 * prog[m8]

    if in_ciclo_a:
        m9 = months == 9
        m10 = months == 10
        m11 = months == 11
        m12 = months == 12
        mult[m9] = 1.42 + 0.12 * prog[m9]
        peak_curve = np.sin(np.clip(prog[m10] * 1.15, 0.0, 1.0) * np.pi * 0.68)
        mult[m10] = 1.55 + 0.20 * peak_curve
        mult[m11] = 1.50 - (1.50 - 0.82) * prog[m11]
        mult[m12] = 0.84 + 0.08 * prog[m12]

    if in_ciclo_d:
        m9 = months == 9
        m10 = months == 10
        m11 = months == 11
        m12 = months == 12
        mult[m9] = 0.72 + 0.18 * prog[m9] if perfil == "NATAL_FIM_DE_ANO" else 0.96 + 0.12 * prog[m9]
        mult[m10] = 1.15 + 0.40 * prog[m10]
        mult[m11] = 1.65 + (2.10 - 1.65) * prog[m11]
        if perfil == "NATAL_FIM_DE_ANO":
            mult[m12] = np.where(days[m12] <= 24, 2.25 + 0.45 * (days[m12] / 24.0), 1.35)
        else:
            mult[m12] = np.where(days[m12] <= 20, 1.85 - 0.20 * (days[m12] / 20.0), 1.45)

    return mult


def _compute_deterministic_product_series(
    pid_int: int,
    vol_base: float,
    perfil: str,
    months: np.ndarray,
    days: np.ndarray,
    years: np.ndarray,
    dims: np.ndarray,
    dows: np.ndarray,
    dates_str: np.ndarray,
) -> np.ndarray:
    """Calcula a série diária 100% determinística para um produto a partir apenas de
    (pid_int, vol_base, perfil, datas) com seed=20261201 + pid_int * 97, independente
    do estado anterior de vendas no arquivo .db.
    """
    n = len(dates_str)
    season_mult = _build_seasonal_curve(pid_int, perfil, months, days, dims)

    rng = np.random.default_rng(seed=20261201 + pid_int * 97)
    year_jitter = {y: 1.0 + rng.uniform(-0.04, 0.04) for y in range(2020, 2027)}
    year_mult = np.array(
        [year_jitter.get(int(y), 1.0) * (0.95 + 0.015 * (y - 2020)) for y in years],
        dtype=np.float64,
    )

    t_idx = np.arange(n, dtype=np.float64)
    phase1 = _seed_float_from_key(pid_int, "ph1") * 2 * np.pi
    phase2 = _seed_float_from_key(pid_int, "ph2") * 2 * np.pi
    wave = (
        0.055 * np.sin(2.0 * np.pi * t_idx / 11.0 + phase1)
        + 0.035 * np.cos(2.0 * np.pi * t_idx / 23.0 + phase2)
    )
    daily_jitter = rng.uniform(-0.085, 0.085, size=n)
    organic_mult = np.clip(1.0 + wave + daily_jitter, 0.85, 1.15)

    dow_weights = np.array([0.96, 0.94, 0.97, 1.01, 1.06, 1.09, 0.97], dtype=np.float64)
    dow_mult = dow_weights[dows]
    calibrated = vol_base * season_mult * year_mult * dow_mult * organic_mult

    # Picos válidos de Black Friday (27/11/2026) para itens do Ciclo D / Tech (sem afetar Ciclo A!)
    in_ciclo_a = (pid_int in CICLO_A_EXPLICIT_IDS) or (
        (pid_int % 3 == 0) and (perfil in CICLO_A_PROFILES)
    )
    if not in_ciclo_a and perfil in ("NATAL_FIM_DE_ANO", "BLACK_FRIDAY_TECH", "MULTISSAZONAL_TECH"):
        mask_bf = dates_str == "2026-11-27"
        if np.any(mask_bf):
            bf_spike = rng.uniform(2.8, 3.9)
            calibrated[mask_bf] = calibrated[mask_bf] * bf_spike
        mask_bf_adj = (dates_str == "2026-11-26") | (dates_str == "2026-11-28")
        if np.any(mask_bf_adj):
            calibrated[mask_bf_adj] = calibrated[mask_bf_adj] * 1.18

    final_v = np.maximum(
        np.maximum(3, int(round(vol_base * 0.30))),
        np.round(calibrated),
    ).astype(np.int64)

    # Ajuste final explícito no produto 124 (Garantia estrita de pico 1133 em 29/10/2026)
    if pid_int == 124:
        mask_oct29 = dates_str == "2026-10-29"
        final_v[mask_oct29] = 1133

    return final_v


def _compute_deterministic_price_series(
    pid_int: int,
    preco_base: float,
    perfil: str,
    years: np.ndarray,
    months: np.ndarray,
    days: np.ndarray,
    preco_end: Optional[float] = None,
) -> np.ndarray:
    """Gera série diária determinística de preços (2020-2026) ancorada em preco_base e preco_atual_2026_11_30."""
    n = len(years)
    t_idx = np.arange(n, dtype=np.float64)
    t_norm = t_idx / max(1, n - 1)
    base_val = float(preco_base or 100.0)
    target_end = float(preco_end) if preco_end else (base_val * 1.45)
    end_ratio = target_end / max(0.01, base_val)

    inflation_curve = 1.0 + (end_ratio - 1.0) * (t_norm ** 0.85)
    phase = _seed_float_from_key(pid_int, "price_ph") * 2.0 * np.pi
    micro_var = 1.0 + 0.012 * np.sin(2.0 * np.pi * t_idx / 45.0 + phase)

    promo = np.ones(n, dtype=np.float64)
    if perfil in ("BLACK_FRIDAY_TECH", "NATAL_FIM_DE_ANO", "MULTISSAZONAL_TECH"):
        mask_bf = (months == 11) & (days == 27)
        mask_bf_adj = (months == 11) & ((days == 26) | (days == 28))
        promo[mask_bf] = 0.90
        promo[mask_bf_adj] = 0.94

    prices = base_val * inflation_curve * micro_var * promo
    if preco_end and n > 0:
        prices[-1] = float(preco_end)
    return np.maximum(1.0, np.round(prices, 2))


def _load_inflation_map(api_db_path: Optional[Path] = None) -> dict[tuple[int, int], float]:
    infl_map: dict[tuple[int, int], float] = {}
    infl_csv = _find_inflation_csv(api_db_path)
    if infl_csv and infl_csv.exists():
        df_inf = pd.read_csv(infl_csv)
        for _, r in df_inf.iterrows():
            infl_map[(int(r["ano"]), int(r["mes"]))] = float(r["inflacao_mensal"])
    return infl_map


def update_api_sqlite_db(db_path: Path, is_local_format: bool = False) -> dict:
    """Atualiza e recalibra historico_vendas.db (ou fallback local/Render) até 2026-11-30 de forma determinística."""
    logger.info(f"Conectando ao banco: {db_path}")
    conn = sqlite3.connect(str(db_path), timeout=60.0)
    try:
        cur = conn.cursor()
        jm = cur.execute("PRAGMA journal_mode").fetchone()
        if not jm or str(jm[0]).lower() != "wal":
            cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA synchronous = NORMAL")
        cur.execute("PRAGMA temp_store = MEMORY")
        cur.execute("PRAGMA cache_size = -8000")
        return _update_api_sqlite_db_with_conn(conn, cur, db_path, is_local_format=is_local_format)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _update_local_sqlite_chunked(
    conn: sqlite3.Connection,
    cur: sqlite3.Cursor,
    db_path: Path,
) -> dict:
    """Popula ou recalibra banco local (Render / fallback) em lotes de 50 produtos (<512 MB RAM)."""
    catalog_list = _load_catalog_products()
    catalog_map = {int(p["id"]): p for p in catalog_list}

    existing_rows = cur.execute("SELECT id, title, price, platform FROM products").fetchall()
    existing_prod_count = len(existing_rows)
    non_api_count = sum(1 for r in existing_rows if str(r[3]) != "api_vendas")

    catalog_mismatch = False
    if catalog_list:
        if existing_prod_count < len(catalog_map) or non_api_count > 0:
            catalog_mismatch = True
        else:
            existing_by_id = {int(r[0]): (str(r[1]), round(float(r[2] or 0.0), 2)) for r in existing_rows}
            for pid, c in catalog_map.items():
                exp_pair = (str(c.get("nome") or f"Produto {pid}"), round(float(c.get("preco_base") or 100.0), 2))
                if existing_by_id.get(pid) != exp_pair:
                    catalog_mismatch = True
                    break

    # 1. Garantir catálogo oficial dos 500 produtos na tabela products (limpando títulos/preços antigos divergentes)
    if catalog_list and (existing_prod_count == 0 or catalog_mismatch):
        if existing_prod_count > 0:
            logger.info("[Local/Render] Catálogo divergente ou incompleto detectado. Limpando produtos/vendas antigos...")
            cur.execute("DELETE FROM sales_history")
            cur.execute("DELETE FROM products")
            conn.commit()

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        existing_ids = {int(r[0]) for r in cur.execute("SELECT id FROM products").fetchall()}
        to_insert_prods = []
        for p in catalog_list:
            pid = int(p["id"])
            if pid not in existing_ids:
                to_insert_prods.append((
                    pid,
                    f"API_{pid}",
                    "api_vendas",
                    str(p.get("nome") or f"Produto {pid}"),
                    str(p.get("categoria") or "Geral"),
                    float(p.get("preco_base") or 100.0),
                    "BRL",
                    "new",
                    1,
                    now_str,
                    now_str,
                ))
        if to_insert_prods:
            cur.executemany(
                """
                INSERT INTO products (
                    id, external_id, platform, title, category, price, currency, condition, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                to_insert_prods,
            )
            conn.commit()
            logger.info(f"[Local/Render] Inseridos {len(to_insert_prods)} produtos oficiais de catalog_500_products.json.")
        del to_insert_prods, existing_ids

    prod_rows = cur.execute("SELECT id, title, category, price FROM products ORDER BY id").fetchall()
    if not prod_rows:
        logger.warning(f"Nenhum produto encontrado em {db_path} e nenhum catálogo disponível.")
        return {
            "local_db_path": str(db_path),
            "total_rows": 0,
            "min_date": None,
            "max_date": None,
            "remaining_low_errors": 0,
        }

    # 2. Montar metadados sem carregar 1.26M linhas na memória
    prod_meta: dict[int, tuple[float, str, float, Optional[float]]] = {}
    for pid_raw, title, _cat, price in prod_rows:
        pid = int(pid_raw)
        if pid in catalog_map:
            c = catalog_map[pid]
            p_end = c.get("preco_atual_2026_11_30")
            prod_meta[pid] = (
                float(c.get("volume_base") or 40),
                str(c.get("perfil_sazonal") or "REGULAR"),
                float(c.get("preco_base") or price or 100.0),
                float(p_end) if p_end is not None else None,
            )
        else:
            qty_rows = cur.execute(
                "SELECT quantity_sold FROM sales_history WHERE product_id = ?",
                (pid,),
            ).fetchall()
            med_vol = int(round(float(np.median([r[0] for r in qty_rows])))) if qty_rows else 40
            prod_meta[pid] = (
                float(max(10, med_vol)),
                _infer_perfil_from_title(str(title or "")),
                float(price or 100.0),
                None,
            )

    # 3. Pré-computar calendário único (2526 dias: 2020-01-01 .. 2026-11-30)
    all_dates = pd.date_range("2020-01-01", "2026-11-30", freq="D")
    n_days = len(all_dates)
    dates_str = all_dates.strftime("%Y-%m-%d").to_numpy()
    years = all_dates.year.to_numpy(dtype=np.int32)
    months = all_dates.month.to_numpy(dtype=np.int32)
    days = all_dates.day.to_numpy(dtype=np.int32)
    dows = all_dates.dayofweek.to_numpy(dtype=np.int32)
    dims = all_dates.days_in_month.to_numpy(dtype=np.int32)
    del all_dates

    s_count, s_min, s_max = cur.execute(
        "SELECT COUNT(*), MIN(substr(date, 1, 10)), MAX(substr(date, 1, 10)) FROM sales_history"
    ).fetchone()
    s_count = int(s_count or 0)
    expected_full_rows = len(prod_rows) * n_days

    # 4A. Banco vazio ou incompleto (<90% da série ou início != 2020-01-01): geração em chunks de 50 produtos
    if s_count == 0 or str(s_min or "") != "2020-01-01" or s_count < int(expected_full_rows * 0.90):
        if s_count > 0:
            logger.info(f"[Local/Render] Limpando série parcial anterior ({s_count:,} linhas) para reconstrução limpa...")
            cur.execute("DELETE FROM sales_history")
            conn.commit()

        logger.info(
            f"[Local/Render] Gerando {expected_full_rows:,} registros determinísticos em lotes de {CHUNK_SIZE_PRODUCTS} produtos..."
        )
        # Dropar índices secundários durante inserção em lote reduz tempo de boot no Render em >5x
        cur.execute("DROP INDEX IF EXISTS idx_sales_product_date")
        cur.execute("DROP INDEX IF EXISTS idx_sales_date")
        conn.commit()

        dates_list = dates_str.tolist()
        try:
            for start_idx in range(0, len(prod_rows), CHUNK_SIZE_PRODUCTS):
                chunk = prod_rows[start_idx : start_idx + CHUNK_SIZE_PRODUCTS]
                batch_rows = []
                for prow in chunk:
                    pid_int = int(prow[0])
                    vol_base, perfil, preco_base, preco_end = prod_meta[pid_int]
                    final_v = _compute_deterministic_product_series(
                        pid_int=pid_int,
                        vol_base=vol_base,
                        perfil=perfil,
                        months=months,
                        days=days,
                        years=years,
                        dims=dims,
                        dows=dows,
                        dates_str=dates_str,
                    )
                    prices = _compute_deterministic_price_series(
                        pid_int=pid_int,
                        preco_base=preco_base,
                        perfil=perfil,
                        years=years,
                        months=months,
                        days=days,
                        preco_end=preco_end,
                    )
                    for d_s, qty_v, p_v in zip(dates_list, final_v.tolist(), prices.tolist()):
                        batch_rows.append((pid_int, d_s, qty_v, p_v))

                cur.executemany(
                    "INSERT INTO sales_history (product_id, date, quantity_sold, price_at_date, available_quantity, platform, collected_at) VALUES (?, ?, ?, ?, 100, 'api_vendas', CURRENT_TIMESTAMP)",
                    batch_rows,
                )
                conn.commit()
                del batch_rows
                gc.collect()
        finally:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales_history (product_id, date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_history (date)")
            conn.commit()
    else:
        # 4B. Banco já populado com >=90% de histórico desde 2020-01-01: ajustar cauda de nov/2026 e recalibrar em chunks de 50 produtos
        if cur.execute("SELECT 1 FROM sales_history WHERE date(date) > '2026-11-30' LIMIT 1").fetchone():
            cur.execute("DELETE FROM sales_history WHERE date(date) > '2026-11-30'")
            conn.commit()

        existing_nov_tail = cur.execute(
            "SELECT COUNT(*) FROM sales_history WHERE date(date) >= '2026-11-03' AND date(date) <= '2026-11-30'"
        ).fetchone()[0]
        expected_nov_tail = len(prod_rows) * 28

        if existing_nov_tail != expected_nov_tail:
            cur.execute("DELETE FROM sales_history WHERE date(date) >= '2026-11-03' AND date(date) <= '2026-11-30'")
            conn.commit()

            last_prices = dict(
                cur.execute("""
                    SELECT s.product_id, s.price_at_date
                    FROM sales_history s
                    JOIN (
                        SELECT product_id, MAX(date) AS md FROM sales_history WHERE date(date) <= '2026-11-02' GROUP BY product_id
                    ) m ON s.product_id = m.product_id AND s.date = m.md
                """).fetchall()
            )
            new_dates = pd.date_range("2026-11-03", "2026-11-30", freq="D")
            rows_to_insert = []
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            for prow in prod_rows:
                pid = int(prow[0])
                vol_base, perfil, preco_base, _ = prod_meta[pid]
                base_price = float(last_prices.get(pid) or preco_base or 100.0)
                for step_idx, dt in enumerate(new_dates):
                    promo = 1.0
                    if dt.day in (26, 27, 28) and perfil in ("BLACK_FRIDAY_TECH", "NATAL_FIM_DE_ANO", "MULTISSAZONAL_TECH"):
                        promo = 0.90 if dt.day == 27 else 0.94
                    day_drift = 1.0 - 0.00015 * step_idx + 0.002 * np.sin(step_idx * 0.7 + pid)
                    p_val = round(max(1.0, base_price * day_drift * promo), 2)
                    rows_to_insert.append((pid, dt.strftime("%Y-%m-%d"), int(round(vol_base)), p_val, 100, "api_vendas", now_str))
            cur.executemany(
                "INSERT INTO sales_history (product_id, date, quantity_sold, price_at_date, available_quantity, platform, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows_to_insert,
            )
            conn.commit()
            del rows_to_insert, last_prices

        # Recalibração em lotes de 50 produtos sem carregar toda a tabela na RAM
        for start_idx in range(0, len(prod_rows), CHUNK_SIZE_PRODUCTS):
            chunk_pids = [int(r[0]) for r in prod_rows[start_idx : start_idx + CHUNK_SIZE_PRODUCTS]]
            placeholders = ",".join("?" for _ in chunk_pids)
            chunk_df = pd.read_sql_query(
                f"SELECT id, product_id AS produto_id, substr(date, 1, 10) AS data_venda FROM sales_history WHERE product_id IN ({placeholders}) ORDER BY product_id, data_venda",
                conn,
                params=chunk_pids,
            )
            if chunk_df.empty:
                continue

            chunk_dt = pd.to_datetime(chunk_df["data_venda"])
            chunk_df["ano"] = chunk_dt.dt.year.to_numpy(dtype=np.int32)
            chunk_df["mes"] = chunk_dt.dt.month.to_numpy(dtype=np.int32)
            chunk_df["dia"] = chunk_dt.dt.day.to_numpy(dtype=np.int32)
            chunk_df["dow"] = chunk_dt.dt.dayofweek.to_numpy(dtype=np.int32)
            chunk_df["dim"] = chunk_dt.dt.days_in_month.to_numpy(dtype=np.int32)

            recal_pairs: list[tuple[int, int]] = []
            for pid, grp in chunk_df.groupby("produto_id", sort=False):
                pid_int = int(pid)
                vol_base, perfil, _, _ = prod_meta[pid_int]
                final_v = _compute_deterministic_product_series(
                    pid_int=pid_int,
                    vol_base=vol_base,
                    perfil=perfil,
                    months=grp["mes"].to_numpy(np.int32),
                    days=grp["dia"].to_numpy(np.int32),
                    years=grp["ano"].to_numpy(np.int32),
                    dims=grp["dim"].to_numpy(np.int32),
                    dows=grp["dow"].to_numpy(np.int32),
                    dates_str=grp["data_venda"].to_numpy(),
                )
                recal_pairs.extend(zip(grp["id"].tolist(), final_v.tolist()))

            cur.execute("DROP TABLE IF EXISTS _tmp_recal_local")
            cur.execute("CREATE TEMP TABLE _tmp_recal_local (id INTEGER PRIMARY KEY, vendas INTEGER NOT NULL)")
            cur.executemany("INSERT INTO _tmp_recal_local (id, vendas) VALUES (?, ?)", recal_pairs)
            cur.execute(
                "UPDATE sales_history SET quantity_sold = (SELECT t.vendas FROM _tmp_recal_local t WHERE t.id = sales_history.id) WHERE EXISTS (SELECT 1 FROM _tmp_recal_local t WHERE t.id = sales_history.id)"
            )
            cur.execute("DROP TABLE IF EXISTS _tmp_recal_local")
            conn.commit()
            del chunk_df, chunk_dt, recal_pairs
            gc.collect()

    try:
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass

    stats = cur.execute(
        "SELECT COUNT(*), MIN(substr(date, 1, 10)), MAX(substr(date, 1, 10)), SUM(CASE WHEN quantity_sold <= 1 THEN 1 ELSE 0 END) FROM sales_history"
    ).fetchone()
    return {
        "local_db_path": str(db_path),
        "total_rows": stats[0],
        "min_date": stats[1],
        "max_date": stats[2],
        "remaining_low_errors": stats[3],
    }


def _update_api_sqlite_db_with_conn(
    conn: sqlite3.Connection,
    cur: sqlite3.Cursor,
    db_path: Path,
    is_local_format: bool = False,
) -> dict:

    if is_local_format:
        return _update_local_sqlite_chunked(conn, cur, db_path)

    # 1. Carregar catálogo oficial da API de Vendas
    prods_df = pd.read_sql_query(
        "SELECT id, nome, categoria, preco_base, volume_base, perfil_sazonal, grupo_anomalia FROM produtos ORDER BY id",
        conn,
    )
    infl_map = _load_inflation_map(db_path)
    nov_infl = infl_map.get((2026, 11), 0.30)

    # 2. Garantir cobertura exata 2020-01-01 .. 2026-11-30 para todos os 500 produtos (idempotente)
    if cur.execute("SELECT 1 FROM vendas_historicas WHERE data_venda > '2026-11-30' LIMIT 1").fetchone():
        cur.execute("DELETE FROM vendas_historicas WHERE data_venda > '2026-11-30'")
        conn.commit()
    existing_nov_tail = cur.execute(
        "SELECT COUNT(*) FROM vendas_historicas WHERE data_venda >= '2026-11-03' AND data_venda <= '2026-11-30'"
    ).fetchone()[0]
    expected_nov_tail = len(prods_df) * 28

    if existing_nov_tail != expected_nov_tail:
        logger.info(
            f"Ajustando janela 2026-11-03..2026-11-30 (atual={existing_nov_tail}, esperado={expected_nov_tail})..."
        )
        cur.execute("DELETE FROM vendas_historicas WHERE data_venda >= '2026-11-03' AND data_venda <= '2026-11-30'")
        conn.commit()
        existing_max_id = cur.execute("SELECT COALESCE(MAX(id), 0) FROM vendas_historicas").fetchone()[0]

        last_prices = dict(
            cur.execute("""
                SELECT v.produto_id, v.preco
                FROM vendas_historicas v
                JOIN (
                    SELECT produto_id, MAX(data_venda) AS md
                    FROM vendas_historicas
                    WHERE data_venda <= '2026-11-02'
                    GROUP BY produto_id
                ) m ON v.produto_id = m.produto_id AND v.data_venda = m.md
            """).fetchall()
        )

        new_dates = pd.date_range("2026-11-03", "2026-11-30", freq="D")
        rows_to_insert = []
        next_id = int(existing_max_id) + 1

        for _, prow in prods_df.iterrows():
            pid = int(prow["id"])
            nome = str(prow["nome"])
            cat = str(prow["categoria"])
            perfil = str(prow["perfil_sazonal"] or "REGULAR")
            base_price = float(last_prices.get(pid) or prow["preco_base"] or 100.0)
            vol_base = int(prow["volume_base"] or 40)

            for step_idx, dt in enumerate(new_dates):
                d_str = dt.strftime("%Y-%m-%d")
                promo = 1.0
                if dt.day in (26, 27, 28) and perfil in ("BLACK_FRIDAY_TECH", "NATAL_FIM_DE_ANO", "MULTISSAZONAL_TECH"):
                    promo = 0.90 if dt.day == 27 else 0.94
                day_drift = 1.0 - 0.00015 * step_idx + 0.002 * np.sin(step_idx * 0.7 + pid)
                p_val = round(max(1.0, base_price * day_drift * promo), 2)

                rows_to_insert.append(
                    (next_id, pid, nome, p_val, vol_base, cat, d_str, 2026, 11, int(dt.day), nov_infl)
                )
                next_id += 1

        cur.executemany(
            """
            INSERT INTO vendas_historicas (
                id, produto_id, nome_produto, preco, vendas, categoria, data_venda, ano, mes, dia, inflacao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        conn.commit()
        logger.info(f"Inseridos {len(rows_to_insert):,} registros faltantes (2026-11-03 a 2026-11-30).")
    else:
        logger.info("Janela 2026-11-03..2026-11-30 já possui 14.000 registros completos.")

    # 3. Carregar datas ordenadas e recalibrar 100% deterministicamente (independente do estado prévio)
    logger.info("Recalibrando série completa (2020-01-01 a 2026-11-30) de forma 100% determinística...")
    sales_all = pd.read_sql_query(
        "SELECT id, produto_id, data_venda, ano, mes, dia FROM vendas_historicas ORDER BY produto_id, data_venda",
        conn,
    )
    sales_all["dt"] = pd.to_datetime(sales_all["data_venda"])
    sales_all["dow"] = sales_all["dt"].dt.dayofweek.to_numpy()
    sales_all["dim"] = sales_all["dt"].dt.days_in_month.to_numpy()

    prod_meta = {
        int(r["id"]): (
            float(r["volume_base"] or 40),
            str(r["perfil_sazonal"] or "REGULAR"),
        )
        for _, r in prods_df.iterrows()
    }

    new_vendas_list = []
    for pid, grp in sales_all.groupby("produto_id", sort=False):
        pid_int = int(pid)
        vol_base, perfil = prod_meta[pid_int]
        final_v = _compute_deterministic_product_series(
            pid_int=pid_int,
            vol_base=vol_base,
            perfil=perfil,
            months=grp["mes"].to_numpy(dtype=np.int32),
            days=grp["dia"].to_numpy(dtype=np.int32),
            years=grp["ano"].to_numpy(dtype=np.int32),
            dims=grp["dim"].to_numpy(dtype=np.int32),
            dows=grp["dow"].to_numpy(dtype=np.int32),
            dates_str=grp["data_venda"].to_numpy(),
        )
        new_vendas_list.append(pd.DataFrame({"id": grp["id"].to_numpy(), "vendas": final_v}))

    updated_df = pd.concat(new_vendas_list, ignore_index=True)

    # 4. Aplicar atualização em lote no SQLite de origem
    logger.info(f"Gravando {len(updated_df):,} linhas determinísticas em {db_path}...")
    cur.execute("DROP TABLE IF EXISTS _tmp_recal_vendas")
    cur.execute("CREATE TEMP TABLE _tmp_recal_vendas (id INTEGER PRIMARY KEY, vendas INTEGER NOT NULL)")
    cur.executemany(
        "INSERT INTO _tmp_recal_vendas (id, vendas) VALUES (?, ?)",
        zip(updated_df["id"].tolist(), updated_df["vendas"].tolist()),
    )
    cur.execute("""
        UPDATE vendas_historicas
        SET vendas = (SELECT t.vendas FROM _tmp_recal_vendas t WHERE t.id = vendas_historicas.id)
        WHERE EXISTS (SELECT 1 FROM _tmp_recal_vendas t WHERE t.id = vendas_historicas.id)
    """)
    cur.execute("DROP TABLE IF EXISTS _tmp_recal_vendas")
    conn.commit()

    stats = cur.execute(
        "SELECT COUNT(*), MIN(data_venda), MAX(data_venda), SUM(CASE WHEN vendas <= 1 THEN 1 ELSE 0 END) FROM vendas_historicas"
    ).fetchone()

    logger.info(
        f"API DB atualizado: {stats[0]:,} registros | faixa {stats[1]} .. {stats[2]} | erros <=1 restantes: {stats[3]}"
    )

    return {
        "api_db_path": str(db_path),
        "total_rows": stats[0],
        "min_date": stats[1],
        "max_date": stats[2],
        "remaining_low_errors": stats[3],
    }


def _populate_non_sqlite_from_catalog(engine) -> dict:
    """Fallback chunked (50 produtos) para bancos não-SQLite (ex: PostgreSQL no Render)."""
    catalog_list = _load_catalog_products()
    if not catalog_list:
        return {"total_rows": 0, "min_date": None, "max_date": None}

    all_dates = pd.date_range("2020-01-01", "2026-11-30", freq="D")
    dates_py = [dt.to_pydatetime() for dt in all_dates]
    dates_str = all_dates.strftime("%Y-%m-%d").to_numpy()
    years = all_dates.year.to_numpy(dtype=np.int32)
    months = all_dates.month.to_numpy(dtype=np.int32)
    days = all_dates.day.to_numpy(dtype=np.int32)
    dows = all_dates.dayofweek.to_numpy(dtype=np.int32)
    dims = all_dates.days_in_month.to_numpy(dtype=np.int32)
    del all_dates

    now_dt = datetime.utcnow()
    session = get_session(engine)
    try:
        session.query(SalesHistory).delete()
        session.query(Product).delete()
        session.commit()

        prod_dicts = [
            {
                "id": int(p["id"]),
                "external_id": f"API_{int(p['id'])}",
                "platform": "api_vendas",
                "title": str(p.get("nome") or f"Produto {p['id']}"),
                "category": str(p.get("categoria") or "Geral"),
                "price": float(p.get("preco_base") or 100.0),
                "currency": "BRL",
                "condition": "new",
                "is_active": True,
                "created_at": now_dt,
                "updated_at": now_dt,
            }
            for p in catalog_list
        ]
        session.execute(Product.__table__.insert(), prod_dicts)
        session.commit()
        del prod_dicts

        total_rows = 0
        for start_idx in range(0, len(catalog_list), CHUNK_SIZE_PRODUCTS):
            chunk = catalog_list[start_idx : start_idx + CHUNK_SIZE_PRODUCTS]
            batch_rows = []
            for p in chunk:
                pid_int = int(p["id"])
                vol_base = float(p.get("volume_base") or 40)
                perfil = str(p.get("perfil_sazonal") or "REGULAR")
                preco_base = float(p.get("preco_base") or 100.0)
                preco_end = p.get("preco_atual_2026_11_30")
                final_v = _compute_deterministic_product_series(
                    pid_int=pid_int,
                    vol_base=vol_base,
                    perfil=perfil,
                    months=months,
                    days=days,
                    years=years,
                    dims=dims,
                    dows=dows,
                    dates_str=dates_str,
                )
                prices = _compute_deterministic_price_series(
                    pid_int=pid_int,
                    preco_base=preco_base,
                    perfil=perfil,
                    years=years,
                    months=months,
                    days=days,
                    preco_end=float(preco_end) if preco_end is not None else None,
                )
                for d_py, qty_v, p_v in zip(dates_py, final_v.tolist(), prices.tolist()):
                    batch_rows.append({
                        "product_id": pid_int,
                        "date": d_py,
                        "quantity_sold": qty_v,
                        "price_at_date": p_v,
                        "available_quantity": 100,
                        "platform": "api_vendas",
                        "collected_at": now_dt,
                    })
            session.execute(SalesHistory.__table__.insert(), batch_rows)
            session.commit()
            total_rows += len(batch_rows)
            del batch_rows
            gc.collect()

        # Ajustar sequences caso seja PostgreSQL no Render
        try:
            if getattr(engine, "dialect", None) and engine.dialect.name == "postgresql":
                from sqlalchemy import text
                session.execute(text("SELECT setval(pg_get_serial_sequence('products', 'id'), COALESCE(MAX(id), 1)) FROM products;"))
                session.execute(text("SELECT setval(pg_get_serial_sequence('sales_history', 'id'), COALESCE(MAX(id), 1)) FROM sales_history;"))
                session.commit()
        except Exception as seq_err:
            logger.warning(f"Aviso ao ajustar sequences PostgreSQL: {seq_err}")

        return {"total_rows": total_rows, "min_date": "2020-01-01", "max_date": "2026-11-30"}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sync_to_local_db() -> dict:
    """Sincroniza historico_vendas.db -> data/trendcommerce_dev.db usando VendasApiClient."""
    logger.info("Sincronizando historico_vendas.db -> data/trendcommerce_dev.db via VendasApiClient...")
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = get_session(engine)
    try:
        res = vendas_client.sync_to_trendecommerce(session, min_date="2020-01-01")
        if not res.get("success"):
            raise RuntimeError(f"Falha na sincronização: {res.get('error')}")
    finally:
        session.close()

    local_db_file = _get_target_local_sqlite_path(engine) or LOCAL_DB_PATH

    conn = sqlite3.connect(str(local_db_file), timeout=30.0)
    try:
        local_stats = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date), SUM(CASE WHEN quantity_sold <= 1 THEN 1 ELSE 0 END) FROM sales_history"
        ).fetchone()
    finally:
        conn.close()
    logger.info(
        f"Local DB sincronizado: {local_stats[0]:,} registros | faixa {local_stats[1]} .. {local_stats[2]} | erros <=1: {local_stats[3]}"
    )
    return {
        **res,
        "local_min_date": local_stats[1],
        "local_max_date": local_stats[2],
        "local_low_errors": local_stats[3],
    }


def main() -> dict:
    api_db = vendas_client.get_database_path()
    if api_db and api_db.exists():
        res_api = update_api_sqlite_db(api_db, is_local_format=False)
        res_sync = sync_to_local_db()
        logger.info(f"Concluído com sucesso: API={res_api} | LOCAL={res_sync}")
        return {"mode": "api_and_local", "api": res_api, "local": res_sync}

    engine = get_engine()
    Base.metadata.create_all(engine)
    target_local_db = _get_target_local_sqlite_path(engine)

    if target_local_db is not None and (target_local_db.exists() or CATALOG_JSON_PATH.exists()):
        res_local = update_api_sqlite_db(target_local_db, is_local_format=True)
        logger.info(f"Fallback local/Render concluído com sucesso: LOCAL={res_local}")
        return {"mode": "local_only", "local": res_local}

    if target_local_db is None and CATALOG_JSON_PATH.exists():
        res_sa = _populate_non_sqlite_from_catalog(engine)
        logger.info(f"Fallback SQLAlchemy/Render concluído com sucesso: LOCAL={res_sa}")
        return {"mode": "local_sqlalchemy", "local": res_sa}

    raise FileNotFoundError(
        f"Nenhum banco nem catálogo encontrado em {LOCAL_DB_PATH} ou {CATALOG_JSON_PATH}."
    )


if __name__ == "__main__":
    main()
