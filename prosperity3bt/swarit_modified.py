import json
import numpy as np
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    
    POSITION_LIMIT = {
        "EMERALDS": 80,
        "TOMATOES": 80,
    }

    def __init__(self):
        self.price_history = {"EMERALDS": [], "TOMATOES": []}
        self.inventory_pressure = {"EMERALDS": 0}
        self.liquidity_history = {"bid": [], "ask": []}

    # =========================
    # HELPERS
    # =========================

    def fair_price(self, product):
        hist = self.price_history[product]
        if len(hist) < 5: return hist[-1] if hist else 0
        return np.median(hist[-5:])

    def volatility(self, product):
        hist = self.price_history[product]
        if len(hist) < 10: return 1
        return np.std(hist[-10:]) + 0.1

    def find_thin_levels(self, order_depth):
        bids = sorted(order_depth.buy_orders.items(), reverse=True)
        asks = sorted(order_depth.sell_orders.items())

        thin_bid = bids[0][0]
        thin_ask = asks[0][0]

        for price, vol in bids[:3]:
            if abs(vol) <= 8:
                thin_bid = price
                break

        for price, vol in asks[:3]:
            if abs(vol) <= 8:
                thin_ask = price
                break

        return thin_bid, thin_ask

    def get_imbalance(self, order_depth):
        bid_volume = sum(order_depth.buy_orders.values())
        ask_volume = -sum(order_depth.sell_orders.values())
        total = bid_volume + ask_volume
        return (bid_volume - ask_volume) / total if total != 0 else 0

    def detect_liquidity_shift(self, order_depth):
        bid_volume = sum(order_depth.buy_orders.values())
        ask_volume = -sum(order_depth.sell_orders.values())

        self.liquidity_history["bid"].append(bid_volume)
        self.liquidity_history["ask"].append(ask_volume)

        if len(self.liquidity_history["bid"]) > 5:
            self.liquidity_history["bid"].pop(0)
            self.liquidity_history["ask"].pop(0)

        if len(self.liquidity_history["bid"]) < 5:
            return 0

        bid_trend = self.liquidity_history["bid"][-1] - self.liquidity_history["bid"][0]
        ask_trend = self.liquidity_history["ask"][-1] - self.liquidity_history["ask"][0]

        if bid_trend < -8: return -1
        if ask_trend < -8: return +1
        return 0

    # =========================
    # CORE LOGIC
    # =========================

    def trade_product(self, product, order_depth, position):
        orders = []
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid = (best_bid + best_ask) / 2
        self.price_history[product].append(mid)

        limit = self.POSITION_LIMIT.get(product, 0)
        
        # We use a state tracker so we never exceed 80 total
        current_capacity_buy = limit - position
        current_capacity_sell = limit + position
        
        consolidated_buys = {}
        consolidated_sells = {}

        # Safe Helper function to track limits automatically
        def safe_buy(price, qty):
            nonlocal current_capacity_buy
            qty = min(qty, current_capacity_buy)
            if qty > 0:
                consolidated_buys[price] = consolidated_buys.get(price, 0) + qty
                current_capacity_buy -= qty

        def safe_sell(price, qty):
            nonlocal current_capacity_sell
            qty = min(qty, current_capacity_sell)
            if qty > 0:
                consolidated_sells[price] = consolidated_sells.get(price, 0) + qty
                current_capacity_sell -= qty

        # =========================
        # EMERALDS (BOT 8 FIXED)
        # =========================
        if product == "EMERALDS":

            if abs(position) > 40:
                self.inventory_pressure[product] += (position / 10)
            else:
                self.inventory_pressure[product] = 0

            pressure = self.inventory_pressure[product]

            bid_volume = sum(order_depth.buy_orders.values())
            ask_volume = -sum(order_depth.sell_orders.values())
            liquidity = bid_volume + ask_volume

            if liquidity > 30:
                base_size = 55
            elif liquidity > 15:
                base_size = 45
            else:
                base_size = 35

            skew = position / limit

            buy_size = base_size * (1 - skew)
            sell_size = base_size * (1 + skew)

            # 🔥 FIXED PRESSURE CAP
            if position > 40:
                sell_size *= (1 + min(abs(pressure), 3.0))
            elif position < -40:
                buy_size *= (1 + min(abs(pressure), 3.0))

            buy_size = int(max(0, min(round(buy_size), current_capacity_buy)))
            sell_size = int(max(0, min(round(sell_size), current_capacity_sell)))

        
            if buy_size > 0:
                safe_buy(best_bid + 1, int(buy_size * 0.6))
                safe_buy(best_bid, int(buy_size * 0.4))

            if sell_size > 0:
                safe_sell(best_ask - 1, int(sell_size * 0.6))
                safe_sell(best_ask, int(sell_size * 0.4))

        # =========================
        # TOMATOES (BOT 12)
        # =========================
        if product == "TOMATOES":
            imbalance = self.get_imbalance(order_depth)
            thin_bid, thin_ask = self.find_thin_levels(order_depth)
            liq_signal = self.detect_liquidity_shift(order_depth)

            aggression = max(1.0, 6 * (1 - abs(position) / limit))
            scaled_size = int(round(10 * aggression))
            # BUG 3 FIX: Guarantee we never cross our own spread
            bid_price = min(thin_bid + 1, best_ask - 1)
            ask_price = max(thin_ask - 1, best_bid + 1) 

            # 1. BASE MM (BUG 2 FIX: Using actual bid_price/ask_price)
            safe_buy(bid_price, scaled_size)
            safe_sell(ask_price, scaled_size)

            # 2. CONTROLLED PRE-SPIKE
            if abs(imbalance) > 0.2:
                boost = int(round(1.5 * scaled_size))
                if liq_signal == 1:
                    safe_buy(bid_price, boost)
                elif liq_signal == -1:
                    safe_sell(ask_price, boost)

            # 3. SOFT INVENTORY UNWIND
            if abs(position) > 60:
                unwind_size = int(round(abs(position) * 0.5))
                if position > 0:
                    safe_sell(best_bid, unwind_size) # Sells aggressively into the bid
                else:
                    safe_buy(best_ask, unwind_size)

            # 4. MICRO PROFIT TAKE
            fair = self.fair_price(product)
            if position > 0 and best_bid > fair:
                safe_sell(best_bid, 10)
            if position < 0 and best_ask < fair:
                safe_buy(best_ask, 10)

        # Map consolidations back to Engine format
        for p, q in consolidated_buys.items(): orders.append(Order(product, p, q))
        for p, q in consolidated_sells.items(): orders.append(Order(product, p, -q))
        
        return orders


    # =========================
    # RUN (UNCHANGED)
    # =========================

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        traderData = ""

        for product in state.order_depths:
            position = state.position.get(product, 0)
            result[product] = self.trade_product(product, state.order_depths[product], position)

        shadow_book = []
        for symbol, orders in result.items():
            for order in orders:
                shadow_book.append({
                    "symbol": symbol,
                    "price": order.price,
                    "quantity": order.quantity,
                    "type": "BUY" if order.quantity > 0 else "SELL"
                })

        if shadow_book:
            print(f"SHADOW_BOOK:{state.timestamp}:{json.dumps(shadow_book)}")

        return result, conversions, traderData