import pandas as pd
import numpy as np
from itertools import product

FILE = "tomatoes_price_diff.csv"


# -----------------------
# load safely
# -----------------------

def read_csv(path):

    with open(path, "r") as f:
        first = f.readline()

    sep = ";" if first.count(";") > first.count(",") else ","

    df = pd.read_csv(path, sep=sep)

    df.columns = df.columns.str.lower().str.strip()

    return df


df = read_csv(FILE)

print("Columns:", df.columns)
print("Rows:", len(df))


if "mid_price" not in df.columns:
    raise Exception("mid_price column not found")


df["mid_price"] = pd.to_numeric(df["mid_price"], errors="coerce")

df = df.dropna(subset=["mid_price"])

print("Rows after clean:", len(df))


if len(df) == 0:
    raise Exception("Dataframe empty after cleaning")


# -----------------------
# EMA
# -----------------------

alpha = 0.2

ema = []
e = df["mid_price"].iloc[0]

for x in df["mid_price"]:
    e = alpha * x + (1 - alpha) * e
    ema.append(e)

df["ema"] = ema


# -----------------------
# micro (approx)
# -----------------------

df["micro"] = df["mid_price"]


# -----------------------
# last price
# -----------------------

df["last"] = df["mid_price"].shift(1)

df["future"] = df["mid_price"].shift(-1)

df = df.dropna(subset=["mid_price", "ema", "last", "future"])

print("Rows for search:", len(df))


# -----------------------
# search weights
# -----------------------

best_score = -1e9
best = None

steps = np.arange(0, 1.01, 0.05)

for a in steps:
    for b in steps:

        c = 1 - a - b

        if c < 0 or c > 1:
            continue

        fair = (
            a * df["micro"]
            + b * df["ema"]
            + c * df["last"]
        )

        predict = fair - df["mid_price"]
        target = df["future"] - df["mid_price"]

        corr = np.corrcoef(predict, target)[0, 1]

        if np.isnan(corr):
            continue

        if corr > best_score:
            best_score = corr
            best = (a, b, c)

print("BEST:", best)
print("CORR:", best_score)