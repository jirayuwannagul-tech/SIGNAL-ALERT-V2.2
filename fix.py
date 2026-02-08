import json
with open("app/services/signal_detector.py", "r") as f:
    content = f.read()

# เพิ่ม default settings
content = content.replace(
    'self.indicator_settings = config.get("INDICATORS", {})',
    '''self.indicator_settings = config.get("INDICATORS", {
            "squeeze": {"length": 20, "bb_mult": 2.0, "kc_mult": 1.5},
            "macd": {"fast": 8, "slow": 17, "signal": 9}, 
            "rsi": {"period": 14, "oversold": 40, "overbought": 60}
        })'''
)

with open("app/services/signal_detector.py", "w") as f:
    f.write(content)
print("Fixed!")
