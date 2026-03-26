from typing import List, Tuple, Dict
import traceback
import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from math import ceil


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


                    # ---------- MAKING ----------

                    bid_price = bid_wall + 1
                    ask_price = ask_wall - 1

                    for bp in sorted(buy_orders.keys(), reverse=True):

                        overbid = bp + 1

                        if overbid < wall_mid:
                            bid_price = max(bid_price, overbid)
                            break

                        elif bp < wall_mid:
                            bid_price = max(bid_price, bp)
                            break


                    for sp in sorted(sell_orders.keys()):

                        underask = sp - 1

                        if underask > wall_mid:
                            ask_price = min(ask_price, underask)
                            break

                        elif sp > wall_mid:
                            ask_price = min(ask_price, sp)
                            break


                    if buy_cap > 0:
                        orders.append(Order("EMERALDS", int(bid_price), buy_cap))

                    if sell_cap > 0:
                        orders.append(Order("EMERALDS", int(ask_price), -sell_cap))


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

                    buy_vol = sum(buy_orders.values())
                    sell_vol = sum(abs(v) for v in sell_orders.values())

                    imbalance = buy_vol - sell_vol

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
                    # 1. TAKING (WINNING STRAT — KEEP EXACT)
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
                    # 2. MAKING (AGGRESSIVE ADAPTIVE MM)
                    # ==================================================
                    # tomorrow (25th march, work on this.... make market making very efficient... use fillprobablity and everythign to design a very good aggressor function)
                    # ---------- aggression function ----------

                    pos_ratio = abs(pos) / LIMIT
                    mid_dev = abs(mid - wall_mid)

                    agg = spread * 0.25

                    agg *= (1 - pos_ratio)
                    agg *= (1 - mid_dev / max(1, spread))

                    agg = int(max(1, min(5, agg)))


                    # ---------- inventory skew ----------
                    # reduce risk when position large

                    skew = int(pos / 20)   # tuning parameter


                    # ---------- base quotes (queue priority) ----------

                    bid_price = best_bid + agg - skew
                    ask_price = best_ask - agg - skew


                    # ---------- keep inside wall_mid ----------
                    if bid_price >= wall_mid:
                        bid_price = int(wall_mid - 1)

                    if ask_price <= wall_mid:
                        ask_price = int(wall_mid + 1)


                    # ---------- keep valid spread ----------
                    if bid_price >= ask_price:
                        bid_price = best_bid
                        ask_price = best_ask


                    # ---------- extra safety near limits ----------
                    if pos > 0.6 * LIMIT:
                        bid_price -= 1

                    if pos < -0.6 * LIMIT:
                        ask_price += 1


                    # ---------- post orders ----------
                    if buy_cap > 0:
                        orders.append(Order("TOMATOES", int(bid_price), buy_cap))

                    if sell_cap > 0:
                        orders.append(Order("TOMATOES", int(ask_price), -sell_cap))


                    # # ==================================================
                    # # 3. RISK CONTROL
                    # # ==================================================

                    # if abs(pos) > 0.75 * LIMIT:

                    #     reduce = 1

                    #     if pos > 0:
                    #         orders.append(Order("TOMATOES", best_bid, -reduce))
                    #         pos -= reduce

                    #     elif pos < 0:
                    #         orders.append(Order("TOMATOES", best_ask, reduce))
                    #         pos += reduce


                    # ==================================================
                    # SAVE STATE
                    # ==================================================

                    data["tom_prev"] = mid
                    trader_data = json.dumps(data)


                result["TOMATOES"] = orders

        except Exception as e:
            logger.flush("ERROR", e)
            logger.flush(traceback.format_exc())

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data