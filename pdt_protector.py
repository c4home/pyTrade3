from config import *
class PDTProtector:
    def __init__(self, db_manager):
        self.db = db_manager
        self.day_trades = collections.deque()
        self._load_history()

    def _load_history(self):
        self.day_trades.clear()
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        try:
            with self.db.get_cursor() as cur:
                cur.execute("""
                    SELECT t1.timestamp FROM trading_history t1
                    WHERE t1.action = 'SELL' AND t1.timestamp >= ?
                    AND t1.stock_id IN (
                        SELECT t2.stock_id FROM trading_history t2
                        WHERE t2.action = 'BUY' AND DATE(t2.timestamp) = DATE(t1.timestamp)
                    )
                    ORDER BY t1.timestamp ASC
                """, (cutoff,))
                rows = cur.fetchall()
                for row in rows:
                    dt = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                    self.day_trades.append(dt)
            logger.info(f"PDT Protector: Loaded {len(self.day_trades)} day trades from the last 7 days.")
        except Exception as e:
            logger.error(f"Failed to load PDT history: {e}")

    def _cleanup(self):
        cutoff = datetime.now() - timedelta(days=7)
        while self.day_trades and self.day_trades[0] < cutoff:
            self.day_trades.popleft()

    def count_day_trades_5d(self):
        self._cleanup()
        return len(self.day_trades)

    def register_day_trade_if_needed(self, symbol=None):
        self._load_history()

    def can_trade(self):
        count = self.count_day_trades_5d()
        if count >= 3:
            return False
        return True
