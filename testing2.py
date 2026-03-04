import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime

class BarclaysTargetFinder:
    def __init__(self):
        self.barclays_url_map = {
            'SAF.PA': 'https://publicresearch.barclays.com/eq/20011416.htm',
            # Add more symbols here if you discover their Barclays report IDs
            # Example: 'ASML.AS': 'https://publicresearch.barclays.com/eq/XXXXXXX.htm',
        }
    
    def get_barclays_target(self, symbol):
        # Step 1: Try yfinance first (fast and reliable when available)
        ticker = yf.Ticker(symbol)
        df = ticker.upgrades_downgrades
        
        if df is not None and not df.empty:
            barclays_names = ['barclays', 'barclays capital', 'barclays plc']
            barclays_data = df[df['Firm'].str.lower().isin(barclays_names)]
            
            if not barclays_data.empty:
                latest_action = barclays_data.sort_index().iloc[-1]
                date_str = latest_action.name.strftime('%Y-%m-%d')
                target_val = latest_action.get('currentPriceTarget')
                
                if pd.notnull(target_val) and target_val != 0:
                    return float(target_val), f"Target: €{float(target_val):.2f} (yfinance)", date_str
                else:
                    grade = latest_action.get('ToGrade', 'N/A')
                    return None, f"Rating: {grade} (yfinance)", date_str
        
        # Step 2: Fallback to direct Barclays scraping if symbol is in map
        symbol_upper = symbol.upper()
        if symbol_upper in self.barclays_url_map:
            return self._scrape_barclays_page(self.barclays_url_map[symbol_upper])
        else:
            return None, f"No Barclays data for {symbol}", "N/A"
    
    def _scrape_barclays_page(self, report_url):
        """Scrape the Barclays price table from the hidden priceTable endpoint"""
        try:
            price_table_url = report_url.replace('/eq/', '/priceTable/').replace('.htm', '') + '.htm'
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(price_table_url, headers=headers, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table')
            if not table:
                return None, "No price table found", "N/A"
            
            rows = table.find_all('tr')[1:]  # Skip header
            
            # Find the most recent row with a price target (Barclays tables are newest first)
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    date = cols[0].get_text(strip=True)
                    price_target = cols[3].get_text(strip=True).strip()
                    
                    if price_target:
                        # Clean price (remove €, commas, etc.)
                        price_clean = re.sub(r'[^\d.]', '', price_target)
                        if price_clean:
                            return float(price_clean), f"Target: €{price_clean} (Barclays scrape)", date
            
            return None, "No price target found in table", "N/A"
                
        except Exception as e:
            logger.error(f"Barclays scrape error for {report_url}: {e}")
            return None, f"Scrape error: {str(e)}", "N/A"
