from typing import List, Tuple, Dict
import traceback
import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from math import ceil

import json
from typing import Any

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2

            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out


logger = Logger()

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


                    # ==================================================
                    # 2. MAKING (AGGRESSIVE ADAPTIVE MM — SAME AS TOMATOES)
                    # ==================================================

                    best_bid = max(buy_orders.keys())
                    best_ask = min(sell_orders.keys())

                    mid = (best_bid + best_ask) / 2
                    spread = best_ask - best_bid

                    best_bid_vol = buy_orders.get(best_bid, 0)
                    best_ask_vol = abs(sell_orders.get(best_ask, 0))


                    # ---------- choose best aggression a ----------

                    best_a = 1
                    best_score = -1e9

                    pos_ratio = abs(pos) / LIMIT
                    mid_dev = abs(mid - wall_mid)

                    for a_try in range(1, 6):

                        dist = a_try

                        queue = best_bid_vol + best_ask_vol

                        queue_penalty = queue / 20.0

                        fill_prob = 1 / (1 + dist + queue_penalty)

                        effective_spread = spread / (1 + queue_penalty)

                        spread_gain = effective_spread

                        inv_penalty = 0.4 * pos_ratio
                        fair_penalty = 0.3 * (mid_dev / max(1, spread))

                        vol_bonus = 0
                        if best_bid_vol <= 4 or best_ask_vol <= 4:
                            vol_bonus = 0.2

                        early_penalty = 0
                        if state.timestamp < 2000:
                            early_penalty = 0.3

                        score = (
                            fill_prob * spread_gain
                            + vol_bonus
                            - inv_penalty
                            - fair_penalty
                            - early_penalty
                        )

                        if score > best_score:
                            best_score = score
                            best_a = a_try


                    a = best_a


                    # ---------- inventory skew ----------

                    skew = 1

                    bid_price = best_bid + a - skew
                    ask_price = best_ask - a + skew


                    # ---------- keep inside fair ----------

                    if bid_price >= mid:
                        bid_price = int(mid - 1)

                    if ask_price <= mid:
                        ask_price = int(mid + 1)


                    # ---------- keep valid spread ----------

                    if bid_price >= ask_price:
                        bid_price = best_bid
                        ask_price = best_ask


                    # ---------- limit safety ----------

                    if pos > 0.7 * LIMIT:
                        bid_price -= 1

                    if pos < -0.7 * LIMIT:
                        ask_price += 1


                    # ==================================================
                    # SIZE OPTIMIZATION
                    # ==================================================

                    best_size = 1
                    best_size_score = -1e9

                    pos_ratio = abs(pos) / LIMIT
                    mid_dev = abs(mid - wall_mid)

                    for size_try in range(1, 81):

                        if size_try > buy_cap and size_try > sell_cap:
                            break

                        fill_prob = 1 / (1 + a + size_try / 5)

                        spread_gain = spread * size_try

                        inv_penalty = 1.2 * pos_ratio * size_try
                        fair_penalty = 0.3 * (mid_dev / max(1, spread)) * size_try

                        early_penalty = 0
                        if state.timestamp < 2000:
                            early_penalty = 0.3 * size_try

                        score = (
                            fill_prob * spread_gain
                            - inv_penalty
                            - fair_penalty
                            - early_penalty
                        )

                        if score > best_size_score:
                            best_size_score = score
                            best_size = size_try


                    size = best_size


                    # ---------- clamp with caps ----------

                    buy_size = min(size, max(0, buy_cap - 10))
                    sell_size = min(size, max(0, sell_cap - 10))


                    # ==================================================
                    # POST
                    # ==================================================

                    if buy_size > 0:
                        orders.append(
                            Order("EMERALDS", int(bid_price), buy_size)
                        )
                        # print(Order("EMERALDS", int(bid_price), buy_size))
                        # print(pos)

                    if sell_size > 0:
                        orders.append(
                            Order("EMERALDS", int(ask_price), -sell_size)
                        )
                        # print(Order("EMERALDS", int(ask_price), -sell_size))
                        # print(pos)


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


                    # ==================================================
                    # 2. MAKING (AGGRESSIVE ADAPTIVE MM — FIXED)
                    # ==================================================

                    # ---------- choose best aggression a ----------

                    best_a = 1
                    best_score = -1e9

                    pos_ratio = abs(pos) / LIMIT
                    mid_dev = abs(mid - wall_mid)

                    for a_try in range(1, 6):

                        dist = a_try

                        queue = best_bid_vol + best_ask_vol

                        queue_penalty = queue / 20.0

                        fill_prob = 1 / (1 + dist + queue_penalty)

                        effective_spread = spread / (1 + queue_penalty)

                        spread_gain = effective_spread

                        # risk penalties
                        inv_penalty = 0.4 * pos_ratio
                        fair_penalty = 0.3 * (mid_dev / max(1, spread))

                        # volume bonus (low liquidity → be aggressive)
                        vol_bonus = 0
                        if best_bid_vol <= 4 or best_ask_vol <= 4:
                            vol_bonus = 0.2

                        # early penalty
                        early_penalty = 0
                        if state.timestamp < 2000:
                            early_penalty = 0.3

                        score = (
                            fill_prob * spread_gain
                            + vol_bonus
                            - inv_penalty
                            - fair_penalty
                            - early_penalty
                        )

                        if score > best_score:
                            best_score = score
                            best_a = a_try


                    a = best_a

                    # ---------- inventory skew ----------
                    skew = 1

                    # ---------- queue priority quotes ----------

                    bid_price = best_bid + a - skew
                    ask_price = best_ask - a + skew


                    # ---------- keep inside fair ----------

                    if bid_price >= mid:
                        bid_price = int(mid - 1)

                    if ask_price <= mid:
                        ask_price = int(mid + 1)


                    # ---------- keep valid spread ----------

                    if bid_price >= ask_price:
                        bid_price = best_bid
                        ask_price = best_ask


                    # ---------- limit safety ----------

                    if pos > 0.7 * LIMIT:
                        bid_price -= 1

                    if pos < -0.7 * LIMIT:
                        ask_price += 1

                    # ==================================================
                    # SIZE OPTIMIZATION (same method as a)
                    # ==================================================

                    best_size = 1
                    best_size_score = -1e9

                    pos_ratio = abs(pos) / LIMIT
                    mid_dev = abs(mid - wall_mid)

                    for size_try in range(1, 81):

                        # cannot exceed capacity
                        if size_try > buy_cap and size_try > sell_cap:
                            break

                        # fill prob decreases with size
                        fill_prob = 1 / (1 + a + size_try / 5)

                        spread_gain = spread * size_try

                        inv_penalty = 1.2 * pos_ratio * size_try
                        fair_penalty = 0.3 * (mid_dev / max(1, spread)) * size_try

                        early_penalty = 0
                        if state.timestamp < 2000:
                            early_penalty = 0.3 * size_try

                        score = (
                            fill_prob * spread_gain
                            - inv_penalty
                            - fair_penalty
                            - early_penalty
                        )

                        if score > best_size_score:
                            best_size_score = score
                            best_size = size_try


                    size = best_size


                    # clamp with caps

                    buy_size = min(size, max(0, buy_cap - 20))
                    sell_size = min(size, max(0, sell_cap - 20))

        
                    # ==================================================
                    # POST
                    # ==================================================

                    if buy_size > 0:
                        orders.append(Order("TOMATOES", int(bid_price), buy_size))
                        # logger.print(Order("TOMATOES", int(bid_price), buy_size))
                        # logger.print(pos)

                    if sell_size > 0:
                        orders.append(Order("TOMATOES", int(ask_price), -sell_size))
                        # logger.print(Order("TOMATOES", int(ask_price), -sell_size))
                        # logger.print(pos)

                    data["tom_prev"] = mid
                    trader_data = json.dumps(data)

                result["TOMATOES"] = orders

        except Exception as e:
            logger.print("ERROR", e)
            logger.print(traceback.format_exc())

        logger.flush(state, result, conversions, trader_data)

        return result, conversions, trader_data