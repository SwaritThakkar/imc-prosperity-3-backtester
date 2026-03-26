"""
================================================================================
IMC PROSPERITY — TOMATOES ANALYTICS DASHBOARD
================================================================================
Author  : Quantitative Developer
Purpose : Multi-panel matplotlib dashboard for TOMATOES product from Round 0
          IMC Prosperity trading challenge price and trade CSV data.

Usage   : python prosperity_tomatoes_dashboard.py

Configuration constants (top of script) allow easy product / indicator changes.

Expects the following files in the same directory as this script:
    prices_round_0_day_-1.csv
    prices_round_0_day_-2.csv
    trades_round_0_day_-1.csv
    trades_round_0_day_-2.csv
================================================================================
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.widgets import CheckButtons

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION  ←  change these to adapt the script to another product/setting
# ──────────────────────────────────────────────────────────────────────────────

PRODUCT          = "TOMATOES"   # product name as it appears in the CSV
EMA_PERIOD       = 14           # period for exponential moving average
BB_PERIOD        = 20           # Bollinger Band rolling window
BB_STD           = 2            # number of standard deviations for Bollinger Bands
VOL_WINDOW       = 20           # rolling window for volatility (std of mid_price)
DAY_OFFSET       = 1_000_000    # timestamp offset added to day -1 so timelines don't overlap

# ── Visibility Toggles ────────────────────────────────────────────────────────
SHOW_L3          = False        # show/hide L3 bid/ask price lines
SHOW_L2          = True         # show/hide L2 bid/ask price lines
SHOW_TRADES      = True         # show/hide trade scatter overlay
SHOW_BB_FILL     = True         # show/hide Bollinger Band fill_between
SHOW_ORDERBOOK   = True         # show/hide Panel 2 (order book volumes + imbalance)
SHOW_VOLATILITY  = True         # show/hide Panel 3 (volatility + spread)
SHOW_VOLUME      = True         # show/hide Panel 4 (total volume)

# File names — adjust paths here if CSVs live elsewhere
PRICE_FILES = [
    "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/prices_round_0_day_-2.csv",   # day -2 comes first in chronological order
    "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/prices_round_0_day_-1.csv",
]
TRADE_FILES = [
    "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/trades_round_0_day_-2.csv",
    "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/trades_round_0_day_-1.csv",
]

# ──────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE  — keeps the whole dashboard visually consistent
# ──────────────────────────────────────────────────────────────────────────────

CLR = {
    "mid"        : "#FFFFFF",
    "ema"        : "#FFD700",     # gold
    "bb_mean"    : "#00BFFF",     # deep sky blue
    "bb_upper"   : "#FF6347",     # tomato red  (fitting for TOMATOES)
    "bb_lower"   : "#FF6347",
    "bb_fill"    : "#FF634720",   # translucent fill between bands
    "best_bid"   : "#00FF7F",     # spring green
    "best_ask"   : "#FF4500",     # orange-red
    "l2_bid"     : "#00FF7F50",   # faint
    "l2_ask"     : "#FF450050",
    "l3_bid"     : "#00FF7F25",
    "l3_ask"     : "#FF450025",
    "buy_trade"  : "#39FF14",     # neon green  buy
    "sell_trade" : "#FF073A",     # neon red    sell
    "neutral_trade": "#AAAAAA",
    "bid_vol"    : "#00FF7F",
    "ask_vol"    : "#FF4500",
    "imbalance"  : "#FFD700",
    "volatility" : "#BF5FFF",     # purple
    "spread"     : "#FF8C00",     # dark orange
    "total_vol"  : "#00BFFF",
    "background" : "#0D0D0D",
    "grid"       : "#2A2A2A",
    "text"       : "#E0E0E0",
    "day_line"   : "#444455",
}


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _sniff_and_read(path: str) -> pd.DataFrame:
    """
    Robustly read a CSV whose separator and column names may vary.

    IMC Prosperity CSVs sometimes use semicolons instead of commas, and
    column names may have extra whitespace or differ in casing.  This
    function:
        1. Sniffs the first raw line to decide between ',' and ';'.
        2. Reads with the detected separator.
        3. Strips whitespace from all column names.
        4. Prints the detected columns so the user can debug mismatches.

    Parameters
    ----------
    path : str
        Absolute or relative path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Raw DataFrame with cleaned column names.
    """
    # ── Step 1: peek at the first line to detect separator ───────────────────
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        first_line = fh.readline()

    sep = ";" if first_line.count(";") > first_line.count(",") else ","

    # ── Step 2: read with detected separator ─────────────────────────────────
    df = pd.read_csv(path, sep=sep)

    # ── Step 3: normalise column names ───────────────────────────────────────
    df.columns = df.columns.str.strip().str.lower()

    print(f"  [sniff] sep='{sep}'  columns: {list(df.columns)}")
    return df


def _rename_columns(df: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    """
    Rename columns using a dict of {canonical_name: [possible_aliases]}.

    Allows the rest of the code to always reference canonical names
    (e.g. 'timestamp', 'mid_price') regardless of what the CSV called them.

    Parameters
    ----------
    df      : pd.DataFrame  — DataFrame with normalised (lowercased) column names.
    mapping : dict          — {target_name: [alias1, alias2, ...]}

    Returns
    -------
    pd.DataFrame with columns renamed where aliases were found.
    """
    rename_map = {}
    for canonical, aliases in mapping.items():
        if canonical in df.columns:
            continue    # already correct, no rename needed
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical
                break   # first match wins
    if rename_map:
        print(f"  [rename] applying: {rename_map}")
        df = df.rename(columns=rename_map)
    return df


# Canonical column names and their known aliases in Prosperity CSVs
_PRICE_COL_ALIASES: dict[str, list[str]] = {
    "timestamp"   : ["time", "ts", "timestep"],
    "product"     : ["symbol", "instrument", "prod"],
    "mid_price"   : ["midprice", "mid", "midpoint", "mid_px"],
    "bid_price_1" : ["bidprice1", "bid1", "best_bid", "bid_px_1"],
    "ask_price_1" : ["askprice1", "ask1", "best_ask", "ask_px_1"],
    "bid_volume_1": ["bidvolume1", "bid_vol_1", "bidvol1"],
    "ask_volume_1": ["askvolume1", "ask_vol_1", "askvol1"],
}

_TRADE_COL_ALIASES: dict[str, list[str]] = {
    "timestamp": ["time", "ts", "timestep"],
    "symbol"   : ["product", "instrument", "prod"],
    "price"    : ["trade_price", "px", "tradeprice"],
    "quantity" : ["qty", "size", "volume", "amount"],
    "buyer"    : ["buy_id", "buyer_id"],
    "seller"   : ["sell_id", "seller_id"],
}


def load_prices(filepaths: list[str]) -> list[pd.DataFrame]:
    """
    Load price CSV files from disk.

    Each file is loaded into a separate DataFrame.  The loader:
      - Auto-detects comma vs semicolon separator.
      - Normalises column names to lowercase.
      - Renames known aliases to canonical names.
      - Coerces numeric columns safely.

    Parameters
    ----------
    filepaths : list of str
        Ordered list of price CSV file paths.  filepaths[0] = earliest day.

    Returns
    -------
    list of pd.DataFrame
        One DataFrame per file, with canonical column names.
    """
    frames = []
    for path in filepaths:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"[load_prices] Cannot find price file: '{path}'\n"
                f"  → Make sure CSV files are in the same directory as this script."
            )
        print(f"[load_prices] Reading '{path}' …")
        df = _sniff_and_read(path)
        df = _rename_columns(df, _PRICE_COL_ALIASES)

        # Verify the essential column exists after renaming
        if "timestamp" not in df.columns:
            raise KeyError(
                f"[load_prices] Could not find a 'timestamp' column in '{path}'.\n"
                f"  Detected columns: {list(df.columns)}\n"
                f"  → Add an alias to _PRICE_COL_ALIASES if your CSV uses a different name."
            )

        # Safe numeric coercion — non-numeric values become NaN, not crashes
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        if "mid_price" in df.columns:
            df["mid_price"] = pd.to_numeric(df["mid_price"], errors="coerce")

        frames.append(df)
        print(f"  → {len(df):,} rows loaded")
    return frames


def load_trades(filepaths: list[str]) -> list[pd.DataFrame]:
    """
    Load trade CSV files from disk.

    Trade files record market trades (buyer / seller pairs).  The loader
    applies the same auto-detection and alias-renaming as load_prices.

    Parameters
    ----------
    filepaths : list of str
        Ordered list of trade CSV file paths, same ordering as price files.

    Returns
    -------
    list of pd.DataFrame
        One DataFrame per file (empty DataFrame if file is missing).
    """
    frames = []
    for path in filepaths:
        if not os.path.exists(path):
            print(f"[load_trades] WARNING: trade file not found: '{path}' — skipping")
            frames.append(pd.DataFrame())
            continue
        print(f"[load_trades] Reading '{path}' …")
        df = _sniff_and_read(path)
        df = _rename_columns(df, _TRADE_COL_ALIASES)

        if "timestamp" not in df.columns:
            print(
                f"  WARNING: no 'timestamp' column found in '{path}' — "
                f"columns are {list(df.columns)} — skipping this trade file."
            )
            frames.append(pd.DataFrame())
            continue

        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        if "price"    in df.columns:
            df["price"]    = pd.to_numeric(df["price"],    errors="coerce")
        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

        frames.append(df)
        print(f"  → {len(df):,} rows loaded")
    return frames


# ══════════════════════════════════════════════════════════════════════════════
#  MERGING FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def merge_days(
    price_frames : list[pd.DataFrame],
    trade_frames : list[pd.DataFrame],
    product      : str       = PRODUCT,
    day_offset   : int       = DAY_OFFSET,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Merge multiple day DataFrames into a single continuous timeline.

    Strategy
    --------
    * Day index 0 (earliest) keeps its timestamps as-is.
    * Each subsequent day has (day_index × day_offset) added to its timestamps.
      This prevents timestamp collisions between days.
    * Only rows matching ``product`` (or ``symbol`` for trades) are kept.
    * The merged result is sorted by timestamp.

    Parameters
    ----------
    price_frames : list of pd.DataFrame
        Raw price DataFrames — one per day, in chronological order.
    trade_frames : list of pd.DataFrame
        Raw trade DataFrames — one per day, same ordering.
    product      : str
        Product name to filter on (e.g. "TOMATOES").
    day_offset   : int
        Integer added to timestamps per day shift to avoid overlap.

    Returns
    -------
    prices_df : pd.DataFrame
        Merged, filtered, sorted price data.
    trades_df : pd.DataFrame
        Merged, filtered, sorted trade data.
    """

    # ── Prices ────────────────────────────────────────────────────────────────
    price_parts = []
    for day_idx, df in enumerate(price_frames):
        if df.empty:
            continue
        chunk = df.copy()
        # Apply time offset so day N doesn't collide with day N-1
        chunk["timestamp"] = chunk["timestamp"] + day_idx * day_offset
        # Record which source day this row came from (useful for debugging)
        chunk["day"] = day_idx
        # Filter to the target product
        prod_col = "product" if "product" in chunk.columns else "symbol"
        chunk = chunk[chunk[prod_col].astype(str).str.strip().str.upper() == product.upper()]
        price_parts.append(chunk)

    if not price_parts:
        raise ValueError(
            f"[merge_days] No price rows found for product='{product}'. "
            f"Check product name and CSV contents."
        )

    prices_df = (
        pd.concat(price_parts, ignore_index=True)
          .sort_values("timestamp")
          .reset_index(drop=True)
    )
    print(f"[merge_days] Merged prices — {len(prices_df):,} rows for '{product}'")

    # ── Trades ────────────────────────────────────────────────────────────────
    trade_parts = []
    for day_idx, df in enumerate(trade_frames):
        if df.empty:
            continue
        chunk = df.copy()
        chunk["timestamp"] = chunk["timestamp"] + day_idx * day_offset
        chunk["day"]       = day_idx
        # Trade files use 'symbol' instead of 'product'
        sym_col = "symbol" if "symbol" in chunk.columns else "product"
        chunk = chunk[chunk[sym_col].astype(str).str.strip().str.upper() == product.upper()]
        trade_parts.append(chunk)

    if trade_parts:
        trades_df = (
            pd.concat(trade_parts, ignore_index=True)
              .sort_values("timestamp")
              .reset_index(drop=True)
        )
        print(f"[merge_days] Merged trades — {len(trades_df):,} rows for '{product}'")
    else:
        print(f"[merge_days] No trade data found for '{product}' — trade overlay disabled")
        trades_df = pd.DataFrame()

    return prices_df, trades_df


