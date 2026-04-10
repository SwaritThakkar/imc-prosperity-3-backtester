import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import RadioButtons
from pathlib import Path

BASE = Path(__file__).resolve().parent
PRICES_FILE = "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/prices_round_0_day_-1.csv"
TRADES_FILE = "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/prosperity3bt/resources/round0/trades_round_0_day_-1.csv"

prices = pd.read_csv(PRICES_FILE, sep=";")
trades = pd.read_csv(TRADES_FILE, sep=";")


# -----------------------------
# Accuracy analysis for rules
# -----------------------------
def compute_rule_accuracies(prices_df: pd.DataFrame):
    """
    Statement 1:
    if (cur_best_bid > last_best_bid and askvol1 != bidvol1) then next_best_bid < cur_best_bid

    Statement 2:
    reversed for asks:
    if (cur_best_ask < last_best_ask and askvol1 != bidvol1) then next_best_ask > cur_best_ask
    """
    results = {}

    for product in sorted(prices_df["product"].dropna().unique()):
        p = prices_df[prices_df["product"] == product].sort_values("timestamp").copy()

        p["last_best_bid"] = p["bid_price_1"].shift(1)
        p["next_best_bid"] = p["bid_price_1"].shift(-1)

        p["last_best_ask"] = p["ask_price_1"].shift(1)
        p["next_best_ask"] = p["ask_price_1"].shift(-1)

        # Statement 1 trigger and success
        bid_trigger = (
            (p["bid_price_1"] > p["last_best_bid"]) &
            (p["ask_volume_1"] != p["bid_volume_1"])
        )
        bid_success = bid_trigger & (p["next_best_bid"] < p["bid_price_1"])

        bid_trigger_count = int(bid_trigger.sum())
        bid_success_count = int(bid_success.sum())
        bid_accuracy = (
            bid_success_count / bid_trigger_count
            if bid_trigger_count > 0 else float("nan")
        )

        # Statement 2 trigger and success
        ask_trigger = (
            (p["ask_price_1"] < p["last_best_ask"]) &
            (p["ask_volume_1"] != p["bid_volume_1"])
        )
        ask_success = ask_trigger & (p["next_best_ask"] > p["ask_price_1"])

        ask_trigger_count = int(ask_trigger.sum())
        ask_success_count = int(ask_success.sum())
        ask_accuracy = (
            ask_success_count / ask_trigger_count
            if ask_trigger_count > 0 else float("nan")
        )

        results[product] = {
            "bid_trigger_count": bid_trigger_count,
            "bid_success_count": bid_success_count,
            "bid_accuracy": bid_accuracy,
            "ask_trigger_count": ask_trigger_count,
            "ask_success_count": ask_success_count,
            "ask_accuracy": ask_accuracy,
        }

    return results


rule_results = compute_rule_accuracies(prices)
for product, r in rule_results.items():
    print(
        f"{product} | "
        f"Stmt1 bid-accuracy: {r['bid_accuracy']:.4f} "
        f"({r['bid_success_count']}/{r['bid_trigger_count']}) | "
        f"Stmt2 ask-accuracy: {r['ask_accuracy']:.4f} "
        f"({r['ask_success_count']}/{r['ask_trigger_count']})"
    )

    
products = sorted(prices["product"].dropna().unique().tolist())
default_product = "TOMATOES" if "TOMATOES" in products else products[0]

trade_symbol_col = "symbol" if "symbol" in trades.columns else "product"

fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(3, 2, width_ratios=[20, 3], height_ratios=[3, 2, 1])

ax_price = fig.add_subplot(gs[0, 0])
ax_vol = fig.add_subplot(gs[1, 0], sharex=ax_price)
ax_imb = fig.add_subplot(gs[2, 0], sharex=ax_price)
ax_radio = fig.add_subplot(gs[:, 1])

plt.subplots_adjust(hspace=0.18, right=0.88)

radio = RadioButtons(ax_radio, products, active=products.index(default_product))
ax_radio.set_title("Product")

visibility_state = {product: {} for product in products}
legend_artist_map = {}
current_product = default_product


def clear_axes():
    ax_price.cla()
    ax_vol.cla()
    ax_imb.cla()


def add_interactive_legend(ax, product):
    global legend_artist_map

    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return

    legend = ax.legend(loc="upper left", ncol=4 if ax is ax_price else 3, fontsize=9)

    label_to_artists = {}
    for artist in ax.get_children():
        label = None
        if hasattr(artist, "get_label"):
            label = artist.get_label()

        if not isinstance(label, str):
            continue

        if label.startswith("_"):
            continue

        label_to_artists.setdefault(label, []).append(artist)

    legend_handles = legend.legend_handles
    legend_texts = legend.get_texts()

    for leg_handle, leg_text, label in zip(legend_handles, legend_texts, labels):
        leg_handle.set_picker(True)
        leg_text.set_picker(True)

        artists = label_to_artists.get(label, [])
        legend_artist_map[leg_handle] = (product, label, artists, leg_handle, leg_text)
        legend_artist_map[leg_text] = (product, label, artists, leg_handle, leg_text)

        visible = visibility_state[product].get(label, True)
        for artist in artists:
            artist.set_visible(visible)

        leg_handle.set_alpha(1.0 if visible else 0.2)
        leg_text.set_alpha(1.0 if visible else 0.2)


