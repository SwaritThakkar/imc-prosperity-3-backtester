import json

inp = "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/backtests/2026-03-26_14-18-23.log"
out = "/Users/swaritthakkar/Documents/GitHub/imc-prosperity-3-backtester/backtests/1.log"


with open(inp, "r") as f:
    content = f.read()

# split objects safely
objects = content.split("}\n{")

clean_objects = []

for i, obj in enumerate(objects):

    if not obj.strip():
        continue

    if not obj.startswith("{"):
        obj = "{" + obj

    if not obj.endswith("}"):
        obj = obj + "}"

    try:
        data = json.loads(obj)
        clean_objects.append(data["lambdaLog"])
    except Exception as e:
        print("skip", i, e)


with open(out, "w") as f:
    for line in clean_objects:
        f.write(line + "\n")

print("done → good.log")