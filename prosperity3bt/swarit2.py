from typing import List, Tuple, Dict
import traceback
import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from math import ceil

class Trader:
    def run(self, state: TradingState):

        result = {}
        conversions = 0
        trader_data = ""

        try:

            # ===========================
            # EMERALDS (StaticTrader style)
            # ===========================

            if "EMERALDS" in state.order_depths:

                orders = []

                od = state.order_depths["EMERALDS"]

                LIMIT = 80

                buy_orders = od.buy_orders
                sell_orders = od.sell_orders

                if buy_orders and sell_orders:

                    bid_wall = min(buy_orders.keys())
                    ask_wall = max(sell_orders.keys())

                    wall_mid = (bid_wall + ask_wall) / 2

                    pos = state.position.get("EMERALDS", 0)

                    buy_cap = LIMIT - pos
                    sell_cap = LIMIT + pos

                    # ---------- LOAD MEMORY ----------

                    data = {}
                    if state.traderData != "":
                        data = json.loads(state.traderData)
                    fills = data.get("em_fills", 0)
                    quotes = data.get("em_quotes", 1)
                    last_pos = data.get("em_last_pos", pos)
                    fill_rate = fills / quotes

                    # ---------- TAKING ----------

                    for sp in sorted(sell_orders.keys()):
                        sv = abs(sell_orders[sp])

                        if sp <= wall_mid - 1:

                            qty = min(sv, buy_cap)

                            if qty > 0:
                                orders.append(Order("EMERALDS", sp, qty))
                                buy_cap -= qty
                                pos += qty

                        elif sp <= wall_mid and pos < 0:

                            qty = min(sv, -pos)

                            if qty > 0:
                                orders.append(Order("EMERALDS", sp, qty))
                                buy_cap -= qty
                                pos += qty


                    for bp in sorted(buy_orders.keys(), reverse=True):
                        bv = buy_orders[bp]

                        if bp >= wall_mid + 1:

                            qty = min(bv, sell_cap)

                            if qty > 0:
                                orders.append(Order("EMERALDS", bp, -qty))
                                sell_cap -= qty
                                pos -= qty

                        elif bp >= wall_mid and pos > 0:

                            qty = min(bv, pos)

                            if qty > 0:
                                orders.append(Order("EMERALDS", bp, -qty))
                                sell_cap -= qty
                                pos -= qty


                    # ---------- UPDATE FILL STATS ----------

                    if pos != last_pos:
                        fills += abs(pos - last_pos)
                    quotes += 1

                    # ==================================================
                    # 2. MAKING — STABLE HYBRID MM (4k+ SAFE)
                    # ==================================================

                    best_bid = max(buy_orders.keys())
                    best_ask = min(sell_orders.keys())

                    mid = (best_bid + best_ask) / 2
                    spread = best_ask - best_bid

                    pos_ratio = pos / LIMIT
                    abs_ratio = abs(pos) / LIMIT

                    best_bid_vol = buy_orders.get(best_bid, 0)
                    best_ask_vol = abs(sell_orders.get(best_ask, 0))


                    # ==================================================
                    # INVENTORY-AWARE RESERVATION PRICE
                    # ==================================================

                    gamma = max(1.5, spread / 4)   # dynamic gamma (important)

                    reservation = mid - gamma * pos_ratio


                    # ==================================================
                    # AGGRESSION OPTIMIZER
                    # ==================================================

                    best_a = 1
                    best_score = -1e9

                    for a_try in range(1, 7):

                        bid_try = reservation - a_try
                        ask_try = reservation + a_try

                        # distance from best → fill prob
                        dist_bid = max(0, best_bid - bid_try + 1)
                        dist_ask = max(0, ask_try - best_ask + 1)

                        dist = (dist_bid + dist_ask) / 2

                        fill_prob = 1 / (1 + dist)

                        spread_gain = min(2 * a_try, spread)

                        inv_penalty = 0.6 * abs_ratio
                        fair_penalty = abs(mid - reservation) / max(1, spread)

                        vol_bonus = 0
                        if best_bid_vol <= 4 or best_ask_vol <= 4:
                            vol_bonus = 0.2

                        early_penalty = 0
                        if state.timestamp < 2000:
                            early_penalty = 0.4

                        fill_bonus = 0
                        if fill_rate < 0.3:
                            fill_bonus += 0.5
                        if fill_rate > 0.7:
                            fill_bonus -= 0.3

                        score = (
                            fill_prob * spread_gain
                            + vol_bonus
                            + fill_bonus
                            - inv_penalty
                            - fair_penalty
                            - early_penalty
                        )

                        if score > best_score:
                            best_score = score
                            best_a = a_try


                    a = best_a


                    # ==================================================
                    # FINAL PRICES (reservation dominates queue)
                    # ==================================================

                    bid_price = max(reservation - a, best_bid + 1)
                    ask_price = min(reservation + a, best_ask - 1)


                    # keep valid
                    if bid_price >= ask_price:
                        bid_price = best_bid + 1
                        ask_price = best_ask - 1

                    if bid_price >= ask_price:
                        bid_price = 0
                        ask_price = 0


                    # ==================================================
                    # EXTREME INVENTORY SAFETY
                    # ==================================================

                    if pos > 0.6 * LIMIT:
                        bid_price -= 2

                    if pos < -0.6 * LIMIT:
                        ask_price += 2


                    # ==================================================
                    # SIZE OPTIMIZER (directional)
                    # ==================================================

                    best_size = 1
                    best_score = -1e9

                    for size_try in range(1, 81):

                        if size_try > buy_cap and size_try > sell_cap:
                            break

                        if state.timestamp < 2000:
                            size_try = min(size_try, 15)

                        fill_prob = 1 / (1 + a + size_try / 5)

                        spread_gain = (ask_price - bid_price) * size_try

                        # directional penalty
                        buy_pen = 0
                        sell_pen = 0

                        if pos > 0:
                            buy_pen = abs_ratio * size_try

                        if pos < 0:
                            sell_pen = abs_ratio * size_try

                        inv_penalty = buy_pen + sell_pen

                        score = fill_prob * spread_gain - inv_penalty

                        if score > best_score:
                            best_score = score
                            best_size = size_try


                    size = best_size


                    # ==================================================
                    # STRONG SIZE SKEW
                    # ==================================================

                    sk = 1.6

                    buy_size = int(size * max(0, 1 - sk * pos_ratio))
                    sell_size = int(size * max(0, 1 + sk * pos_ratio))


                    # ==================================================
                    # CAP SAFETY (important)
                    # ==================================================

                    buy_size = min(buy_size, max(0, buy_cap - 10))
                    sell_size = min(sell_size, max(0, sell_cap - 10))


                    # ==================================================
                    # EXTRA INVENTORY SAFETY
                    # ==================================================

                    if abs(pos) > 0.5 * LIMIT:
                        buy_size = int(buy_size * 0.5)
                        sell_size = int(sell_size * 1.5)


                    # ==================================================
                    # POST — MULTI LEVEL QUOTES
                    # ==================================================

                    levels = 3
                    base_buy = buy_size
                    base_sell = sell_size
                    decay = max(2, size // 5)

                    for i in range(levels):
                        bsize = max(0, base_buy - i * decay)
                        ssize = max(0, base_sell - i * decay)
                        bprice = bid_price - i
                        aprice = ask_price + i
                        if bsize > 0 and bprice > 0:
                            orders.append(Order("EMERALDS", int(bprice), bsize))
                        if ssize > 0 and aprice > 0:
                            orders.append(Order("EMERALDS", int(aprice), -ssize))


                    # ---------- SAVE MEMORY ----------

                    data["em_fills"] = fills
                    data["em_quotes"] = quotes
                    data["em_last_pos"] = pos
                    trader_data = json.dumps(data)


                result["EMERALDS"] = orders


            # ===========================
            # TOMATOES
            # ===========================

            if "TOMATOES" in state.order_depths:

                orders = []

                od = state.order_depths["TOMATOES"]

                pos = state.position.get("TOMATOES", 0)

                LIMIT = 80

                buy_orders = od.buy_orders
                sell_orders = od.sell_orders

                if buy_orders and sell_orders:

                    # ----------------------------
                    # FEATURES
                    # ----------------------------

                    bid_wall = min(buy_orders.keys())
                    ask_wall = max(sell_orders.keys())

                    best_bid = max(buy_orders.keys())
                    best_ask = min(sell_orders.keys())

                    wall_mid = (bid_wall + ask_wall) / 2
                    mid = (best_bid + best_ask) / 2

                    spread = best_ask - best_bid

                    # safe volumes
                    best_bid_vol = buy_orders.get(best_bid, 0)
                    best_ask_vol = abs(sell_orders.get(best_ask, 0))

                    # ----------------------------
                    # LOAD MEMORY
                    # ----------------------------

                    data = {}
                    if state.traderData != "":
                        data = json.loads(state.traderData)

                    prev_mid = data.get("tom_prev", None)
                    fills = data.get("tom_fills", 0)
                    quotes = data.get("tom_quotes", 1)
                    last_pos = data.get("tom_last_pos", pos)
                    fill_rate = fills / quotes

                    buy_cap = LIMIT - pos
                    sell_cap = LIMIT + pos


                    # ==================================================
                    # 1. TAKING (unchanged)
                    # ==================================================

                    for sp in sorted(sell_orders.keys()):
                        sv = abs(sell_orders[sp])

                        if sp <= wall_mid - 1:

                            qty = min(sv, buy_cap)

                            if qty > 0:
                                orders.append(Order("TOMATOES", sp, qty))
                                buy_cap -= qty
                                pos += qty

                        elif sp <= wall_mid and pos < 0:

                            qty = min(sv, -pos)

                            if qty > 0:
                                orders.append(Order("TOMATOES", sp, qty))
                                buy_cap -= qty
                                pos += qty


                    for bp in sorted(buy_orders.keys(), reverse=True):
                        bv = buy_orders[bp]

                        if bp >= wall_mid + 1:

                            qty = min(bv, sell_cap)

                            if qty > 0:
                                orders.append(Order("TOMATOES", bp, -qty))
                                sell_cap -= qty
                                pos -= qty

                        elif bp >= wall_mid and pos > 0:

                            qty = min(bv, pos)

                            if qty > 0:
                                orders.append(Order("TOMATOES", bp, -qty))
                                sell_cap -= qty
                                pos -= qty


                    # ---------- UPDATE FILL STATS ----------

                    if pos != last_pos:
                        fills += abs(pos - last_pos)
                    quotes += 1

                    # ==================================================
                    # 2. MAKING — STABLE HYBRID MM (4k+ SAFE)
                    # ==================================================

                    best_bid = max(buy_orders.keys())
                    best_ask = min(sell_orders.keys())

                    mid = (best_bid + best_ask) / 2
                    spread = best_ask - best_bid

                    pos_ratio = pos / LIMIT
                    abs_ratio = abs(pos) / LIMIT

                    best_bid_vol = buy_orders.get(best_bid, 0)
                    best_ask_vol = abs(sell_orders.get(best_ask, 0))


                    # ==================================================
                    # INVENTORY-AWARE RESERVATION PRICE
                    # ==================================================

                    gamma = max(1.5, spread / 4)   # dynamic gamma (important)

                    reservation = mid - gamma * pos_ratio


                    # ==================================================
                    # AGGRESSION OPTIMIZER
                    # ==================================================

                    best_a = 1
                    best_score = -1e9

                    for a_try in range(1, 7):

                        bid_try = reservation - a_try
                        ask_try = reservation + a_try

                        # distance from best → fill prob
                        dist_bid = max(0, best_bid - bid_try + 1)
                        dist_ask = max(0, ask_try - best_ask + 1)

                        dist = (dist_bid + dist_ask) / 2

                        fill_prob = 1 / (1 + dist)

                        spread_gain = min(2 * a_try, spread)

                        inv_penalty = 0.6 * abs_ratio
                        fair_penalty = abs(mid - reservation) / max(1, spread)

                        vol_bonus = 0
                        if best_bid_vol <= 4 or best_ask_vol <= 4:
                            vol_bonus = 0.2

                        early_penalty = 0
                        if state.timestamp < 2000:
                            early_penalty = 0.4

                        fill_bonus = 0
                        if fill_rate < 0.3:
                            fill_bonus += 0.5
                        if fill_rate > 0.7:
                            fill_bonus -= 0.3

                        score = (
                            fill_prob * spread_gain
                            + vol_bonus
                            + fill_bonus
                            - inv_penalty
                            - fair_penalty
                            - early_penalty
                        )

                        if score > best_score:
                            best_score = score
                            best_a = a_try


                    a = best_a


                    # ==================================================
                    # FINAL PRICES (reservation dominates queue)
                    # ==================================================

                    bid_price = max(reservation - a, best_bid + 1)
                    ask_price = min(reservation + a, best_ask - 1)


                    # keep valid
                    if bid_price >= ask_price:
                        bid_price = best_bid + 1
                        ask_price = best_ask - 1

                    if bid_price >= ask_price:
                        bid_price = 0
                        ask_price = 0


                    # ==================================================
                    # EXTREME INVENTORY SAFETY
                    # ==================================================

                    if pos > 0.6 * LIMIT:
                        bid_price -= 2

                    if pos < -0.6 * LIMIT:
                        ask_price += 2


                    # ==================================================
                    # SIZE OPTIMIZER (directional)
                    # ==================================================

                    best_size = 1
                    best_score = -1e9

                    for size_try in range(1, 81):

                        if size_try > buy_cap and size_try > sell_cap:
                            break

                        if state.timestamp < 2000:
                            size_try = min(size_try, 15)

                        fill_prob = 1 / (1 + a + size_try / 5)

                        spread_gain = (ask_price - bid_price) * size_try

                        # directional penalty
                        buy_pen = 0
                        sell_pen = 0

                        if pos > 0:
                            buy_pen = abs_ratio * size_try

                        if pos < 0:
                            sell_pen = abs_ratio * size_try

                        inv_penalty = buy_pen + sell_pen

                        score = fill_prob * spread_gain - inv_penalty

                        if score > best_score:
                            best_score = score
                            best_size = size_try


                    size = best_size


                    # ==================================================
                    # STRONG SIZE SKEW
                    # ==================================================

                    sk = 1.6

                    buy_size = int(size * max(0, 1 - sk * pos_ratio))
                    sell_size = int(size * max(0, 1 + sk * pos_ratio))


                    # ==================================================
                    # CAP SAFETY (important)
                    # ==================================================

                    buy_size = min(buy_size, max(0, buy_cap - 10))
                    sell_size = min(sell_size, max(0, sell_cap - 10))


                    # ==================================================
                    # EXTRA INVENTORY SAFETY
                    # ==================================================

                    if abs(pos) > 0.5 * LIMIT:
                        buy_size = int(buy_size * 0.5)
                        sell_size = int(sell_size * 1.5)


                    # ==================================================
                    # POST — MULTI LEVEL QUOTES
                    # ==================================================

                    levels = 3
                    base_buy = buy_size
                    base_sell = sell_size
                    decay = max(2, size // 5)

                    for i in range(levels):
                        bsize = max(0, base_buy - i * decay)
                        ssize = max(0, base_sell - i * decay)
                        bprice = bid_price - i
                        aprice = ask_price + i
                        if bsize > 0 and bprice > 0:
                            orders.append(Order("TOMATOES", int(bprice), bsize))
                        if ssize > 0 and aprice > 0:
                            orders.append(Order("TOMATOES", int(aprice), -ssize))

                    data["tom_prev"] = mid
                    data["tom_fills"] = fills
                    data["tom_quotes"] = quotes
                    data["tom_last_pos"] = pos
                    trader_data = json.dumps(data)

                result["TOMATOES"] = orders

        except Exception as e:
            print("ERROR", e)
            print(traceback.format_exc())

        return result, conversions, trader_data