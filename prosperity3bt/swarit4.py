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

                    bid_wall = min(buy_orders.keys())
                    ask_wall = max(sell_orders.keys())

                    wall_mid = (bid_wall + ask_wall) / 2

                    best_bid_bot = max(buy_orders.keys())
                    best_ask_bot = min(sell_orders.keys())

                    best_bid_size = buy_orders[best_bid_bot]
                    best_ask_size = abs(sell_orders[best_ask_bot])

                    mid = (best_bid_bot + best_ask_bot) / 2

                    if best_bid_size + best_ask_size > 0:
                        microprice = (
                            best_ask_bot * best_bid_size + best_bid_bot * best_ask_size
                        ) / (best_bid_size + best_ask_size)
                    else:
                        microprice = mid

                    prev_fair = data.get("tom_fair", microprice)
                    alpha = 0.25
                    fair_price = alpha * microprice + (1 - alpha) * prev_fair

                    buy_cap = LIMIT - pos
                    sell_cap = LIMIT + pos

                    # =========================================================
                    # SIMPLE FLICKER DETECTION
                    # =========================================================
                    # We only use flickers to REDUCE EXISTING INVENTORY.
                    #
                    # cheap ask flicker  -> if short, buy it back
                    # rich bid flicker   -> if long, sell into it
                    #
                    # No separate regime, no position-tracking state, no special
                    # exit logic. Normal MM + normal MT continue regardless.
                    # =========================================================

                    curr_bid_depth = len(buy_orders)
                    curr_ask_depth = len(sell_orders)

                    prev_bid_depth = data.get("tom_prev_bid_depth", curr_bid_depth)
                    prev_ask_depth = data.get("tom_prev_ask_depth", curr_ask_depth)

                    prev_buy_orders_raw = data.get("tom_prev_buy_orders", {})
                    prev_sell_orders_raw = data.get("tom_prev_sell_orders", {})

                    prev_buy_orders = {int(k): v for k, v in prev_buy_orders_raw.items()}
                    prev_sell_orders = {int(k): v for k, v in prev_sell_orders_raw.items()}

                    new_bid_prices = [p for p in buy_orders.keys() if p not in prev_buy_orders]
                    new_ask_prices = [p for p in sell_orders.keys() if p not in prev_sell_orders]

                    flicker_bid_price = max(new_bid_prices) if new_bid_prices else None
                    flicker_ask_price = min(new_ask_prices) if new_ask_prices else None

                    bid_flicker = (
                        prev_bid_depth == 2
                        and curr_bid_depth == 3
                        and flicker_bid_price is not None
                    )
                    ask_flicker = (
                        prev_ask_depth == 2
                        and curr_ask_depth == 3
                        and flicker_ask_price is not None
                    )
                    

                    # # =========================================================
                    # # SHADOW PRESSURE TEST (NO REAL ORDER PLACEMENT)
                    # # =========================================================
                    # # Periodically define a hypothetical large bid/ask away from touch
                    # # and measure whether the market reacts on later ticks.
                    # # This block NEVER sends the test order.
                    # # =========================================================

                    # shadow_test = data.get("tom_shadow_test", None)

                    # TEST_EVERY = 1000          # every 10 timestamps if step=100
                    # TEST_SIZE = 40
                    # TEST_OFFSET = 3            # away from current touch
                    # TRACK_HORIZON = 300        # track for 3 ticks

                    # # -------------------------
                    # # 1) launch a new shadow test periodically
                    # # -------------------------
                    # if shadow_test is None and state.timestamp % TEST_EVERY == 0:
                    #     shadow_side = "BID" if (state.timestamp // TEST_EVERY) % 2 == 0 else "ASK"

                    #     if shadow_side == "BID":
                    #         shadow_price = best_bid_bot - TEST_OFFSET
                    #         shadow_would_be_top = shadow_price >= best_bid_bot
                    #     else:
                    #         shadow_price = best_ask_bot + TEST_OFFSET
                    #         shadow_would_be_top = shadow_price <= best_ask_bot

                    #     shadow_test = {
                    #         "start_ts": state.timestamp,
                    #         "side": shadow_side,
                    #         "price": shadow_price,
                    #         "size": TEST_SIZE,
                    #         "start_best_bid": best_bid_bot,
                    #         "start_best_ask": best_ask_bot,
                    #         "start_mid": mid,
                    #         "start_micro": microprice,
                    #         "start_spread": best_ask_bot - best_bid_bot,
                    #         "start_bid_depth": curr_bid_depth,
                    #         "start_ask_depth": curr_ask_depth,
                    #         "start_bid_size": best_bid_size,
                    #         "start_ask_size": best_ask_size,
                    #         "would_cancel_if_top_next_tick": False,
                    #         "observations": [],
                    #     }

                    #     logger.print(
                    #         "[SHADOW_START]",
                    #         "ts=", state.timestamp,
                    #         "side=", shadow_side,
                    #         "price=", shadow_price,
                    #         "size=", TEST_SIZE,
                    #         "best_bid=", best_bid_bot,
                    #         "best_ask=", best_ask_bot,
                    #         "mid=", mid,
                    #         "micro=", microprice,
                    #         "spread=", best_ask_bot - best_bid_bot
                    #     )

                    # # -------------------------
                    # # 2) update current shadow test
                    # # -------------------------
                    # if shadow_test is not None:
                    #     age = state.timestamp - shadow_test["start_ts"]

                    #     # would our hypothetical order become top-of-book now?
                    #     if shadow_test["side"] == "BID":
                    #         if shadow_test["price"] >= best_bid_bot:
                    #             shadow_test["would_cancel_if_top_next_tick"] = True
                    #     else:
                    #         if shadow_test["price"] <= best_ask_bot:
                    #             shadow_test["would_cancel_if_top_next_tick"] = True

                    #     # nearby market-trade activity
                    #     near_trade_qty = 0
                    #     near_trade_count = 0
                    #     for tr in state.market_trades.get("TOMATOES", []):
                    #         if abs(tr.price - shadow_test["price"]) <= 1:
                    #             near_trade_qty += abs(tr.quantity)
                    #             near_trade_count += 1

                    #     obs = {
                    #         "ts": state.timestamp,
                    #         "age": age,
                    #         "best_bid": best_bid_bot,
                    #         "best_ask": best_ask_bot,
                    #         "mid": mid,
                    #         "micro": microprice,
                    #         "spread": best_ask_bot - best_bid_bot,
                    #         "bid_depth": curr_bid_depth,
                    #         "ask_depth": curr_ask_depth,
                    #         "bid_size": best_bid_size,
                    #         "ask_size": best_ask_size,
                    #         "near_trade_qty": near_trade_qty,
                    #         "near_trade_count": near_trade_count,
                    #     }
                    #     shadow_test["observations"].append(obs)

                    #     logger.print(
                    #         "[SHADOW_TICK]",
                    #         "start_ts=", shadow_test["start_ts"],
                    #         "age=", age,
                    #         "side=", shadow_test["side"],
                    #         "price=", shadow_test["price"],
                    #         "best_bid=", best_bid_bot,
                    #         "best_ask=", best_ask_bot,
                    #         "mid=", mid,
                    #         "micro=", microprice,
                    #         "spread=", best_ask_bot - best_bid_bot,
                    #         "near_trade_qty=", near_trade_qty,
                    #         "near_trade_count=", near_trade_count,
                    #         "would_cancel_if_top_next_tick=", shadow_test["would_cancel_if_top_next_tick"]
                    #     )

                    #     # -------------------------
                    #     # 3) close and summarize test
                    #     # -------------------------
                    #     if age >= TRACK_HORIZON:
                    #         end_best_bid = best_bid_bot
                    #         end_best_ask = best_ask_bot
                    #         end_mid = mid
                    #         end_micro = microprice

                    #         delta_bid = end_best_bid - shadow_test["start_best_bid"]
                    #         delta_ask = end_best_ask - shadow_test["start_best_ask"]
                    #         delta_mid = end_mid - shadow_test["start_mid"]
                    #         delta_micro = end_micro - shadow_test["start_micro"]

                    #         # heuristic reaction scores
                    #         if shadow_test["side"] == "BID":
                    #             quote_reaction = (
                    #                 (delta_bid > 0)
                    #                 or (delta_mid > 0)
                    #                 or (delta_micro > 0)
                    #             )
                    #         else:
                    #             quote_reaction = (
                    #                 (delta_ask < 0)
                    #                 or (delta_mid < 0)
                    #                 or (delta_micro < 0)
                    #             )

                    #         total_near_trade_qty = sum(x["near_trade_qty"] for x in shadow_test["observations"])
                    #         total_near_trade_count = sum(x["near_trade_count"] for x in shadow_test["observations"])

                    #         logger.print(
                    #             "[SHADOW_END]",
                    #             "start_ts=", shadow_test["start_ts"],
                    #             "side=", shadow_test["side"],
                    #             "price=", shadow_test["price"],
                    #             "size=", shadow_test["size"],
                    #             "delta_bid=", delta_bid,
                    #             "delta_ask=", delta_ask,
                    #             "delta_mid=", delta_mid,
                    #             "delta_micro=", delta_micro,
                    #             "quote_reaction=", quote_reaction,
                    #             "total_near_trade_qty=", total_near_trade_qty,
                    #             "total_near_trade_count=", total_near_trade_count,
                    #             "would_cancel_if_top_next_tick=", shadow_test["would_cancel_if_top_next_tick"]
                    #         )

                    #         shadow_test = None

                    # # =========================================================
                    # # FLICKER TAKE-THEN-MAKE (FAST EXIT VERSION)
                    # # =========================================================

                    # spoof_positions = data.get("tom_spoof_positions", [])

                    # # ---------------------------------------------------------
                    # # reconcile actual fills against outstanding spoof positions
                    # # ---------------------------------------------------------
                    # own_tom_trades = state.own_trades.get("TOMATOES", [])

                    # for spf in spoof_positions:
                    #     spf.setdefault("qty_open", spf.get("qty", 0))
                    #     spf.setdefault("exit_price", None)
                    #     spf.setdefault("entry_filled", False)
                    #     spf.setdefault("exit_age", 0)

                    # for fill in own_tom_trades:
                    #     fill_qty = abs(fill.quantity)
                    #     fill_price = fill.price

                    #     # our BUY filled
                    #     if fill.buyer == "SUBMISSION":
                    #         # entry fill for LONG spoof
                    #         for spf in spoof_positions:
                    #             if fill_qty <= 0:
                    #                 break
                    #             if (
                    #                 spf["side"] == "LONG"
                    #                 and not spf.get("entry_filled", False)
                    #                 and spf["entry_price"] == fill_price
                    #             ):
                    #                 matched = min(fill_qty, spf["qty_open"])
                    #                 spf["entry_filled"] = True
                    #                 fill_qty -= matched

                    #         # exit fill for SHORT spoof
                    #         for spf in spoof_positions:
                    #             if fill_qty <= 0:
                    #                 break
                    #             if (
                    #                 spf["side"] == "SHORT"
                    #                 and spf.get("exit_price") == fill_price
                    #                 and spf.get("qty_open", 0) > 0
                    #             ):
                    #                 matched = min(fill_qty, spf["qty_open"])
                    #                 spf["qty_open"] -= matched
                    #                 fill_qty -= matched

                    #     # our SELL filled
                    #     if fill.seller == "SUBMISSION":
                    #         # entry fill for SHORT spoof
                    #         for spf in spoof_positions:
                    #             if fill_qty <= 0:
                    #                 break
                    #             if (
                    #                 spf["side"] == "SHORT"
                    #                 and not spf.get("entry_filled", False)
                    #                 and spf["entry_price"] == fill_price
                    #             ):
                    #                 matched = min(fill_qty, spf["qty_open"])
                    #                 spf["entry_filled"] = True
                    #                 fill_qty -= matched

                    #         # exit fill for LONG spoof
                    #         for spf in spoof_positions:
                    #             if fill_qty <= 0:
                    #                 break
                    #             if (
                    #                 spf["side"] == "LONG"
                    #                 and spf.get("exit_price") == fill_price
                    #                 and spf.get("qty_open", 0) > 0
                    #             ):
                    #                 matched = min(fill_qty, spf["qty_open"])
                    #                 spf["qty_open"] -= matched
                    #                 fill_qty -= matched

                    # # keep only still-open spoof positions
                    # spoof_positions = [spf for spf in spoof_positions if spf.get("qty_open", 0) > 0]

                    # # ---------------------------------------------------------
                    # # 1) manage exits every tick until matched
                    # # ---------------------------------------------------------
                    # for spf in spoof_positions:
                    #     if not spf.get("entry_filled", False):
                    #         continue

                    #     qty_open = spf["qty_open"]
                    #     age = state.timestamp - spf["timestamp"]

                    #     # age == 100  -> first tick after entry
                    #     # age == 200  -> second tick after entry
                    #     # age >= 300  -> kill remaining inventory aggressively

                    #     if spf["side"] == "LONG" and sell_cap > 0:
                    #         exit_qty = min(qty_open, sell_cap)

                    #         if exit_qty > 0:
                    #             exit_price = best_bid_bot+1

                    #             orders.append(Order("TOMATOES", exit_price, -exit_qty))
                    #             sell_cap -= exit_qty
                    #             spf["exit_price"] = exit_price
                    #             spf["exit_age"] = age

                    #     elif spf["side"] == "SHORT" and buy_cap > 0:
                    #         exit_qty = min(qty_open, buy_cap)

                    #         if exit_qty > 0:
                    #             exit_price = best_ask_bot-1

                    #             orders.append(Order("TOMATOES", exit_price, exit_qty))
                    #             buy_cap -= exit_qty
                    #             spf["exit_price"] = exit_price
                    #             spf["exit_age"] = age

                    # # ---------------------------------------------------------
                    # # 2) fresh spoof entries
                    # # ---------------------------------------------------------
                    # if ask_flicker and buy_cap > 0:
                    #     spoof_qty = abs(sell_orders.get(flicker_ask_price, 0))
                    #     qty = min(spoof_qty, buy_cap)

                    #     if qty > 0:
                    #         orders.append(Order("TOMATOES", flicker_ask_price, qty))
                    #         buy_cap -= qty
                    #         pos += qty

                    #         spoof_positions.append({
                    #             "side": "LONG",
                    #             "qty": qty,
                    #             "qty_open": qty,
                    #             "timestamp": state.timestamp,
                    #             "entry_price": flicker_ask_price,
                    #             "entry_filled": False,
                    #             "exit_price": None,
                    #             "exit_age": 0,
                    #         })

                    # if bid_flicker and sell_cap > 0:
                    #     spoof_qty = buy_orders.get(flicker_bid_price, 0)
                    #     qty = min(spoof_qty, sell_cap)

                    #     if qty > 0:
                    #         orders.append(Order("TOMATOES", flicker_bid_price, -qty))
                    #         sell_cap -= qty
                    #         pos -= qty

                    #         spoof_positions.append({
                    #             "side": "SHORT",
                    #             "qty": qty,
                    #             "qty_open": qty,
                    #             "timestamp": state.timestamp,
                    #             "entry_price": flicker_bid_price,
                    #             "entry_filled": False,
                    #             "exit_price": None,
                    #             "exit_age": 0,
                    #         })

                    # logger.print("inventory=", pos, "open_spoofs=", spoof_positions)

                    # =========================================================
                    # SIMPLE MARKET MAKING
                    # =========================================================
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

                    spread = ask_price - bid_price

                    if not bid_flicker:
                        if buy_cap > 0:
                            orders.append(Order("TOMATOES", int(bid_price), buy_cap))
                    if not ask_flicker:
                        if sell_cap > 0:
                            orders.append(Order("TOMATOES", int(ask_price), -sell_cap))

                    
                    # =========================================================
                    # SAVE STATE
                    # =========================================================

                    data["tom_prev_bid_depth"]   = curr_bid_depth
                    data["tom_prev_ask_depth"]   = curr_ask_depth
                    data["tom_prev_buy_orders"]  = {str(p): q for p, q in buy_orders.items()}
                    data["tom_prev_sell_orders"] = {str(p): q for p, q in sell_orders.items()}
                    # data["tom_shadow_test"] = shadow_test
                    #data["tom_spoof_positions"] = spoof_positions

                    logger.print(
                        "inventory=", pos,
                        "bid_flicker=", bid_flicker,
                        "ask_flicker=", ask_flicker
                    )

                result["TOMATOES"] = orders

        except Exception as e:
            print("ERROR", e)
            print(traceback.format_exc())

        trader_data = json.dumps(data)
        logger.flush(state, result, conversions, trader_data)
        #logger.print(result)
        return result, conversions, trader_data