# ==============================================================================
# pyTrade3 — AlphaCreation Engine (alpha_engine.py)
# Stage 2 in Lean Architecture: Quantitative Scoring & Strategy Signal Generation
# ==============================================================================

from datetime import datetime
from typing import List, Dict, Tuple, Optional
from .models import MarketSnapshot, AlphaSignal

class AlphaEngine:
    """
    Mathematical Alpha Engine implementing DIP and MOMENTUM quantitative scoring.
    Synced 100% with AGENTS.md and core_backtest_engine.py.
    """
    DIP_BASE_MIN = 5      # DIP: RSI+BB+Trend raw points must be >= 5
    MOM_BASE_MIN = 6      # MOMENTUM: MACD+ADX+Vol+RSI raw points must be >= 6
    DIP_SMART_MIN = 7     # DIP trigger threshold
    MOM_SMART_MIN = 8     # MOMENTUM trigger threshold

    @staticmethod
    def calculate_analyst_modifier(analyst_data: Optional[List[Dict]], market_value: float) -> Tuple[int, str]:
        """Calculates score modifier (-2 to +3) based on analyst consensus and authority tiers."""
        if not analyst_data or market_value <= 0:
            return 0, ""

        total_weight = 0.0
        weighted_sum = 0.0
        now = datetime.now()

        for entry in analyst_data:
            if not entry.get('target') or not entry.get('date') or entry['date'] == "--":
                continue

            try:
                target_date = datetime.strptime(entry['date'], "%Y-%m-%d")
                days_old = (now - target_date).days
                if days_old > 90:
                    continue

                recency_multiplier = max(0.1, (90 - days_old) / 90.0)
                source_weight = 2.0 if entry.get('tier') == 1 else 1.0
                combined_weight = recency_multiplier * source_weight

                weighted_sum += float(entry['target']) * combined_weight
                total_weight += combined_weight
            except (ValueError, TypeError):
                continue

        if total_weight == 0:
            return 0, ""

        weighted_target = weighted_sum / total_weight
        upside_pct = (weighted_target - market_value) / market_value

        modifier = 0
        note = ""
        if upside_pct > 0.20:
            modifier = 3 if total_weight > 2.0 else 2
            note = f", Analyst: {modifier:+d} (Strong-Upside)"
        elif upside_pct > 0.10:
            modifier = 1
            note = ", Analyst: +1 (Fair-Upside)"
        elif upside_pct < -0.05:
            modifier = -2
            note = ", Analyst: -2 (Overvalued)"

        return modifier, note

    @classmethod
    def calculate_score(
        cls,
        snapshot: MarketSnapshot,
        analyst_data: Optional[List[Dict]] = None,
        cached_bank_note: Optional[Tuple] = None
    ) -> AlphaSignal:
        """
        Calculates the Smart Score (0-12) using multi-factor analysis.
        Follows Section 2 of AGENTS.md.
        """
        if snapshot.high_14d <= 0 or snapshot.market_price <= 0:
            return AlphaSignal(
                strategy="DIP",
                smart_score=0,
                base_score=0,
                target_upside_pct=0.0,
                score_reason="Insufficient Data",
                qualifies=False
            )

        market_val = snapshot.market_price
        ma200 = snapshot.ma200
        score_reason = ""
        target_upside_pct = 0.0

        # --- STEP 1: MARKET STRUCTURE CONTEXT (0 to +3) ---
        trend_score = 0
        if market_val > ma200:
            trend_score = 3
        elif market_val > snapshot.previous_close:
            trend_score = 1

        # --- STRATEGY A: DIP BUYER (Max 10 Points) ---
        dip_points = 0
        dip_details = []

        # 1. RSI Oversold (Max 4 Pts)
        if snapshot.rsi < 25:
            dip_points += 4
            dip_details.append("RSI<25: +4")
        elif snapshot.rsi < 30:
            dip_points += 3
            dip_details.append("RSI<30: +3")
        elif snapshot.rsi < 40:
            dip_points += 2
            dip_details.append("RSI<40: +2")

        # 2. Bollinger Bands (Max 3 Pts)
        if snapshot.bb_pct_b < 0:
            dip_points += 3
            dip_details.append("BB<0: +3")
        elif snapshot.bb_pct_b < 0.1:
            dip_points += 2
            dip_details.append("BB<0.1: +2")
        elif snapshot.bb_pct_b < 0.2:
            dip_points += 1
            dip_details.append("BB<0.2: +1")

        # 3. Trend Context (Max 3 Pts)
        dip_points += trend_score
        if trend_score > 0:
            dip_details.append(f"Trend: +{trend_score}")

        # --- STRATEGY B: MOMENTUM BREAKOUT (Max 10 Points) ---
        mom_points = 0
        mom_details = []

        # 1. MACD Trend (Max 3 Pts)
        if "S_BULL" in snapshot.macd_signal:
            mom_points += 3
            mom_details.append("MACD(S_BULL): +3")
        elif "BULL" in snapshot.macd_signal:
            mom_points += 2
            mom_details.append("MACD(BULL): +2")

        # 2. ADX (Max 2 Pts, if Price > MA50)
        if market_val > snapshot.ma50:
            if snapshot.adx > 35:
                mom_points += 2
                mom_details.append("ADX>35: +2")
            elif snapshot.adx > 25:
                mom_points += 1
                mom_details.append("ADX>25: +1")

        # 3. Volume Spike (Max 2 Pts)
        proj_vol = snapshot.projected_volume
        avg_vol = snapshot.avg_volume_14d
        if avg_vol > 0 and proj_vol > avg_vol * 1.5:
            mom_points += 2
            mom_details.append("ProjVol>1.5x: +2")
        elif avg_vol > 0 and proj_vol > avg_vol:
            mom_points += 1
            mom_details.append("ProjVol>Avg: +1")

        # 4. RSI Sweet Spot (Max 3 Pts)
        if 50 <= snapshot.rsi <= 70:
            mom_points += 3
            mom_details.append("RSI(50-70): +3")
        elif 40 <= snapshot.rsi <= 50:
            mom_points += 1
            mom_details.append("RSI(40-50): +1")

        # --- SELECTION ---
        if dip_points >= mom_points:
            base_score = dip_points
            strategy = "DIP"
            base_details = ", ".join(dip_details)
        else:
            base_score = mom_points
            strategy = "MOMENTUM"
            base_details = ", ".join(mom_details)

        # --- STEP 3: ANALYST & VALUATION MODIFIER ---
        analyst_mod, analyst_note = cls.calculate_analyst_modifier(analyst_data, market_val)
        target_bonus = 0

        bank_target = cached_bank_note[0] if cached_bank_note and cached_bank_note[0] else None
        final_target = bank_target if bank_target else snapshot.target_price

        if final_target and final_target > 0 and market_val > 0:
            temp_target = final_target
            if snapshot.stock_id.upper().endswith(".L") and market_val > temp_target * 10:
                temp_target = temp_target * 100
            elif market_val > 10 and temp_target < 10:
                temp_target = temp_target * 100

            target_upside_pct = ((temp_target - market_val) / market_val) * 100

            if market_val <= (temp_target * 0.80):
                target_bonus = 3
                score_reason += f", Bank Target: +3 (20%+ Upside vs {final_target})"
            elif market_val <= (temp_target * 0.90):
                target_bonus = 2
                score_reason += f", Bank Target: +2 (10%+ Upside vs {final_target})"
            elif market_val < temp_target:
                target_bonus = 1
                score_reason += ", Bank Target: +1 (Below Target)"
            elif market_val >= (temp_target * 1.20):
                target_bonus = -3
                score_reason += f", Bank Target: -3 (20%+ Overvalued vs {final_target})"
            elif market_val >= (temp_target * 1.10):
                target_bonus = -2
                score_reason += f", Bank Target: -2 (10%+ Overvalued vs {final_target})"
            elif market_val > temp_target:
                target_bonus = -1
                score_reason += ", Bank Target: -1 (Above Target)"

        # --- FINAL SCORE ---
        smart_score = base_score + analyst_mod + target_bonus

        # Step 4: Asset Class Adjustment (ETF/ETC Boost)
        if snapshot.asset_type.upper() in ["ETF", "ETC"]:
            smart_score += 6
            score_reason += ", ETF/ETC Baseline: +6"

        smart_score = max(0, min(12, int(smart_score)))
        bonus_reason = score_reason
        base_breakdown = f"{base_details}" if base_details else ""
        full_reason = f"[{strategy}] Score: {smart_score}/12 {{{base_breakdown}{analyst_note}{bonus_reason}}}".strip()

        # Two-gate qualification check
        qualifies = False
        if strategy == "DIP" and smart_score >= cls.DIP_SMART_MIN and base_score >= cls.DIP_BASE_MIN:
            qualifies = True
        elif strategy == "MOMENTUM" and smart_score >= cls.MOM_SMART_MIN and base_score >= cls.MOM_BASE_MIN:
            qualifies = True

        return AlphaSignal(
            strategy=strategy,
            smart_score=smart_score,
            base_score=base_score,
            target_upside_pct=target_upside_pct,
            score_reason=full_reason,
            qualifies=qualifies
        )

