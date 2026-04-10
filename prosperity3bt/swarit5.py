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
        data = {}
        if state.traderData:
            try:
                data = json.loads(state.traderData)
            except:
                data = {}
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

                    raw_best_bid = max(buy_orders.keys())
                    raw_best_ask = min(sell_orders.keys())
                    mid = (raw_best_bid + raw_best_ask) / 2

                    buy_cap = LIMIT - pos
                    sell_cap = LIMIT + pos

                    # -------------------------------------------------
                    # STRESS-TEST MODE PARAMETERS
                    # -------------------------------------------------
                    DUMP_TRIGGER = LIMIT - 5     # once inventory reaches this, start dumping
                    RESET_LEVEL = 5              # once inventory gets back near flat, start buying again

                    tom_probe_state = data.get("tom_probe_state", "ACCUMULATE")
                    prev_mid = data.get("tom_prev_mid", mid)
                    prev_best_bid = data.get("tom_prev_best_bid", raw_best_bid)
                    prev_best_ask = data.get("tom_prev_best_ask", raw_best_ask)

                    # -------------------------------------------------
                    # MODE SWITCHING
                    # -------------------------------------------------
                    if tom_probe_state == "ACCUMULATE" and pos >= DUMP_TRIGGER:
                        tom_probe_state = "DUMP"

                    if tom_probe_state == "DUMP" and pos <= RESET_LEVEL:
                        tom_probe_state = "ACCUMULATE"

                    logger.print(
                        "[TOM_PROBE_STATE]",
                        "ts=", state.timestamp,
                        "mode=", tom_probe_state,
                        "pos=", pos,
                        "buy_cap=", buy_cap,
                        "sell_cap=", sell_cap,
                        "best_bid=", raw_best_bid,
                        "best_ask=", raw_best_ask,
                        "mid=", mid
                    )

                    # -------------------------------------------------
                    # MODE 1: ACCUMULATE
                    # Buy all visible asks until inventory is near full
                    # -------------------------------------------------
                    if tom_probe_state == "ACCUMULATE":
                        sweep_cost = 0
                        sweep_qty = 0

                        for sp in sorted(sell_orders.keys()):
                            ask_qty = abs(sell_orders[sp])
                            qty = min(ask_qty, buy_cap)

                            if qty > 0:
                                orders.append(Order("TOMATOES", sp, qty))
                                buy_cap -= qty
                                pos += qty
                                sweep_qty += qty
                                sweep_cost += sp * qty

                        avg_fill = (sweep_cost / sweep_qty) if sweep_qty > 0 else None

                        logger.print(
                            "[TOM_ACCUMULATE]",
                            "ts=", state.timestamp,
                            "swept_qty=", sweep_qty,
                            "avg_fill=", avg_fill,
                            "new_pos=", pos,
                            "book_best_bid=", raw_best_bid,
                            "book_best_ask=", raw_best_ask
                        )

                    # -------------------------------------------------
                    # MODE 2: DUMP
                    # Sell all visible bids until inventory is reduced
                    # -------------------------------------------------
                    elif tom_probe_state == "DUMP":
                        dump_value = 0
                        dump_qty = 0

                        for bp in sorted(buy_orders.keys(), reverse=True):
                            bid_qty = buy_orders[bp]
                            qty = min(bid_qty, sell_cap, pos)

                            if qty > 0:
                                orders.append(Order("TOMATOES", bp, -qty))
                                sell_cap -= qty
                                pos -= qty
                                dump_qty += qty
                                dump_value += bp * qty

                        avg_dump = (dump_value / dump_qty) if dump_qty > 0 else None

                        logger.print(
                            "[TOM_DUMP]",
                            "ts=", state.timestamp,
                            "dump_qty=", dump_qty,
                            "avg_dump=", avg_dump,
                            "new_pos=", pos,
                            "book_best_bid=", raw_best_bid,
                            "book_best_ask=", raw_best_ask
                        )

                    # -------------------------------------------------
                    # RESPONSE METRICS
                    # -------------------------------------------------
                    logger.print(
                        "[TOM_RESPONSE]",
                        "ts=", state.timestamp,
                        "prev_mid=", prev_mid,
                        "mid=", mid,
                        "delta_mid=", mid - prev_mid,
                        "prev_best_bid=", prev_best_bid,
                        "best_bid=", raw_best_bid,
                        "delta_bid=", raw_best_bid - prev_best_bid,
                        "prev_best_ask=", prev_best_ask,
                        "best_ask=", raw_best_ask,
                        "delta_ask=", raw_best_ask - prev_best_ask,
                        "spread=", raw_best_ask - raw_best_bid
                    )

                    # -------------------------------------------------
                    # SAVE STATE
                    # -------------------------------------------------
                    data["tom_probe_state"] = tom_probe_state
                    data["tom_prev_mid"] = mid
                    data["tom_prev_best_bid"] = raw_best_bid
                    data["tom_prev_best_ask"] = raw_best_ask

                result["TOMATOES"] = orders

        except Exception as e:
            print("ERROR", e)
            print(traceback.format_exc())

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        #logger.print(result)
        return result, conversions, trader_data