def plot_product(product: str):
    global current_product, legend_artist_map
    current_product = product
    legend_artist_map = {}

    clear_axes()

    p = prices[prices["product"] == product].sort_values("timestamp").copy()
    t = trades[trades[trade_symbol_col] == product].sort_values("timestamp").copy()
    # Print rule accuracies for currently selected product
    if product in rule_results:
        r = rule_results[product]
        print(
            f"[{product}] "
            f"Stmt1 bid-accuracy = {r['bid_accuracy']:.4f} "
            f"({r['bid_success_count']}/{r['bid_trigger_count']}) | "
            f"Stmt2 ask-accuracy = {r['ask_accuracy']:.4f} "
            f"({r['ask_success_count']}/{r['ask_trigger_count']})"
        )

    ts = p["timestamp"]

    # Price chart
    line_specs = [
        ("mid_price", f"{product} mid", "-", 2.0),
        ("bid_price_1", "bid 1", "-", 1.2),
        ("bid_price_2", "bid 2", "--", 1.0),
        ("bid_price_3", "bid 3", ":", 1.0),
        ("ask_price_1", "ask 1", "-", 1.2),
        ("ask_price_2", "ask 2", "--", 1.0),
        ("ask_price_3", "ask 3", ":", 1.0),
    ]

    for col, label, style, lw in line_specs:
        if col in p.columns and p[col].notna().any():
            ax_price.plot(ts, p[col], linestyle=style, linewidth=lw, label=label)

    if not t.empty and "price" in t.columns:
        sizes = t["quantity"].abs().clip(lower=5, upper=80)
        ax_price.scatter(
            t["timestamp"],
            t["price"],
            s=sizes,
            alpha=1,
            label="trades"
        )

    ax_price.set_title(f"Round 0 Day -1 — {product}: Prices and Trades")
    ax_price.set_ylabel("Price")
    ax_price.grid(True, alpha=0.25)

    # Volume chart
    vol_specs = [
        ("bid_volume_1", "bid vol 1", "-", 1.2),
        ("bid_volume_2", "bid vol 2", "--", 1.0),
        ("bid_volume_3", "bid vol 3", ":", 1.0),
        ("ask_volume_1", "ask vol 1", "-", 1.2),
        ("ask_volume_2", "ask vol 2", "--", 1.0),
        ("ask_volume_3", "ask vol 3", ":", 1.0),
    ]

    for col, label, style, lw in vol_specs:
        if col in p.columns and p[col].notna().any():
            ax_vol.plot(ts, p[col], linestyle=style, linewidth=lw, label=label)

    ax_vol.set_ylabel("Volume")
    ax_vol.set_title("Order Book Volumes")
    ax_vol.grid(True, alpha=0.25)

    # Imbalance chart using only bid_volume_1 and ask_volume_1
    if "bid_volume_1" in p.columns and "ask_volume_1" in p.columns:
        bid1 = p["bid_volume_1"].fillna(0)
        ask1 = p["ask_volume_1"].fillna(0)

        denom = bid1 + ask1

        # Condition: detect abnormal volume (outside [5,10])
        condition = (bid1 > 10) | (bid1 < 5) | (ask1 > 10) | (ask1 < 5)

        # Compute imbalance only where condition is true
        imbalance = ((bid1 - ask1) / denom.replace(0, pd.NA)).where(condition, 0)
        imbalance = imbalance.fillna(0)

        # Rolling EMA and SMA on modified imbalance
        EMA_SPAN = 10
        SMA_WINDOW = 10

        imbalance_ema = imbalance.ewm(span=EMA_SPAN, adjust=False).mean()
        imbalance_sma = imbalance.rolling(window=SMA_WINDOW, min_periods=1).mean()

        ax_imb.plot(ts, imbalance, linewidth=1.8, label="imbalance")
        ax_imb.plot(ts, imbalance_ema, linewidth=1.5, linestyle="--", label=f"imbalance ema({EMA_SPAN})")
        ax_imb.plot(ts, imbalance_sma, linewidth=1.5, linestyle=":", label=f"imbalance sma({SMA_WINDOW})")
        ax_imb.axhline(0, linestyle="--", linewidth=1)

    ax_imb.set_title("Order Book Imbalance")
    ax_imb.set_ylabel("Imbalance")
    ax_imb.set_xlabel("Timestamp")
    ax_imb.grid(True, alpha=0.25)

    add_interactive_legend(ax_price, product)
    add_interactive_legend(ax_vol, product)
    add_interactive_legend(ax_imb, product)

    fig.canvas.draw_idle()


def on_radio(label):
    plot_product(label)


def on_pick(event):
    artist = event.artist
    if artist not in legend_artist_map:
        return

    product, label, target_artists, leg_handle, leg_text = legend_artist_map[artist]

    current_visible = visibility_state[product].get(label, True)
    new_visible = not current_visible
    visibility_state[product][label] = new_visible

    for target in target_artists:
        target.set_visible(new_visible)

    leg_handle.set_alpha(1.0 if new_visible else 0.2)
    leg_text.set_alpha(1.0 if new_visible else 0.2)

    fig.canvas.draw_idle()


radio.on_clicked(on_radio)
fig.canvas.mpl_connect("pick_event", on_pick)

plot_product(default_product)


def on_key(event):
    current = radio.value_selected
    idx = products.index(current)
    if event.key == "right":
        idx = (idx + 1) % len(products)
        radio.set_active(idx)
    elif event.key == "left":
        idx = (idx - 1) % len(products)
        radio.set_active(idx)

fig.canvas.mpl_connect("key_press_event", on_key)

plt.show()