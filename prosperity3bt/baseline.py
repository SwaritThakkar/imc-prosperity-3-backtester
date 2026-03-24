from typing import List, Tuple, Dict
import traceback
import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState



class Trader:
    def run(self, state: TradingState):

        result = {}
        conversions = 0
        trader_data = ""

        try:

            # ===========================
            # EMERALDS
            # ===========================

            if "EMERALDS" in state.order_depths:

                orders = []

                od = state.order_depths["EMERALDS"]

                LIMIT = 80
                FAIR = 10000

                current_pos = state.position.get("EMERALDS", 0)

                if od.sell_orders:
                    for ask_price in sorted(od.sell_orders.keys()):
                        if ask_price <= FAIR:
                            vol = abs(od.sell_orders[ask_price])
                            qty = min(vol, LIMIT - current_pos)
                            if qty > 0:
                                orders.append(Order("EMERALDS", ask_price, qty))
                                current_pos += qty

                if od.buy_orders:
                    for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                        if bid_price >= FAIR:
                            vol = od.buy_orders[bid_price]
                            qty = min(vol, LIMIT + current_pos)
                            if qty > 0:
                                orders.append(Order("EMERALDS", bid_price, -qty))
                                current_pos -= qty

                buy_capacity = LIMIT - current_pos
                sell_capacity = LIMIT + current_pos

                place_bid = True
                place_ask = True

                best_bid = 9993
                best_ask = 10007

                if current_pos > 70:
                    place_bid = False
                    best_ask = 10002

                elif current_pos > 40:
                    best_bid = 9995
                    best_ask = 10004

                elif current_pos < -70:
                    place_ask = False
                    best_bid = 9998

                elif current_pos < -40:
                    best_bid = 9996
                    best_ask = 10005

                if place_bid and buy_capacity > 0:
                    orders.append(Order("EMERALDS", best_bid, buy_capacity))

                if place_ask and sell_capacity > 0:
                    orders.append(Order("EMERALDS", best_ask, -sell_capacity))

                result["EMERALDS"] = orders

            # ===========================
            # TOMATOES
            # ===========================

            if "TOMATOES" in state.order_depths:

                orders = []

                od = state.order_depths["TOMATOES"]

                pos = state.position.get("TOMATOES", 0)

                LIMIT = 80

                if od.buy_orders and od.sell_orders:

                    best_bid_bot = max(od.buy_orders.keys())
                    best_ask_bot = min(od.sell_orders.keys())

                    buy_cap = LIMIT - pos
                    sell_cap = LIMIT + pos

                    my_bid = best_bid_bot + 1
                    my_ask = best_ask_bot - 1

                    if pos > 20:
                        my_bid = best_bid_bot
                        my_ask = best_ask_bot - 2

                    if pos > 60:
                        my_bid = 1
                        my_ask = best_ask_bot - 3

                    if pos < -20:
                        my_ask = best_ask_bot
                        my_bid = best_bid_bot + 2

                    if pos < -60:
                        my_ask = 100000
                        my_bid = best_bid_bot + 3

                    my_bid = min(my_bid, best_ask_bot - 1)
                    my_ask = max(my_ask, best_bid_bot + 1)

                    if my_bid >= my_ask:
                        my_bid = my_ask - 1

                    if buy_cap > 0 and my_bid > 0:
                        orders.append(Order("TOMATOES", my_bid, buy_cap))

                    if sell_cap > 0 and my_ask < 100000:
                        orders.append(Order("TOMATOES", my_ask, -sell_cap))

                result["TOMATOES"] = orders

        except Exception as e:
            print("ERROR", e)
            print(traceback.format_exc())

        return result, conversions, trader_data

#changed