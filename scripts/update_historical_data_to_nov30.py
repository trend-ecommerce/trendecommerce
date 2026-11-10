"""Script de atualização e recalibração histórica até 30/11/2026.

1. Estende o histórico de vendas de 2026-11-03 até 2026-11-30 para todos os 500 produtos
   no banco da API (C:\\Users\\Aluno\\Desktop\\API_Historico_Vendas\\data\\historico_vendas.db)
   ou diretamente no banco local (data/trendcommerce_dev.db) caso o banco da API não exista.
2. Recalibra as curvas sazonais mensais (2020 a 2026) com ciclos reais de Alta -> Queda
   (Ciclos A, B, C e D), variação diária orgânica (±8% a ±15%), preservação de outliers
   superiores válidos (ex: 1133 un em 29/10/2026 para o produto 124, Black Friday 27/11/2026)
   e remoção de zeros de erro de captura.
3. Sincroniza 100% dos registros (2020-01-01 a 2026-11-30) para data/trendcommerce_dev.db
   via VendasApiClient.sync_to_trendecommerce.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Adiciona a raiz do projeto ao sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import get_database_url, get_engine, get_session  # noqa: E402
from src.database.models import Base  # noqa: E402
from src.services.vendas_api_client import vendas_client  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("UpdateHistoricalData")

API_DB_PRIMARY = Path(r"C:\Users\Aluno\Desktop\API_Historico_Vendas\data\historico_vendas.db")
INFLATION_CSV = Path(r"C:\Users\Aluno\Desktop\API_Historico_Vendas\data\inflacao_historica.csv")
LOCAL_DB_PATH = PROJECT_ROOT / "data" / "trendcommerce_dev.db"

CICLO_A_EXPLICIT_IDS = {366, 319, 337, 389, 106, 114}
CICLO_A_PROFILES = {"FITNESS_ANO_NOVO", "VERAO_CALOR", "REGULAR"}
CICLO_B_PROFILES = {"VERAO_CALOR", "VOLTA_AS_AULAS", "FITNESS_ANO_NOVO"}
CICLO_C_PROFILES = {"DIA_DAS_MAES", "DIA_DOS_NAMORADOS", "INVERNO_FRIO"}
CICLO_D_PROFILES = {"NATAL_FIM_DE_ANO", "BLACK_FRIDAY_TECH"}


def _seed_float_from_key(pid: int, salt: str) -> float:
    h = hashlib.md5(f"{pid}:{salt}".encode("utf-8")).digest()
    val = int.from_bytes(h[:4], "little") / 0xFFFFFFFF
    return val


def _build_seasonal_curve(
    pid: int,
    perfil: str,
    months: np.ndarray,
    days: np.ndarray,
    days_in_month: np.ndarray,
) -> np.ndarray:
    """Constrói multiplicador sazonal diário (2020-2026) combinando ciclos reais de Alta -> Queda."""
    n = len(months)
    # Progresso intra-mês [0.0 .. 1.0]
    prog = np.clip((days - 1) / np.maximum(1, days_in_month - 1), 0.0, 1.0)
    mult = np.ones(n, dtype=np.float64)

    in_ciclo_a = (pid in CICLO_A_EXPLICIT_IDS) or (
        (pid % 3 == 0) and (perfil in CICLO_A_PROFILES)
    )
    in_ciclo_b = perfil in CICLO_B_PROFILES
    in_ciclo_c = perfil in CICLO_C_PROFILES
    in_ciclo_d = perfil in CICLO_D_PROFILES

    # Perfil base neutro para meses fora dos ciclos principais
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

    # Ciclo B: Alta Forte em Jan/Fev (1.60x..1.85x) -> Queda Acentuada em Mar/Abr (0.75x..0.85x)
    if in_ciclo_b:
        m1 = months == 1
        m2 = months == 2
        m3 = months == 3
        m4 = months == 4
        # Jan sobe de 1.62 até 1.85; Fev mantém alto 1.82 -> 1.60
        mult[m1] = 1.62 + 0.23 * np.sin(prog[m1] * np.pi * 0.7)
        mult[m2] = 1.82 - 0.22 * prog[m2]
        # Mar cai forte pós-verão 0.85 -> 0.77; Abr mantém baixo 0.76 -> 0.80
        mult[m3] = 0.85 - 0.08 * prog[m3]
        mult[m4] = 0.76 + 0.05 * np.sin(prog[m4] * np.pi)

    # Ciclo C: Alta em Mai/Jun/Jul (1.55x..1.80x) -> Queda em Ago (0.78x)
    if in_ciclo_c:
        m5 = months == 5
        m6 = months == 6
        m7 = months == 7
        m8 = months == 8
        if perfil == "DIA_DAS_MAES":
            mult[m5] = 1.64 + 0.16 * np.sin(prog[m5] * np.pi)  # pico no Dia das Mães em Maio
            mult[m6] = 1.65 - 0.06 * prog[m6]
            mult[m7] = 1.60 - 0.05 * prog[m7]
        elif perfil == "DIA_DOS_NAMORADOS":
            mult[m5] = 1.56 + 0.12 * prog[m5]
            mult[m6] = 1.68 + 0.12 * np.sin(prog[m6] * np.pi)  # pico Dia dos Namorados em Junho
            mult[m7] = 1.62 - 0.07 * prog[m7]
        else:  # INVERNO_FRIO
            mult[m5] = 1.55 + 0.15 * prog[m5]
            mult[m6] = 1.70 + 0.10 * prog[m6]
            mult[m7] = 1.78 - 0.18 * prog[m7]
        # Retração clara em Agosto (0.78x)
        mult[m8] = 0.81 - 0.06 * prog[m8]

    # Ciclo A: Alta Forte em Setembro e Outubro -> Queda Progressiva em Novembro
    if in_ciclo_a:
        m9 = months == 9
        m10 = months == 10
        m11 = months == 11
        m12 = months == 12
        # Setembro: 1.42 -> 1.54 (média ~1.45x..1.48x)
        mult[m9] = 1.42 + 0.12 * prog[m9]
        # Outubro: continua subindo até ~1.75x em meados/fim de Out, fechando Out ~1.64x
        peak_curve = np.sin(np.clip(prog[m10] * 1.15, 0.0, 1.0) * np.pi * 0.68)
        mult[m10] = 1.55 + 0.20 * peak_curve
        # Novembro (01/11 a 30/11): inicia em 1.50x e desacelera dia após dia até 0.82x em 30/11
        mult[m11] = 1.50 - (1.50 - 0.82) * prog[m11]
        # Dezembro (2020-2025): mantém acomodação pós-queda ~0.85x -> 0.92x
        mult[m12] = 0.84 + 0.08 * prog[m12]

    # Ciclo D: Alta Progressiva em Outubro (1.35x) e Novembro (1.65x -> 2.10x) rumo ao Natal
    if in_ciclo_d:
        m9 = months == 9
        m10 = months == 10
        m11 = months == 11
        m12 = months == 12
        # Setembro pré-aquecimento
        mult[m9] = 0.72 + 0.18 * prog[m9] if perfil == "NATAL_FIM_DE_ANO" else 0.96 + 0.12 * prog[m9]
        # Outubro: subida consistente em torno de 1.35x (1.15 -> 1.55)
        mult[m10] = 1.15 + 0.40 * prog[m10]
        # Novembro: 1.65x em 01/11 subindo progressivamente até 2.10x em 30/11
        mult[m11] = 1.65 + (2.10 - 1.65) * prog[m11]
        # Dezembro (2020-2025): Natal alto para NATAL_FIM_DE_ANO, forte pós-BF para BLACK_FRIDAY_TECH
        if perfil == "NATAL_FIM_DE_ANO":
            mult[m12] = np.where(days[m12] <= 24, 2.25 + 0.45 * (days[m12] / 24.0), 1.35)
        else:
            mult[m12] = np.where(days[m12] <= 20, 1.85 - 0.20 * (days[m12] / 20.0), 1.45)

    return mult


def _load_inflation_map() -> dict[tuple[int, int], float]:
    infl_map: dict[tuple[int, int], float] = {}
    if INFLATION_CSV.exists():
        df_inf = pd.read_csv(INFLATION_CSV)
        for _, r in df_inf.iterrows():
            infl_map[(int(r["ano"]), int(r["mes"]))] = float(r["inflacao_mensal"])
    return infl_map


def update_api_sqlite_db(db_path: Path, is_local_format: bool = False) -> dict:
    """Atualiza e recalibra historico_vendas.db (ou fallback local) até 2026-11-30."""
    logger.info(f"Conectando ao banco: {db_path}")
    conn = sqlite3.connect(str(db_path), timeout=60.0)
    cur = conn.cursor()

    if is_local_format:
        prods_df = pd.read_sql_query(
            "SELECT id, title AS nome, category AS categoria, price AS preco_base FROM products ORDER BY id",
            conn,
        )
        # Estima volume_base pela mediana existente de cada produto e perfil pela categoria/título
        sales_all = pd.read_sql_query(
            "SELECT id, product_id AS produto_id, date AS data_venda, quantity_sold AS vendas, price_at_date AS preco FROM sales_history ORDER BY product_id, date",
            conn,
        )
        vol_meds = sales_all.groupby("produto_id")["vendas"].median().to_dict()
        prods_df["volume_base"] = prods_df["id"].map(lambda i: max(10, int(round(vol_meds.get(i, 40)))))

        def _infer_perfil(row):
            t = str(row["nome"]).lower()
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

        prods_df["perfil_sazonal"] = prods_df.apply(_infer_perfil, axis=1)

        existing_max_id = cur.execute("SELECT COALESCE(MAX(id), 0) FROM sales_history").fetchone()[0]
        cur.execute("DELETE FROM sales_history WHERE date(date) >= '2026-11-03' AND date(date) <= '2026-11-30'")
        conn.commit()
        existing_max_id = cur.execute("SELECT COALESCE(MAX(id), 0) FROM sales_history").fetchone()[0]

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
        next_id = int(existing_max_id) + 1
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        for _, prow in prods_df.iterrows():
            pid = int(prow["id"])
            vol_base = int(prow["volume_base"])
            base_price = float(last_prices.get(pid) or prow["preco_base"] or 100.0)
            for dt in new_dates:
                rows_to_insert.append((next_id, pid, dt.strftime("%Y-%m-%d"), vol_base, base_price, 100, "api_vendas", now_str))
                next_id += 1
        cur.executemany(
            "INSERT INTO sales_history (id, product_id, date, quantity_sold, price_at_date, available_quantity, platform, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows_to_insert,
        )
        conn.commit()

        sales_all = pd.read_sql_query(
            "SELECT id, product_id AS produto_id, substr(date, 1, 10) AS data_venda, quantity_sold AS vendas FROM sales_history ORDER BY product_id, date",
            conn,
        )
        sales_all["dt"] = pd.to_datetime(sales_all["data_venda"])
        sales_all["ano"] = sales_all["dt"].dt.year
        sales_all["mes"] = sales_all["dt"].dt.month
        sales_all["dia"] = sales_all["dt"].dt.day
        sales_all["dow"] = sales_all["dt"].dt.dayofweek.to_numpy()
        sales_all["dim"] = sales_all["dt"].dt.days_in_month.to_numpy()

        prod_meta = {int(r["id"]): (float(r["volume_base"]), str(r["perfil_sazonal"])) for _, r in prods_df.iterrows()}
        dow_weights = np.array([0.96, 0.94, 0.97, 1.01, 1.06, 1.09, 0.97], dtype=np.float64)
        new_list = []
        for pid, grp in sales_all.groupby("produto_id", sort=False):
            pid_int = int(pid)
            vol_base, perfil = prod_meta[pid_int]
            n = len(grp)
            raw_v = grp["vendas"].to_numpy(dtype=np.float64)
            med15 = pd.Series(raw_v).rolling(window=15, center=True, min_periods=1).median().to_numpy()
            is_spike = (raw_v >= np.maximum(25.0, med15 * 2.5)) & (raw_v > vol_base * 2.1)
            dates_str = grp["data_venda"].to_numpy()
            if pid_int == 124:
                is_spike |= (dates_str == "2026-10-29")
            season_mult = _build_seasonal_curve(pid_int, perfil, grp["mes"].to_numpy(np.int32), grp["dia"].to_numpy(np.int32), grp["dim"].to_numpy(np.int32))
            rng = np.random.default_rng(seed=20261201 + pid_int * 97)
            t_idx = np.arange(n, dtype=np.float64)
            wave = 0.055 * np.sin(2.0 * np.pi * t_idx / 11.0) + 0.035 * np.cos(2.0 * np.pi * t_idx / 23.0)
            organic_mult = np.clip(1.0 + wave + rng.uniform(-0.085, 0.085, size=n), 0.85, 1.15)
            cal = np.maximum(np.maximum(3, int(round(vol_base * 0.30))), np.round(vol_base * season_mult * dow_weights[grp["dow"].to_numpy(np.int32)] * organic_mult)).astype(np.int64)
            final_v = np.where(is_spike, np.round(raw_v).astype(np.int64), cal)
            if pid_int == 124:
                final_v[dates_str == "2026-10-29"] = 1133
            new_list.append(pd.DataFrame({"id": grp["id"].to_numpy(), "vendas": final_v}))
        up_df = pd.concat(new_list, ignore_index=True)
        cur.execute("DROP TABLE IF EXISTS _tmp_recal_local")
        cur.execute("CREATE TEMP TABLE _tmp_recal_local (id INTEGER PRIMARY KEY, vendas INTEGER NOT NULL)")
        cur.executemany("INSERT INTO _tmp_recal_local (id, vendas) VALUES (?, ?)", zip(up_df["id"].tolist(), up_df["vendas"].tolist()))
        cur.execute("UPDATE sales_history SET quantity_sold = (SELECT t.vendas FROM _tmp_recal_local t WHERE t.id = sales_history.id) WHERE EXISTS (SELECT 1 FROM _tmp_recal_local t WHERE t.id = sales_history.id)")
        conn.commit()
        stats = cur.execute("SELECT COUNT(*), MIN(date), MAX(date), SUM(CASE WHEN quantity_sold <= 1 THEN 1 ELSE 0 END) FROM sales_history").fetchone()
        conn.close()
        return {"local_db_path": str(db_path), "total_rows": stats[0], "min_date": stats[1], "max_date": stats[2], "remaining_low_errors": stats[3]}

    # 1. Carregar catálogo de produtos
    prods_df = pd.read_sql_query(
        "SELECT id, nome, categoria, preco_base, volume_base, perfil_sazonal, grupo_anomalia FROM produtos ORDER BY id",
        conn,
    )
    infl_map = _load_inflation_map()
    nov_infl = infl_map.get((2026, 11), 0.30)

    # 2. Garantir cobertura até 2026-11-30 para todos os 500 produtos (idempotente)
    existing_max_id = cur.execute("SELECT COALESCE(MAX(id), 0) FROM vendas_historicas").fetchone()[0]
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

        # Buscar último preço conhecido de cada produto (em 2026-11-02 ou último registro)
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
                # Preço suave em Novembro com leve promoção Black Friday (26-28/11) para itens Tech/Natal
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

    # 3. Carregar toda a série para recalibração sazonal vetorizada
    logger.info("Carregando série completa (2020-01-01 a 2026-11-30) para recalibração de ciclos Alta -> Queda...")
    sales_all = pd.read_sql_query(
        "SELECT id, produto_id, data_venda, vendas, ano, mes, dia FROM vendas_historicas ORDER BY produto_id, data_venda",
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

    # Multiplicador dia da semana (realista e leve)
    dow_weights = np.array([0.96, 0.94, 0.97, 1.01, 1.06, 1.09, 0.97], dtype=np.float64)

    new_vendas_list = []
    prod_groups = sales_all.groupby("produto_id", sort=False)

    logger.info("Calculando curvas sazonais + ruído orgânico (±8% a ±15%) + preservação de picos válidos...")
    for pid, grp in prod_groups:
        pid_int = int(pid)
        vol_base, perfil = prod_meta[pid_int]
        n = len(grp)

        raw_v = grp["vendas"].to_numpy(dtype=np.float64)
        months = grp["mes"].to_numpy(dtype=np.int32)
        days = grp["dia"].to_numpy(dtype=np.int32)
        years = grp["ano"].to_numpy(dtype=np.int32)
        dims = grp["dim"].to_numpy(dtype=np.int32)
        dows = grp["dow"].to_numpy(dtype=np.int32)
        dates_str = grp["data_venda"].to_numpy()

        # Identificar outliers superiores válidos existentes (compras grandes reais > 2.5x mediana local)
        med15 = pd.Series(raw_v).rolling(window=15, center=True, min_periods=1).median().to_numpy()
        is_valid_upper_spike = (raw_v >= np.maximum(25.0, med15 * 2.5)) & (raw_v > vol_base * 2.1)

        # Garantir explicitamente preservação do pico famoso do produto 124 em 29/10/2026 (1133 un)
        if pid_int == 124:
            mask_oct29 = dates_str == "2026-10-29"
            if np.any(mask_oct29):
                raw_v[mask_oct29] = 1133.0
                is_valid_upper_spike |= mask_oct29

        # Construir curva sazonal base do produto (Ciclos A, B, C, D)
        season_mult = _build_seasonal_curve(pid_int, perfil, months, days, dims)

        # Modulação anual leve e realista (para o gráfico de 5 ANOS mostrar evolução natural)
        rng = np.random.default_rng(seed=20261201 + pid_int * 97)
        year_jitter = {y: 1.0 + rng.uniform(-0.04, 0.04) for y in range(2020, 2027)}
        year_mult = np.array([year_jitter.get(int(y), 1.0) * (0.95 + 0.015 * (y - 2020)) for y in years], dtype=np.float64)

        # Variação diária orgânica realista (±8% a ±15%, nunca linha reta)
        t_idx = np.arange(n, dtype=np.float64)
        phase1 = _seed_float_from_key(pid_int, "ph1") * 2 * np.pi
        phase2 = _seed_float_from_key(pid_int, "ph2") * 2 * np.pi
        wave = (
            0.055 * np.sin(2.0 * np.pi * t_idx / 11.0 + phase1)
            + 0.035 * np.cos(2.0 * np.pi * t_idx / 23.0 + phase2)
        )
        daily_jitter = rng.uniform(-0.085, 0.085, size=n)
        organic_mult = np.clip(1.0 + wave + daily_jitter, 0.85, 1.15)

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

        # Piso seguro >= 3 unidades (removendo zeros de erro de captura)
        calibrated_int = np.maximum(np.maximum(3, int(round(vol_base * 0.30))), np.round(calibrated)).astype(np.int64)

        # Preservar 100% dos outliers superiores válidos originais
        final_v = np.where(is_valid_upper_spike, np.round(raw_v).astype(np.int64), calibrated_int)

        # Ajuste final explícito no produto 124 (Garantia estrita de pico 1133 em 29/10/2026)
        if pid_int == 124:
            mask_oct29 = dates_str == "2026-10-29"
            final_v[mask_oct29] = 1133

        new_vendas_list.append(pd.DataFrame({"id": grp["id"].to_numpy(), "vendas": final_v}))

    updated_df = pd.concat(new_vendas_list, ignore_index=True)

    # 4. Aplicar atualização em lote no SQLite de origem (transação única via temp table)
    logger.info(f"Gravando {len(updated_df):,} linhas recalibradas em {db_path}...")
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA synchronous = NORMAL")
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
    conn.close()

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


def sync_to_local_db() -> dict:
    """Sincroniza historico_vendas.db -> data/trendcommerce_dev.db usando VendasApiClient."""
    logger.info("Sincronizando historico_vendas.db -> data/trendcommerce_dev.db via VendasApiClient...")
    engine = get_engine()
    Base.metadata.create_all(engine)
    session = get_session(engine)
    try:
        # Limpar eventuais registros sintéticos acima da faixa oficial para garantir espelho fiel
        res = vendas_client.sync_to_trendecommerce(session, min_date="2020-01-01")
        if not res.get("success"):
            raise RuntimeError(f"Falha na sincronização: {res.get('error')}")

        # Verificar datas finais no banco local SQLite
        conn = sqlite3.connect(str(LOCAL_DB_PATH), timeout=30.0)
        local_stats = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date), SUM(CASE WHEN quantity_sold <= 1 THEN 1 ELSE 0 END) FROM sales_history"
        ).fetchone()
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
    finally:
        session.close()


def main():
    api_db = API_DB_PRIMARY if API_DB_PRIMARY.exists() else vendas_client.get_database_path()
    if api_db and api_db.exists():
        res_api = update_api_sqlite_db(api_db, is_local_format=False)
        res_sync = sync_to_local_db()
        logger.info(f"Concluído com sucesso: API={res_api} | LOCAL={res_sync}")
    elif LOCAL_DB_PATH.exists():
        res_local = update_api_sqlite_db(LOCAL_DB_PATH, is_local_format=True)
        logger.info(f"Fallback local concluído com sucesso: LOCAL={res_local}")
    else:
        raise FileNotFoundError(
            f"Nenhum banco encontrado em {API_DB_PRIMARY} nem em {LOCAL_DB_PATH}."
        )


if __name__ == "__main__":
    main()
