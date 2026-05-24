from config import *
# ==================== EXCHANGE RATE ====================
class ExchangeRateManager:
    def __init__(self):
        self.rates = {
            "USD": 1.08,
            "GBP": 0.85,
            "CAD": 1.48,
            "HKD": 8.50,
            "EUR": 1.0
        }
        self.last_update = 0
        self.update_interval = 3600

    @property
    def eur_usd_rate(self):
        return self.rates.get("USD", 1.08)

    @eur_usd_rate.setter
    def eur_usd_rate(self, value):
        self.rates["USD"] = value

    def get_eur_usd_rate(self):
        return self.get_rate("USD")

    def get_rate(self, currency):
        currency = currency.upper()
        if currency == "EUR":
            return 1.0
        
        now = time.time()
        if now - self.last_update >= self.update_interval:
            self.last_update = now
            def fetch():
                for curr in ["USD", "GBP", "CAD", "HKD"]:
                    try:
                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/EUR{curr}=X"
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            price = data['chart']['result'][0]['meta']['regularMarketPrice']
                            new_rate = float(price)
                            if new_rate > 0:
                                self.rates[curr] = round(new_rate, 4)
                    except Exception as e:
                        pass
            executor.submit(fetch)

        return self.rates.get(currency, 1.0)

    def eur_to_native(self, eur_amount, currency):
        if currency.upper() == 'EUR':
            return eur_amount
        return eur_amount * self.get_rate(currency)

    def get_currency_symbol(self, currency="USD"):
        """Return $, €, £, or HK$ based on currency"""
        currency = currency.upper()
        if currency == "EUR":
            return "€"
        elif currency == "GBP":
            return "£"
        elif currency == "HKD":
            return "HK$"
        return "$"

