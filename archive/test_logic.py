class Bot:
    def __init__(self, qty, score, is_saf=False):
        self.quantity = qty
        self.smart_score = score
        self.is_saf = is_saf

bots = {
    'ARM': Bot(0, 12),
    'QCOM': Bot(0, 12),
    'SAF': Bot(0, 7, True)
}

saf_bot = bots['SAF']
highest_score = max([b.smart_score for b in bots.values() if b.quantity <= 0], default=0)

print(f"Highest Score: {highest_score}")
print(f"SAF Score: {saf_bot.smart_score}")
if saf_bot.smart_score < highest_score:
    print("SAF returned None!")
else:
    print("SAF bypassed the block!")