# ══════════════════════════════════════════════════════════════════════════════
#  INDICATORS FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical indicators required by the dashboard.

    Indicators added as new columns
    --------------------------------
    ema                  Exponential moving average of mid_price (EMA_PERIOD)
    bb_mean              Bollinger Band centre line (simple MA, BB_PERIOD)
    bb_upper             Bollinger Band upper band  (bb_mean + BB_STD × rolling σ)
    bb_lower             Bollinger Band lower band  (bb_mean − BB_STD × rolling σ)
    spread               ask_price_1 − bid_price_1
    volatility           Rolling standard deviation of mid_price (VOL_WINDOW)
    total_volume         bid_volume_1 + ask_volume_1
    imbalance            (bid_vol_1 − ask_vol_1) / (bid_vol_1 + ask_vol_1)

    Parameters
    ----------
    df : pd.DataFrame
        Merged, filtered price DataFrame (output of merge_days).

    Returns
    -------
    pd.DataFrame
        Same DataFrame with new indicator columns appended.
    """

    # Work on a copy to avoid mutating the input
    out = df.copy()

    # ── Coerce numeric columns that might contain NaN / strings ───────────────
    numeric_cols = [
        "mid_price",
        "bid_price_1", "bid_volume_1",
        "bid_price_2", "bid_volume_2",
        "bid_price_3", "bid_volume_3",
        "ask_price_1", "ask_volume_1",
        "ask_price_2", "ask_volume_2",
        "ask_price_3", "ask_volume_3",
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # ── EMA of mid_price ──────────────────────────────────────────────────────
    # pandas ewm uses span= which approximates the traditional N-period EMA
    out["ema"] = out["mid_price"].ewm(span=EMA_PERIOD, adjust=False).mean()

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    bb_roll          = out["mid_price"].rolling(window=BB_PERIOD)
    out["bb_mean"]   = bb_roll.mean()
    bb_std           = bb_roll.std()
    out["bb_upper"]  = out["bb_mean"] + BB_STD * bb_std
    out["bb_lower"]  = out["bb_mean"] - BB_STD * bb_std

    # ── Spread (best ask − best bid) ──────────────────────────────────────────
    if "ask_price_1" in out.columns and "bid_price_1" in out.columns:
        out["spread"] = out["ask_price_1"] - out["bid_price_1"]
    else:
        out["spread"] = np.nan

    # ── Rolling Volatility (std of mid_price) ─────────────────────────────────
    out["volatility"] = out["mid_price"].rolling(window=VOL_WINDOW).std()

    # ── Total Volume at level 1 ───────────────────────────────────────────────
    bv1 = out.get("bid_volume_1", pd.Series(np.nan, index=out.index))
    av1 = out.get("ask_volume_1", pd.Series(np.nan, index=out.index))
    out["total_volume"] = bv1 + av1

    # ── Order Book Imbalance ──────────────────────────────────────────────────
    # Ranges from −1 (fully ask-sided) to +1 (fully bid-sided)
    denom = (bv1 + av1).replace(0, np.nan)   # avoid divide-by-zero
    out["imbalance"] = (bv1 - av1) / denom

    print(f"[compute_indicators] Done — shape {out.shape}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — safe column getter
# ══════════════════════════════════════════════════════════════════════════════

def _col(df: pd.DataFrame, name: str) -> pd.Series | None:
    """
    Return df[name] if the column exists and is not all-NaN, else None.
    Suppresses KeyError gracefully so plots simply skip missing data.
    """
    if name in df.columns and not df[name].isna().all():
        return df[name]
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  PLOT DASHBOARD FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def plot_dashboard(
    prices  : pd.DataFrame,
    trades  : pd.DataFrame,
    product : str = PRODUCT,
) -> None:
    """
    Render a 4-panel matplotlib dashboard for the given product data.

    Panel layout (shared x-axis)
    ────────────────────────────
    [1] PRICE        mid_price, EMA, Bollinger Bands, bid/ask levels, trade dots
    [2] ORDER BOOK   bid/ask volumes at L1, order-book imbalance
    [3] VOLATILITY   rolling σ of mid_price, bid-ask spread
    [4] VOLUME       total volume, bid_volume_1, ask_volume_1

    Parameters
    ----------
    prices  : pd.DataFrame
        Enriched price data (output of compute_indicators).
    trades  : pd.DataFrame
        Filtered trade data (may be empty).
    product : str
        Product name — used only in the figure title.
    """

    ts = prices["timestamp"]       # common x-axis values

    # ── Dark-theme global style ───────────────────────────────────────────────
    plt.rcParams.update({
        "figure.facecolor"  : CLR["background"],
        "axes.facecolor"    : CLR["background"],
        "axes.edgecolor"    : CLR["grid"],
        "axes.labelcolor"   : CLR["text"],
        "axes.titlecolor"   : CLR["text"],
        "xtick.color"       : CLR["text"],
        "ytick.color"       : CLR["text"],
        "text.color"        : CLR["text"],
        "grid.color"        : CLR["grid"],
        "grid.linestyle"    : "--",
        "grid.linewidth"    : 0.5,
        "legend.facecolor"  : "#1A1A1A",
        "legend.edgecolor"  : CLR["grid"],
        "legend.labelcolor" : CLR["text"],
        "font.size"         : 9,
    })

    # ── Figure and GridSpec ───────────────────────────────────────────────────
    fig = plt.figure(figsize=(22, 18), dpi=110)
    fig.suptitle(
        f"IMC PROSPERITY  ·  {product}  ·  Round 0  ·  Day −2 → Day −1",
        fontsize=16, fontweight="bold", color=CLR["text"], y=0.99,
    )

    # Ratio of subplot heights: price panel tallest, others equal
    gs = gridspec.GridSpec(
        4, 1,
        figure=fig,
        height_ratios=[1,0, 0, 0],
        hspace=0.08,
    )

    ax1 = fig.add_subplot(gs[0])
    # ax2 = fig.add_subplot(gs[1], sharex=ax1)
    # ax3 = fig.add_subplot(gs[2], sharex=ax1)
    # ax4 = fig.add_subplot(gs[3], sharex=ax1)

    # ── Utility: apply standard grid/spine style to an axis ──────────────────
    def _style_ax(ax, ylabel, title):
        ax.set_ylabel(ylabel, fontsize=9, labelpad=6)
        ax.set_title(title, fontsize=10, loc="left", pad=4, fontweight="bold")
        ax.grid(True, which="both", alpha=0.4)
        ax.tick_params(axis="both", which="both", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(CLR["grid"])
        # Hide x-tick labels for all but the bottom panel
        # if ax is not ax4:
        #     plt.setp(ax.get_xticklabels(), visible=False)

    # ─────────────────────────────────────────────────────────────────────────
    #  PANEL 1 — PRICE
    # ─────────────────────────────────────────────────────────────────────────

    lines = {}

    if SHOW_L3:
        for side, col, clr in [
            ("bid", "bid_price_3", CLR["l3_bid"]),
            ("ask", "ask_price_3", CLR["l3_ask"]),
        ]:
            s = _col(prices, col)
            if s is not None:
                l, = ax1.plot(ts, s, color=clr, linewidth=0.6, alpha=0.4)
                lines[f"L3 {side}"] = l


    if SHOW_L2:
        for side, col, clr in [
            ("bid", "bid_price_2", CLR["l2_bid"]),
            ("ask", "ask_price_2", CLR["l2_ask"]),
        ]:
            s = _col(prices, col)
            if s is not None:
                l, = ax1.plot(ts, s, color=clr, linewidth=0.8, alpha=0.45)
                lines[f"L2 {side}"] = l


    s_bid = _col(prices, "bid_price_1")
    s_ask = _col(prices, "ask_price_1")

    if s_bid is not None:
        l, = ax1.plot(ts, s_bid, color=CLR["best_bid"])
        lines["Best Bid"] = l

    if s_ask is not None:
        l, = ax1.plot(ts, s_ask, color=CLR["best_ask"])
        lines["Best Ask"] = l


    bb_u = _col(prices, "bb_upper")
    bb_l = _col(prices, "bb_lower")

    if bb_u is not None and bb_l is not None:

        if SHOW_BB_FILL:
            bb_fill = ax1.fill_between(
                ts, bb_l, bb_u,
                color=CLR["bb_fill"]
            )
            lines["BB Fill"] = bb_fill

        l1, = ax1.plot(ts, bb_u, color=CLR["bb_upper"])
        l2, = ax1.plot(ts, bb_l, color=CLR["bb_lower"])

        lines["BB Upper"] = l1
        lines["BB Lower"] = l2


    s_bb_mean = _col(prices, "bb_mean")
    if s_bb_mean is not None:
        l, = ax1.plot(ts, s_bb_mean, color=CLR["bb_mean"])
        lines["BB Mean"] = l


    s_ema = _col(prices, "ema")
    if s_ema is not None:
        l, = ax1.plot(ts, s_ema, color=CLR["ema"])
        lines["EMA"] = l


    s_mid = _col(prices, "mid_price")
    if s_mid is not None:
        l, = ax1.plot(ts, s_mid, color=CLR["mid"])
        lines["Mid"] = l


    if SHOW_TRADES and not trades.empty:

        trades_copy = trades.copy()

        def _classify_trade(row):
            buyer  = str(row.get("buyer",  "")).strip().upper()
            seller = str(row.get("seller", "")).strip().upper()
            if buyer == "SUBMISSION":
                return "sell"
            if seller == "SUBMISSION":
                return "buy"
            return "neutral"

        trades_copy["direction"] = trades_copy.apply(
            _classify_trade, axis=1
        )

        scat = ax1.scatter(
            trades_copy["timestamp"],
            trades_copy["price"],
            c=CLR["neutral_trade"],
            s=10,
        )

        lines["Trades"] = scat

    _style_ax(ax1, "Price", "① PRICE  ·  Mid · EMA · Bollinger · Bid/Ask Levels · Trades")

    # Compact legend (outside so it doesn't cover data)
    ax1.legend(
        loc="upper left", fontsize=7.5, ncol=4,
        framealpha=0.7, borderpad=0.5, handlelength=1.5,
    )
    
    rax = plt.axes([0.01, 0.4, 0.15, 0.3])

    labels = list(lines.keys())
    visibility = [True] * len(labels)

    check = CheckButtons(rax, labels, visibility)


    def func(label):

        artist = lines[label]

        vis = not artist.get_visible()

        artist.set_visible(vis)

        plt.draw()


    check.on_clicked(func)

    # ─────────────────────────────────────────────────────────────────────────
    #  PANEL 2 — ORDER BOOK VOLUMES + IMBALANCE
    # ─────────────────────────────────────────────────────────────────────────

    # Secondary y-axis for imbalance (different scale: −1 to +1)
    # ax2b = ax2.twinx()
    # ax2b.set_facecolor(CLR["background"])

    # if SHOW_ORDERBOOK:
    #     s_bv1 = _col(prices, "bid_volume_1")
    #     s_av1 = _col(prices, "ask_volume_1")
    #     s_imb = _col(prices, "imbalance")

    #     if s_bv1 is not None:
    #         ax2.plot(ts, s_bv1, color=CLR["bid_vol"], linewidth=1.2,
    #                  label="Bid Vol L1")
    #     if s_av1 is not None:
    #         ax2.plot(ts, s_av1, color=CLR["ask_vol"], linewidth=1.2,
    #                  label="Ask Vol L1")

    #     if s_imb is not None:
    #         ax2b.plot(ts, s_imb, color=CLR["imbalance"], linewidth=0.9,
    #                   linestyle=":", alpha=0.8, label="OB Imbalance")
    #         ax2b.axhline(0, color=CLR["grid"], linewidth=0.6)
    #         ax2b.set_ylim(-1.1, 1.1)
    #         ax2b.set_ylabel("Imbalance", fontsize=8, color=CLR["imbalance"])
    #         ax2b.tick_params(axis="y", colors=CLR["imbalance"], labelsize=7)

    # _style_ax(ax2, "Volume", "② ORDER BOOK  ·  Bid / Ask Volumes at L1  ·  OB Imbalance (dotted)")

    # # Combine legends from both y-axes
    # handles1, labels1 = ax2.get_legend_handles_labels()
    # handles2, labels2 = ax2b.get_legend_handles_labels()
    # ax2.legend(handles1 + handles2, labels1 + labels2,
    #            loc="upper left", fontsize=7.5, ncol=3, framealpha=0.7)

    # # ─────────────────────────────────────────────────────────────────────────
    # #  PANEL 3 — VOLATILITY + SPREAD
    # # ─────────────────────────────────────────────────────────────────────────

    # ax3b = ax3.twinx()
    # ax3b.set_facecolor(CLR["background"])

    # if SHOW_VOLATILITY:
    #     s_vol    = _col(prices, "volatility")
    #     s_spread = _col(prices, "spread")

    #     if s_vol is not None:
    #         ax3.plot(ts, s_vol, color=CLR["volatility"], linewidth=1.2,
    #                  label=f"Volatility (σ, w={VOL_WINDOW})")
    #         ax3.fill_between(ts, 0, s_vol.fillna(0),
    #                          color=CLR["volatility"], alpha=0.12)

    #     if s_spread is not None:
    #         ax3b.plot(ts, s_spread, color=CLR["spread"], linewidth=1.0,
    #                   linestyle="--", alpha=0.85, label="Spread (Ask−Bid)")
    #         ax3b.set_ylabel("Spread", fontsize=8, color=CLR["spread"])
    #         ax3b.tick_params(axis="y", colors=CLR["spread"], labelsize=7)

    # _style_ax(ax3, "Std Dev", "③ VOLATILITY  ·  Rolling σ of Mid Price  ·  Bid-Ask Spread (dashed)")

    # handles3, labels3 = ax3.get_legend_handles_labels()
    # handles4, labels4 = ax3b.get_legend_handles_labels()
    # ax3.legend(handles3 + handles4, labels3 + labels4,
    #            loc="upper left", fontsize=7.5, ncol=2, framealpha=0.7)

    # # ─────────────────────────────────────────────────────────────────────────
    # #  PANEL 4 — TOTAL VOLUME
    # # ─────────────────────────────────────────────────────────────────────────

    # if SHOW_VOLUME:
    #     s_tv  = _col(prices, "total_volume")
    #     s_bv1 = _col(prices, "bid_volume_1")
    #     s_av1 = _col(prices, "ask_volume_1")

    #     if s_tv is not None:
    #         ax4.plot(ts, s_tv, color=CLR["total_vol"], linewidth=1.3,
    #                  label="Total Volume (L1)")
    #         ax4.fill_between(ts, 0, s_tv.fillna(0),
    #                          color=CLR["total_vol"], alpha=0.10)

    #     if s_bv1 is not None:
    #         ax4.plot(ts, s_bv1, color=CLR["bid_vol"], linewidth=0.9,
    #                  linestyle="--", alpha=0.75, label="Bid Vol L1")

    #     if s_av1 is not None:
    #         ax4.plot(ts, s_av1, color=CLR["ask_vol"], linewidth=0.9,
    #                  linestyle="-.", alpha=0.75, label="Ask Vol L1")

    # _style_ax(ax4, "Volume", "④ VOLUME  ·  Total · Bid L1 · Ask L1")
    # ax4.set_xlabel("Timestamp", fontsize=9, labelpad=6)
    # plt.setp(ax4.get_xticklabels(), visible=True)

    # ax4.legend(loc="upper left", fontsize=7.5, ncol=3, framealpha=0.7)

    # # ── Day boundary vertical lines ───────────────────────────────────────────
    # # If data spans multiple days, draw a subtle vertical line where day changes
    # if "day" in prices.columns:
    #     day_changes = prices[prices["day"] != prices["day"].shift(1)]
    #     day_changes = day_changes[day_changes["day"] > 0]     # skip first row
    #     for _, row in day_changes.iterrows():
    #         t_change = row["timestamp"]
    #         for ax in [ax1, ax2, ax3, ax4]:
    #             ax.axvline(t_change, color=CLR["day_line"],
    #                        linewidth=1.0, linestyle=":", zorder=0)
    #         # Label only on the top panel
    #         ax1.text(
    #             t_change, ax1.get_ylim()[1],
    #             f"  Day {int(row['day'])+1}", fontsize=7,
    #             color=CLR["day_line"], va="top", ha="left",
    #         )

    # ── Final layout ──────────────────────────────────────────────────────────
    #fig.tight_layout(rect=[0, 0, 1, 0.99])

    output_path = f"prosperity_{product.lower()}_dashboard.png"
    fig.savefig(output_path, dpi=120, bbox_inches="tight",
                facecolor=CLR["background"])
    print(f"\n[plot_dashboard] Saved → '{output_path}'")

    plt.show()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Orchestrate the full pipeline:
        1. Load price CSV files for each day.
        2. Load trade CSV files for each day.
        3. Merge days into a single timeline with non-overlapping timestamps.
        4. Filter to TOMATOES (or PRODUCT constant).
        5. Compute technical indicators.
        6. Render and save the 4-panel dashboard.
    """

    print("=" * 70)
    print(f"  IMC PROSPERITY — {PRODUCT} ANALYTICS DASHBOARD")
    print("=" * 70)

    # ── Step 1: Load raw data ─────────────────────────────────────────────────
    price_frames = load_prices(PRICE_FILES)
    trade_frames = load_trades(TRADE_FILES)

    # ── Step 2 & 3: Merge days into one timeline ──────────────────────────────
    prices_merged, trades_merged = merge_days(
        price_frames, trade_frames,
        product=PRODUCT, day_offset=DAY_OFFSET,
    )

    # ── Step 4: Compute indicators ────────────────────────────────────────────
    prices_enriched = compute_indicators(prices_merged)

    # ── Step 5: Render dashboard ──────────────────────────────────────────────
    plot_dashboard(prices_enriched, trades_merged, product=PRODUCT)

    print("\n[main] ✓ Done.")


if __name__ == "__main__":
    main()