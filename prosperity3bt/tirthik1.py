from typing import List, Tuple, Dict
import traceback
import numpy as np
from datamodel import Order, OrderDepth, TradingState


class Trader:

    def __init__(self):
        self.prices = []

    # =========================
    # SIGNALS
    # =========================
    def compute_ema(self, prices, span=8):
        if len(prices) == 0:
            return 0
        alpha = 2 / (span + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = alpha * p + (1 - alpha) * ema
        return ema

    # =========================
    # MAIN
    # =========================
    def run(self, state: TradingState):

        result = {}
        conversions = 0
        trader_data = ""

        try:

            # ===========================
            # EMERALDS (UNCHANGED)
            # ===========================

            if "EMERALDS" in state.order_depths:

                orders = []
                od = state.order_depths["EMERALDS"]

                LIMIT = 80
                FAIR = 10000

                best_bid_bot = max(od.buy_orders.keys())
                best_ask_bot = min(od.sell_orders.keys())

                current_pos = state.position.get("EMERALDS", 0)

                for ask_price in sorted(od.sell_orders.keys()):
                    if ask_price <= FAIR:
                        vol = abs(od.sell_orders[ask_price])
                        qty = min(vol, LIMIT - current_pos)
                        if qty > 0:
                            orders.append(Order("EMERALDS", ask_price, qty))
                            current_pos += qty

                for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                    if bid_price >= FAIR:
                        vol = od.buy_orders[bid_price]
                        qty = min(vol, LIMIT + current_pos)
                        if qty > 0:
                            orders.append(Order("EMERALDS", bid_price, -qty))
                            current_pos -= qty

                buy_capacity = LIMIT - current_pos
                sell_capacity = LIMIT + current_pos

                best_bid = best_bid_bot + 1
                best_ask = best_ask_bot - 1

                if buy_capacity > 0:
                    orders.append(Order("EMERALDS", best_bid, buy_capacity))

                if sell_capacity > 0:
                    orders.append(Order("EMERALDS", best_ask, -sell_capacity))

                result["EMERALDS"] = orders

            # ===========================
            # TOMATOES (FIXED STRATEGY)
            # ===========================

            if "TOMATOES" in state.order_depths:

                orders = []
                od = state.order_depths["TOMATOES"]

                pos = state.position.get("TOMATOES", 0)
                LIMIT = 80

                if od.buy_orders and od.sell_orders:

                    best_bid = max(od.buy_orders.keys())
                    best_ask = min(od.sell_orders.keys())
                    mid = (best_bid + best_ask) / 2

                    self.prices.append(mid)

                    # WAIT FOR ENOUGH DATA (NO RETURN BUG)
                    if len(self.prices) < 20:
                        result["TOMATOES"] = orders

                    # =========================
                    # SIGNALS
                    # =========================

                    ema_now = self.compute_ema(self.prices[-16:-1], 4)
                    ema_prev = self.compute_ema(self.prices[-16:-1], 8)

                    trend = ema_now - ema_prev

                    std = np.std(self.prices[-20:]) + 1e-9
                    z = (mid - ema_now) / std

                    print(f"Z: {z:.2f}, Trend: {trend:.4f}, Pos: {pos}")

                    buy_cap = LIMIT - pos
                    sell_cap = LIMIT + pos

                    # =========================
                    # ENTRY (RELAXED)
                    # =========================

                    # BUY dips in uptrend
                    if trend > 0 and z < -1.2 and buy_cap > 0:

                        strength = min(abs(z) / 2, 1)
                        target_pos = int(LIMIT * strength)

                        desired = target_pos - pos
                        volume = min(desired, buy_cap)

                        if volume >= 2:
                            orders.append(Order("TOMATOES", best_ask, volume))

                    # SELL rallies in downtrend
                    elif trend < 0 and z > 1.2 and sell_cap > 0:

                        strength = min(abs(z) / 2, 1)
                        target_pos = -int(LIMIT * strength)

                        desired = target_pos - pos
                        volume = min(abs(desired), sell_cap)

                        if volume >= 2:
                            orders.append(Order("TOMATOES", best_bid, -volume))

                    # =========================
                    # EXIT (FASTER)
                    # =========================

                    elif pos > 0 and z > -0.3:
                        orders.append(Order("TOMATOES", best_bid, -pos))

                    elif pos < 0 and z < 0.3:
                        orders.append(Order("TOMATOES", best_ask, -pos))

                result["TOMATOES"] = orders

        except Exception as e:
            print("ERROR", e)
            print(traceback.format_exc())

        return result, conversions, trader_data