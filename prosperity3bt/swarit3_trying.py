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

        # try:

        #     # ===========================
        #     # EMERALDS (StaticTrader style)
        #     # ===========================

        #     if "EMERALDS" in state.order_depths:

        #         orders = []

        #         od = state.order_depths["EMERALDS"]

        #         LIMIT = 80

        #         buy_orders = od.buy_orders
        #         sell_orders = od.sell_orders

        #         if buy_orders and sell_orders:

        #             bid_wall = min(buy_orders.keys())
        #             ask_wall = max(sell_orders.keys())

        #             wall_mid = (bid_wall + ask_wall) / 2

        #             pos = state.position.get("EMERALDS", 0)

        #             buy_cap = LIMIT - pos
        #             sell_cap = LIMIT + pos

        #             # ---------- TAKING ----------

        #             for sp in sorted(sell_orders.keys()):
        #                 sv = abs(sell_orders[sp])

        #                 if sp <= wall_mid - 1:

        #                     qty = min(sv, buy_cap)

        #                     if qty > 0:
        #                         orders.append(Order("EMERALDS", sp, qty))
        #                         buy_cap -= qty
        #                         pos += qty

        #                 elif sp <= wall_mid and pos < 0:

        #                     qty = min(sv, -pos)

        #                     if qty > 0:
        #                         orders.append(Order("EMERALDS", sp, qty))
        #                         buy_cap -= qty
        #                         pos += qty


        #             for bp in sorted(buy_orders.keys(), reverse=True):
        #                 bv = buy_orders[bp]

        #                 if bp >= wall_mid + 1:

        #                     qty = min(bv, sell_cap)

        #                     if qty > 0:
        #                         orders.append(Order("EMERALDS", bp, -qty))
        #                         sell_cap -= qty
        #                         pos -= qty

        #                 elif bp >= wall_mid and pos > 0:

        #                     qty = min(bv, pos)

        #                     if qty > 0:
        #                         orders.append(Order("EMERALDS", bp, -qty))
        #                         sell_cap -= qty
        #                         pos -= qty


        #             # ---------- MAKING ----------

        #             bid_price = bid_wall + 1
        #             ask_price = ask_wall - 1

        #             for bp in sorted(buy_orders.keys(), reverse=True):

        #                 overbid = bp + 1

        #                 if overbid < wall_mid:
        #                     bid_price = max(bid_price, overbid)
        #                     break

        #                 elif bp < wall_mid:
        #                     bid_price = max(bid_price, bp)
        #                     break


        #             for sp in sorted(sell_orders.keys()):

        #                 underask = sp - 1

        #                 if underask > wall_mid:
        #                     ask_price = min(ask_price, underask)
        #                     break

        #                 elif sp > wall_mid:
        #                     ask_price = min(ask_price, sp)
        #                     break


        #             if buy_cap > 0:
        #                 orders.append(Order("EMERALDS", int(bid_price), buy_cap))

        #             if sell_cap > 0:
        #                 orders.append(Order("EMERALDS", int(ask_price), -sell_cap))


        #         result["EMERALDS"] = orders


        #     # ===========================
        #     # TOMATOES
        #     # ===========================

        #     if "TOMATOES" in state.order_depths:

        #         orders = []

        #         od = state.order_depths["TOMATOES"]

        #         pos = state.position.get("TOMATOES", 0)

        #         LIMIT = 80

        #         buy_orders = od.buy_orders
        #         sell_orders = od.sell_orders

        #         if buy_orders and sell_orders:

        #             bid_wall = min(buy_orders.keys())
        #             ask_wall = max(sell_orders.keys())

        #             wall_mid = (bid_wall + ask_wall) / 2

        #             best_bid_bot = max(buy_orders.keys())
        #             best_ask_bot = min(sell_orders.keys())

        #             mid = (best_bid_bot + best_ask_bot) / 2

        #             prev_mid = data.get("tom_prev", mid)

        #             diff = mid - prev_mid
        #             buy_cap = LIMIT - pos
        #             sell_cap = LIMIT + pos

        #             # NEW: load stored trades from previous ticks
        #             tom_trades = data.get("tom_trades", [])

        #             # NEW: prune old trades using lookback window
        #             LOOKBACK = 10
        #             tom_trades = [t for t in tom_trades if t["timestamp"] >= state.timestamp - LOOKBACK]

        #             # ===========================
        #             # 1. TAKING (same as EMERALDS)
        #             # ===========================

        #             for sp in sorted(sell_orders.keys()):
        #                 sv = abs(sell_orders[sp])

        #                 if sp <= wall_mid - 1:

        #                     qty = min(sv, buy_cap)

        #                     if qty > 0:
        #                         orders.append(Order("TOMATOES", sp, qty))
        #                         buy_cap -= qty
        #                         pos += qty
        #                         # NEW: store aggressive buy trade
        #                         tom_trades.append({"price": sp, "qty": qty, "type": "BUY", "timestamp": state.timestamp})

        #                 elif sp <= wall_mid and pos < 0:

        #                     qty = min(sv, -pos)

        #                     if qty > 0:
        #                         orders.append(Order("TOMATOES", sp, qty))
        #                         buy_cap -= qty
        #                         pos += qty
        #                         # NEW: store aggressive buy trade (position recovery)
        #                         tom_trades.append({"price": sp, "qty": qty, "type": "BUY", "timestamp": state.timestamp})


        #             for bp in sorted(buy_orders.keys(), reverse=True):
        #                 bv = buy_orders[bp]

        #                 if bp >= wall_mid + 1:

        #                     qty = min(bv, sell_cap)

        #                     if qty > 0:
        #                         orders.append(Order("TOMATOES", bp, -qty))
        #                         sell_cap -= qty
        #                         pos -= qty
        #                         # NEW: store aggressive sell trade
        #                         tom_trades.append({"price": bp, "qty": qty, "type": "SELL", "timestamp": state.timestamp})

        #                 elif bp >= wall_mid and pos > 0:

        #                     qty = min(bv, pos)

        #                     if qty > 0:
        #                         orders.append(Order("TOMATOES", bp, -qty))
        #                         sell_cap -= qty
        #                         pos -= qty
        #                         # NEW: store aggressive sell trade (position recovery)
        #                         tom_trades.append({"price": bp, "qty": qty, "type": "SELL", "timestamp": state.timestamp})


        #             # NEW: attempt profit-taking exits from stored trades
        #             EDGE = 1
        #             remaining_trades = []

        #             for trade in tom_trades:
        #                 # Skip trades entered this tick to avoid same-tick closure
        #                 if trade["timestamp"] == state.timestamp:
        #                     remaining_trades.append(trade)
        #                     continue

        #                 remaining_qty = trade["qty"]

        #                 if trade["type"] == "BUY":
        #                     # NEW: close BUY trade if current best bid is profitable
        #                     if best_bid_bot >= trade["price"] + EDGE and sell_cap > 0:
        #                         close_qty = min(remaining_qty, sell_cap)
        #                         if close_qty > 0:
        #                             orders.append(Order("TOMATOES", best_bid_bot, -close_qty))
        #                             sell_cap -= close_qty
        #                             remaining_qty -= close_qty

        #                 elif trade["type"] == "SELL":
        #                     # NEW: close SELL trade if current best ask is profitable
        #                     if best_ask_bot <= trade["price"] - EDGE and buy_cap > 0:
        #                         close_qty = min(remaining_qty, buy_cap)
        #                         if close_qty > 0:
        #                             orders.append(Order("TOMATOES", best_ask_bot, close_qty))
        #                             buy_cap -= close_qty
        #                             remaining_qty -= close_qty

        #                 # NEW: keep trade if not fully closed, update remaining qty
        #                 if remaining_qty > 0:
        #                     trade["qty"] = remaining_qty
        #                     remaining_trades.append(trade)

        #             # NEW: save updated trade list back to data
        #             tom_trades = remaining_trades
        #             data["tom_trades"] = tom_trades

        #             # ===========================
        #             # 2. MAKING (same as EMERALDS)
        #             # ===========================

        #             bid_price = bid_wall + 1
        #             ask_price = ask_wall - 1

        #             for bp in sorted(buy_orders.keys(), reverse=True):

        #                 overbid = bp + 1

        #                 if overbid < wall_mid:
        #                     bid_price = max(bid_price, overbid)
        #                     break

        #                 elif bp < wall_mid:
        #                     bid_price = max(bid_price, bp)
        #                     break


        #             for sp in sorted(sell_orders.keys()):

        #                 underask = sp - 1

        #                 if underask > wall_mid:
        #                     ask_price = min(ask_price, underask)
        #                     break

        #                 elif sp > wall_mid:
        #                     ask_price = min(ask_price, sp)
        #                     break


        #             # if buy_cap > 0:
        #             #     orders.append(Order("TOMATOES", int(bid_price), buy_cap))

        #             # if sell_cap > 0:
        #             #     orders.append(Order("TOMATOES", int(ask_price), -sell_cap))


        #             # -----------------------
        #             # save price
        #             # -----------------------

        #             data["tom_prev"] = mid
        #             # trader_data = json.dumps(data)

        #         result["TOMATOES"] = orders

        # except Exception as e:
        #     logger.print("ERROR", e)
        #     logger.print(traceback.format_exc())

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        logger.print(result)
        return result, conversions, trader_data