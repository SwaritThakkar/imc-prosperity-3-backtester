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

                    mid = (best_bid_bot + best_ask_bot) / 2

                    prev_mid = data.get("tom_prev", mid)

                    diff = mid - prev_mid
                    buy_cap = LIMIT - pos
                    sell_cap = LIMIT + pos


                    # ===========================
                    # 1. TAKING (same as EMERALDS)
                    # ===========================

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


                    # ===========================
                    # 2. MAKING (same as EMERALDS)
                    # ===========================

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
                        orders.append(Order("TOMATOES", int(bid_price), buy_cap))

                    if sell_cap > 0:
                        orders.append(Order("TOMATOES", int(ask_price), -sell_cap))


                    # ===========================
                    # 3. DIRECTIONAL SIGNAL (your diff)
                    # ===========================

                    # if 10 <= diff <= 72:

                    #     qty = min(5, LIMIT + pos)

                    #     if qty > 0:
                    #         orders.append(Order("TOMATOES", best_bid_bot, -qty))


                    # elif -72 <= diff <= -48:

                    #     qty = min(5, LIMIT - pos)

                    #     if qty > 0:
                    #         orders.append(Order("TOMATOES", best_ask_bot, qty))


                    # else:

                    #     if pos > 0:
                    #         orders.append(Order("TOMATOES", best_bid_bot, -1))

                    #     elif pos < 0:
                    #         orders.append(Order("TOMATOES", best_ask_bot, 1))


    


                    # -----------------------
                    # save price
                    # -----------------------

                    data["tom_prev"] = mid
                    # trader_data = json.dumps(data)

                result["TOMATOES"] = orders

        except Exception as e:
            print("ERROR", e)
            print(traceback.format_exc())

        trader_data = json.dumps(data)
        return result, conversions, trader_data