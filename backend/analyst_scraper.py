from config import *


class AnalystDataMixin:
    """Mixin thu thập mục tiêu giá (UBS, Barclays, Morgan Stanley, Yahoo Finance) và lịch sự kiện Earnings/Dividends."""

    def get_bank_note(self, run_async=True, force=False):
        fallback = None
        cached_data = self.db_manager.get_cached_bank_note(self.stock_id)

        if cached_data:
            target, source, est_date, last_upd = cached_data
            try:
                if '.' in last_upd:
                    last_upd_dt = datetime.strptime(last_upd, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    last_upd_dt = datetime.strptime(last_upd, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                last_upd_dt = datetime.min

            if (datetime.now() - last_upd_dt).total_seconds() < 86400 and not force:
                self.latest_bank_target = target
                self.latest_bank_source = source
                self.latest_bank_date = est_date
                return target, source, est_date
            else:
                fallback = (target, source, est_date)

        if run_async:
            if not getattr(self, '_fetching_bank_note', False):
                self._fetching_bank_note = True
                def async_fetch(_force=force):
                    try:
                        self.fetch_fresh_bank_note(fallback, force=_force)
                    finally:
                        self._fetching_bank_note = False
                executor.submit(async_fetch)

            if fallback:
                self.latest_bank_target = fallback[0]
                self.latest_bank_source = fallback[1]
                self.latest_bank_date = fallback[2]
                return fallback
            return None, "N/A", "--"
        else:
            return self.fetch_fresh_bank_note(fallback, force=force)

    def fetch_fresh_bank_note(self, fallback=None, max_age_hours=24, force=False):
        # 1. Check if we have recent cached data to avoid redundant API requests
        # Skip this check if force=True (e.g. user clicked the Update button)
        if self.db_manager and not force:
            cached_data = self.db_manager.get_cached_bank_note(self.stock_id)
            if cached_data:
                price, source, date_str, last_updated = cached_data
                if last_updated:
                    try:
                        if isinstance(last_updated, str):
                            if "." in last_updated:
                                last_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S.%f")
                            else:
                                last_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
                        else:
                            last_dt = last_updated

                        if (datetime.now() - last_dt).total_seconds() < (max_age_hours * 3600):
                            logger.info(f"Using cached analyst targets for {self.stock_id} (fetched < {max_age_hours}h ago)")
                            self.latest_bank_target = price
                            self.latest_bank_source = source
                            self.latest_bank_date = date_str
                            return price, source, date_str
                    except Exception as e:
                        logger.warning(f"Error parsing cache date for {self.stock_id}: {e}")

        logger.info(f"Fetching fresh analyst targets for {self.stock_id}...")
        firms = [
            ("Barclays", self.get_barclays_target),
            ("UBS", self.get_ubs_target),
            ("Morgan Stanley", self.get_morgan_stanley_target)
        ]

        valid_data = []
        for name, fetch_method in firms:
            try:
                result = fetch_method(self.stock_id)
                if result and len(result) == 3 and result[0] is not None:
                    price, _, date_str = result
                    valid_data.append({
                        "price": price,
                        "name": name,
                        "date_obj": datetime.strptime(date_str, '%Y-%m-%d'),
                        "date_str": date_str
                    })
            except Exception as e:
                logger.error(f"Error fetching from {name}: {e}")

        if valid_data:
            latest = sorted(valid_data, key=lambda x: x['date_obj'], reverse=True)[0]
            self.latest_bank_target = latest['price']
            self.latest_bank_source = latest['name']
            self.latest_bank_date = latest['date_str']

            self.db_manager.save_target_to_db(
                self.stock_id, self.latest_bank_target,
                self.latest_bank_source, self.latest_bank_date
            )
            return self.latest_bank_target, self.latest_bank_source, self.latest_bank_date

        if fallback:
            logger.info(f"API fetch failed. Using stale fallback for {self.stock_id}.")
            self.latest_bank_target = fallback[0]
            self.latest_bank_source = fallback[1]
            self.latest_bank_date = fallback[2]
            return fallback

        logger.info(f"No analyst data found for {self.stock_id}. Caching 'N/A' for 24h.")
        self.db_manager.save_target_to_db(self.stock_id, 0.0, "--", "--")
        self.latest_bank_target = 0.0
        self.latest_bank_source = "--"
        self.latest_bank_date = "--"
        return None, "N/A", "--"

    def fetch_next_event_date(self, ticker):
        # ---- 1. Earnings (only for stocks) --------------------------------
        if self.asset_type == "STOCK":
            # Try get_earnings_dates DataFrame
            try:
                ed = ticker.get_earnings_dates(limit=12)
                if ed is not None and not ed.empty:
                    now = pd.Timestamp.now(tz='UTC')
                    if ed.index.tz is not None:
                        now = pd.Timestamp.now(tz=ed.index.tz)
                    else:
                        now = pd.Timestamp.now()
                    future = ed[ed.index > now]
                    if not future.empty:
                        return future.index.min().strftime("%Y-%m-%d")
            except Exception as e:
                logger.error(f"[EARNINGS df] {self.stock_id}: {e}")

            # Try calendar dict as fallback
            try:
                cal = ticker.calendar
                if cal and 'Earnings Date' in cal:
                    dates = cal['Earnings Date']
                    if isinstance(dates, list) and len(dates) > 0:
                        return dates[0].strftime("%Y-%m-%d")
            except Exception as e:
                logger.error(f"[EARNINGS cal] {self.stock_id}: {e}")

        # ---- 2. Dividends (ETFs / ETCs / fallback for stocks) -------------
        try:
            # yfinance returns a DataFrame:  index = ex-dividend date
            div = ticker.dividends
            if div is not None and not div.empty:
                # keep only future dates (today + later)
                now = pd.Timestamp.now(tz='UTC')
                future_div = div[div.index > now]
                if not future_div.empty:
                    # the *ex-dividend* date is the one that matters for the trader
                    return future_div.index.min().strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"[DIVIDENDS] {self.stock_id}: {e}")

        # ---- 3. Nothing found --------------------------------------------
        return None

    def update_analyst_data(self, run_async=True):
        # 1. Skip for assets without analyst coverage
        if self.asset_type in ["ETF", "ETC"]:
            self.analyst_data = []
            return

        # 2. Get Bank Data (Tier 1)
        bank_target, bank_source, bank_date = self.get_bank_note(run_async=run_async)

        # 3. Get yfinance Data (Tier 2) + Estimate Date
        try:
            yf_target = getattr(self, 'target_price', 0)
            yf_date = datetime.now().strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Failed to fetch yf target for {self.stock_id}: {e}")
            yf_target = 0
            yf_date = "--"

        # 4. Consolidate
        self.analyst_data = []
        if bank_target:
            self.analyst_data.append({"source": bank_source, "target": bank_target, "date": bank_date, "tier": 1})
        if yf_target:
            self.analyst_data.append({"source": "yfinance", "target": yf_target, "date": yf_date, "tier": 2})

    def get_barclays_target(self, symbol):
        ticker = yf.Ticker(symbol)
        df = ticker.upgrades_downgrades

        if df is None or df.empty:
            return None, "No analyst history found.", "N/A"

        # Filter for Barclays
        barclays_names = ['barclays', 'barclays capital', 'barclays plc']
        barclays_data = df[df['Firm'].str.lower().isin(barclays_names)]

        if barclays_data.empty:
            return None, "Barclays does not cover this stock.", "N/A"

        # Get latest entry
        latest_action = barclays_data.sort_index().iloc[-1]

        # --- NEW: Extract the Date ---
        # .name gets the index value (the timestamp)
        date_str = latest_action.name.strftime('%Y-%m-%d')

        target_val = latest_action.get('currentPriceTarget')

        if pd.notnull(target_val) and target_val != 0:
            return float(target_val), f"Target: ${float(target_val)}", date_str
        else:
            grade = latest_action.get('ToGrade', 'N/A')
            return None, f"Rating: {grade}", date_str

    def get_ubs_target(self, symbol):
        """
        Scrape UBS research page for price target with robust parsing.
        Step 1: Try yfinance upgrades/downgrades (fast, cached).
        Step 2: Fall back to UBS research web scraping if yfinance is missing/stale.
        Returns: (target_price, description, date_string) or (None, error_msg, None)
        """
        # Step 1: Try yfinance first
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.upgrades_downgrades
            if df is not None and not df.empty:
                ubs_names = ['ubs', 'ubs group', 'ubs ag']
                ubs_data = df[df['Firm'].str.lower().isin(ubs_names)]
                if not ubs_data.empty:
                    latest = ubs_data.sort_index().iloc[-1]
                    target_val = latest.get('currentPriceTarget')
                    date_str = latest.name.strftime('%Y-%m-%d')
                    if pd.notnull(target_val) and target_val != 0:
                        days_old = (datetime.now() - latest.name.to_pydatetime().replace(tzinfo=None)).days
                        if days_old <= 30:
                            logger.info(f"[UBS yfinance] {symbol} target ${target_val} is fresh ({days_old}d old). Using it.")
                            return float(target_val), f"Target: ${float(target_val)}", date_str
                        else:
                            logger.info(f"[UBS yfinance] {symbol} target is stale ({days_old}d old). Trying web scrape for fresher data...")
        except Exception as e:
            logger.warning(f"yfinance UBS lookup failed for {symbol}: {e}")

        # Step 2: Web scraping fallback for stocks with known UBS research URLs
        logger.info(f"Attempting UBS web scrape for {symbol}...")

        # Load UBS URL map from assets/ubs_links.json (edit that file to add new stocks)
        _ubs_links_path = os.path.join(PROJECT_ROOT, 'assets', 'ubs_links.json')
        try:
            import json
            with open(_ubs_links_path, 'r') as _f:
                ubs_url_map = {k: v for k, v in json.load(_f).items() if not k.startswith('_')}
        except Exception as _e:
            logger.warning(f"Could not load ubs_links.json: {_e}")
            ubs_url_map = {}

        url = ubs_url_map.get(symbol)
        if not url:
            return None, "No UBS URL mapping", None

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            }
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}", None

            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table')
            if not table:
                return None, "No table found on UBS page", None

            rows = table.find_all('tr')[1:]  # Skip header
            if not rows:
                return None, "No data rows on UBS page", None

            # Latest data is in the last row; structure: Date | Price | Target | Rating
            latest_row = rows[-1]
            cols = latest_row.find_all('td')
            if len(cols) < 3:
                return None, "Unexpected UBS table structure", None

            date = cols[0].get_text(strip=True)
            target_price_str = cols[2].get_text(strip=True).replace(',', '').replace('€', '').replace('$', '').strip()

            target_price = float(target_price_str)
            logger.info(f"[UBS Scrape] {symbol} Target: {target_price} (Date: {date})")
            return target_price, f"Target: {target_price}", date

        except (ValueError, IndexError) as e:
            logger.error(f"UBS scrape parse error for {symbol}: {e}")
            return None, "Scrape parse failure", None
        except Exception as e:
            logger.error(f"UBS scrape request error for {symbol}: {e}")
            return None, f"Scrape error: {e}", None

    def get_morgan_stanley_target(self, symbol):
        ticker = yf.Ticker(symbol)
        df = ticker.upgrades_downgrades

        if df is None or df.empty:
            return None, "No analyst history found."

        # Filter for Morgan Stanley
        ms_names = ['morgan stanley', 'morgan stanley & co.']
        ms_data = df[df['Firm'].str.lower().isin(ms_names)]

        if ms_data.empty:
            return None, "Morgan Stanley does not cover this stock."

        # Get latest entry and extract currentPriceTarget
        latest = ms_data.sort_index().iloc[-1]
        target_val = latest.get('currentPriceTarget')
        date_str = latest.name.strftime('%Y-%m-%d')

        if pd.notnull(target_val) and target_val != 0:
            return float(target_val), f"Target: ${float(target_val)}", date_str
        else:
            grade = latest.get('ToGrade', 'N/A')
            return None, f"Rating: {grade}", date_str
