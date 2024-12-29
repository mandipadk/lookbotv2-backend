import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from scipy.stats import norm

from app.services.market_data import market_data_service
from app.models.technical import (
    TimeFrame,
    OptionContract,
    OptionFlow,
    StrikeAnalysis,
    ExpiryAnalysis,
    OptionsFlowAnalysis
)
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class OptionsFlowService:
    def __init__(self):
        self.market_data = market_data_service
        self.BLOCK_TRADE_THRESHOLD = 100  # contracts
        self.UNUSUAL_VOLUME_THRESHOLD = 2.0  # std deviations
        self.IV_HISTORY_DAYS = 252  # 1 trading year

    async def get_options_flow_analysis(
        self,
        symbol: str,
        lookback_minutes: int = 60
    ) -> OptionsFlowAnalysis:
        """Get complete options flow analysis for a symbol."""
        try:
            # Try to get from cache
            cache_key = f"options_flow:{symbol}:{lookback_minutes}"
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                return OptionsFlowAnalysis(**cached_data)

            # Get market data
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=lookback_minutes)
            
            # Get underlying price and options chain
            underlying_price = await self.market_data.get_last_price(symbol)
            chain = await self._get_options_chain(symbol)
            
            # Get recent options flows
            flows = await self._get_options_flows(
                symbol,
                start_time,
                end_time
            )
            
            if not flows:
                raise ValueError(f"No options flow data found for {symbol}")
            
            # Process flows into DataFrame for analysis
            df = pd.DataFrame([
                {**f.dict(), **f.contract.dict()}
                for f in flows
            ])
            
            # Calculate implied volatility metrics
            iv_metrics = await self._calculate_iv_metrics(symbol, chain)
            
            # Analyze by expiry
            expiries = await self._analyze_expiries(df, chain)
            
            # Find unusual activity
            unusual = self._detect_unusual_activity(df, flows)
            
            # Calculate sentiment metrics
            sentiment = self._calculate_sentiment_metrics(df)
            
            # Calculate options Greeks exposure
            greeks = self._calculate_greeks_exposure(df, chain)
            
            # Create analysis
            analysis = OptionsFlowAnalysis(
                symbol=symbol,
                timestamp=end_time,
                underlying_price=underlying_price,
                total_volume=int(df['size'].sum()),
                total_open_interest=int(
                    sum(c.open_interest for c in chain)
                ),
                put_call_ratio=float(
                    df[df['type'] == 'put']['size'].sum() /
                    df[df['type'] == 'call']['size'].sum()
                    if df[df['type'] == 'call']['size'].sum() > 0 else 0
                ),
                implied_volatility_rank=iv_metrics['rank'],
                implied_volatility_percentile=iv_metrics['percentile'],
                recent_flows=sorted(
                    flows,
                    key=lambda x: x.timestamp,
                    reverse=True
                )[:100],
                expiries=expiries,
                unusual_activity=unusual,
                bullish_flow_ratio=sentiment['bullish_ratio'],
                bearish_flow_ratio=sentiment['bearish_ratio'],
                smart_money_indicator=sentiment['smart_money'],
                gamma_exposure=greeks['gamma'],
                vanna_exposure=greeks['vanna'],
                charm_exposure=greeks['charm'],
                metadata={
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "lookback_minutes": lookback_minutes
                }
            )
            
            # Cache for 30 seconds
            await redis_client.set_json(cache_key, analysis.dict(), 30)
            
            return analysis
            
        except Exception as e:
            logger.error(
                f"Error analyzing options flow for {symbol}: {str(e)}"
            )
            raise

    async def _get_options_chain(
        self,
        symbol: str
    ) -> List[OptionContract]:
        """Get full options chain for a symbol."""
        try:
            chain_data = await self.market_data.get_options_chain(symbol)
            
            contracts = []
            for data in chain_data:
                contract = OptionContract(
                    symbol=symbol,
                    expiry=data['expiry'],
                    strike=float(data['strike']),
                    type=data['type'],
                    bid=float(data['bid']),
                    ask=float(data['ask']),
                    last=float(data['last']),
                    volume=int(data['volume']),
                    open_interest=int(data['open_interest']),
                    implied_volatility=float(data['implied_volatility']),
                    delta=float(data['delta']),
                    gamma=float(data['gamma']),
                    theta=float(data['theta']),
                    vega=float(data['vega']),
                    rho=float(data['rho']),
                    is_weekly=data.get('is_weekly', False),
                    metadata=data.get('metadata', {})
                )
                contracts.append(contract)
            
            return contracts
            
        except Exception as e:
            logger.error(f"Error getting options chain: {str(e)}")
            raise

    async def _get_options_flows(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[OptionFlow]:
        """Get options flow data."""
        try:
            flow_data = await self.market_data.get_options_flow(
                symbol,
                start_time,
                end_time
            )
            
            flows = []
            for data in flow_data:
                contract = OptionContract(**data['contract'])
                
                flow = OptionFlow(
                    timestamp=data['timestamp'],
                    contract=contract,
                    side=data['side'],
                    size=int(data['size']),
                    premium=float(data['premium']),
                    is_sweep=data.get('is_sweep', False),
                    is_block=int(data['size']) >= self.BLOCK_TRADE_THRESHOLD,
                    sentiment=data['sentiment'],
                    execution_type=data['execution_type'],
                    metadata=data.get('metadata', {})
                )
                flows.append(flow)
            
            return sorted(flows, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"Error getting options flows: {str(e)}")
            raise

    async def _calculate_iv_metrics(
        self,
        symbol: str,
        chain: List[OptionContract]
    ) -> Dict[str, float]:
        """Calculate implied volatility metrics."""
        try:
            # Get historical IV data
            iv_history = await self.market_data.get_historical_iv(
                symbol,
                days=self.IV_HISTORY_DAYS
            )
            
            # Calculate current IV (volume-weighted average)
            current_iv = np.average(
                [c.implied_volatility for c in chain],
                weights=[c.volume for c in chain]
            )
            
            # Calculate IV rank and percentile
            iv_rank = (
                (current_iv - min(iv_history)) /
                (max(iv_history) - min(iv_history))
                if max(iv_history) > min(iv_history) else 0
            )
            
            iv_percentile = sum(
                1 for x in iv_history if x <= current_iv
            ) / len(iv_history)
            
            return {
                "rank": float(iv_rank),
                "percentile": float(iv_percentile)
            }
            
        except Exception as e:
            logger.error(f"Error calculating IV metrics: {str(e)}")
            raise

    async def _analyze_expiries(
        self,
        flows_df: pd.DataFrame,
        chain: List[OptionContract]
    ) -> List[ExpiryAnalysis]:
        """Analyze options activity by expiry date."""
        try:
            expiries = []
            
            # Group by expiry
            chain_df = pd.DataFrame([c.dict() for c in chain])
            for expiry, group in chain_df.groupby('expiry'):
                # Calculate volumes and OI
                call_data = group[group['type'] == 'call']
                put_data = group[group['type'] == 'put']
                
                total_volume = group['volume'].sum()
                total_oi = group['open_interest'].sum()
                call_volume = call_data['volume'].sum()
                put_volume = put_data['volume'].sum()
                
                # Calculate PCR
                pcr_volume = (
                    put_volume / call_volume if call_volume > 0 else 0
                )
                pcr_oi = (
                    put_data['open_interest'].sum() /
                    call_data['open_interest'].sum()
                    if call_data['open_interest'].sum() > 0 else 0
                )
                
                # Calculate implied move
                atm_straddle = self._get_atm_straddle(group)
                days_to_expiry = (
                    expiry - datetime.utcnow()
                ).total_seconds() / (24 * 3600)
                implied_move = (
                    atm_straddle * np.sqrt(days_to_expiry / 365)
                    if days_to_expiry > 0 else 0
                )
                
                # Calculate max pain
                max_pain = self._calculate_max_pain(group)
                
                # Analyze each strike
                strikes = []
                for strike, strike_group in group.groupby('strike'):
                    strike_flows = flows_df[
                        (flows_df['expiry'] == expiry) &
                        (flows_df['strike'] == strike)
                    ]
                    
                    strike_analysis = StrikeAnalysis(
                        strike=float(strike),
                        call_volume=int(
                            strike_group[
                                strike_group['type'] == 'call'
                            ]['volume'].sum()
                        ),
                        put_volume=int(
                            strike_group[
                                strike_group['type'] == 'put'
                            ]['volume'].sum()
                        ),
                        call_oi=int(
                            strike_group[
                                strike_group['type'] == 'call'
                            ]['open_interest'].sum()
                        ),
                        put_oi=int(
                            strike_group[
                                strike_group['type'] == 'put'
                            ]['open_interest'].sum()
                        ),
                        pcr_volume=float(
                            strike_group[
                                strike_group['type'] == 'put'
                            ]['volume'].sum() /
                            strike_group[
                                strike_group['type'] == 'call'
                            ]['volume'].sum()
                            if strike_group[
                                strike_group['type'] == 'call'
                            ]['volume'].sum() > 0 else 0
                        ),
                        pcr_oi=float(
                            strike_group[
                                strike_group['type'] == 'put'
                            ]['open_interest'].sum() /
                            strike_group[
                                strike_group['type'] == 'call'
                            ]['open_interest'].sum()
                            if strike_group[
                                strike_group['type'] == 'call'
                            ]['open_interest'].sum() > 0 else 0
                        ),
                        net_premium=float(
                            strike_flows['premium'].sum()
                        ),
                        implied_move=float(implied_move),
                        notable_trades=[
                            OptionFlow(**t) for t in
                            strike_flows.to_dict('records')
                        ]
                    )
                    strikes.append(strike_analysis)
                
                expiry_analysis = ExpiryAnalysis(
                    expiry=expiry,
                    total_volume=int(total_volume),
                    total_oi=int(total_oi),
                    call_volume=int(call_volume),
                    put_volume=int(put_volume),
                    pcr_volume=float(pcr_volume),
                    pcr_oi=float(pcr_oi),
                    implied_move=float(implied_move),
                    max_pain=float(max_pain),
                    strikes=sorted(
                        strikes,
                        key=lambda x: x.strike
                    )
                )
                expiries.append(expiry_analysis)
            
            return sorted(expiries, key=lambda x: x.expiry)
            
        except Exception as e:
            logger.error(f"Error analyzing expiries: {str(e)}")
            raise

    def _get_atm_straddle(self, chain_df: pd.DataFrame) -> float:
        """Get ATM straddle price."""
        try:
            underlying = chain_df['strike'].mean()
            
            # Find closest strike
            atm_strike = chain_df['strike'].iloc[
                (chain_df['strike'] - underlying).abs().argsort()[:1]
            ].iloc[0]
            
            # Get call and put prices
            atm_options = chain_df[chain_df['strike'] == atm_strike]
            call_price = atm_options[
                atm_options['type'] == 'call'
            ]['last'].iloc[0]
            put_price = atm_options[
                atm_options['type'] == 'put'
            ]['last'].iloc[0]
            
            return call_price + put_price
            
        except Exception as e:
            logger.error(f"Error calculating ATM straddle: {str(e)}")
            return 0.0

    def _calculate_max_pain(self, chain_df: pd.DataFrame) -> float:
        """Calculate max pain point."""
        try:
            strikes = sorted(chain_df['strike'].unique())
            
            # Calculate total value of all options at each strike
            pain = []
            for strike in strikes:
                total_pain = 0
                
                # Add call pain
                calls = chain_df[
                    (chain_df['type'] == 'call') &
                    (chain_df['strike'] <= strike)
                ]
                total_pain += sum(
                    oi * max(0, strike - k)
                    for k, oi in zip(
                        calls['strike'],
                        calls['open_interest']
                    )
                )
                
                # Add put pain
                puts = chain_df[
                    (chain_df['type'] == 'put') &
                    (chain_df['strike'] >= strike)
                ]
                total_pain += sum(
                    oi * max(0, k - strike)
                    for k, oi in zip(
                        puts['strike'],
                        puts['open_interest']
                    )
                )
                
                pain.append(total_pain)
            
            # Return strike with minimum pain
            return strikes[np.argmin(pain)]
            
        except Exception as e:
            logger.error(f"Error calculating max pain: {str(e)}")
            return 0.0

    def _detect_unusual_activity(
        self,
        flows_df: pd.DataFrame,
        flows: List[OptionFlow]
    ) -> List[OptionFlow]:
        """Detect unusual options activity."""
        try:
            unusual = []
            
            # Calculate volume Z-scores
            volume_mean = flows_df['size'].mean()
            volume_std = flows_df['size'].std()
            
            for flow in flows:
                # Check if volume is unusual
                if volume_std > 0:
                    z_score = (
                        flow.size - volume_mean
                    ) / volume_std
                    
                    if (
                        abs(z_score) >= self.UNUSUAL_VOLUME_THRESHOLD or
                        flow.is_block or
                        flow.is_sweep
                    ):
                        unusual.append(flow)
            
            return sorted(
                unusual,
                key=lambda x: x.premium,
                reverse=True
            )
            
        except Exception as e:
            logger.error(f"Error detecting unusual activity: {str(e)}")
            return []

    def _calculate_sentiment_metrics(
        self,
        flows_df: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate sentiment metrics from flow data."""
        try:
            total_premium = flows_df['premium'].sum()
            if total_premium == 0:
                return {
                    "bullish_ratio": 0.0,
                    "bearish_ratio": 0.0,
                    "smart_money": 0.0
                }
            
            # Calculate sentiment ratios
            bullish = flows_df[flows_df['sentiment'] == 'bullish']
            bearish = flows_df[flows_df['sentiment'] == 'bearish']
            
            bullish_ratio = (
                bullish['premium'].sum() / total_premium
            )
            bearish_ratio = (
                bearish['premium'].sum() / total_premium
            )
            
            # Calculate smart money indicator
            # Weight by premium and normalize to [-1, 1]
            smart_money = (
                (bullish_ratio - bearish_ratio) *
                (flows_df[flows_df['is_block']]['premium'].sum() /
                 total_premium)
            )
            
            return {
                "bullish_ratio": float(bullish_ratio),
                "bearish_ratio": float(bearish_ratio),
                "smart_money": float(smart_money)
            }
            
        except Exception as e:
            logger.error(f"Error calculating sentiment: {str(e)}")
            return {
                "bullish_ratio": 0.0,
                "bearish_ratio": 0.0,
                "smart_money": 0.0
            }

    def _calculate_greeks_exposure(
        self,
        flows_df: pd.DataFrame,
        chain: List[OptionContract]
    ) -> Dict[str, float]:
        """Calculate aggregate Greeks exposure."""
        try:
            # Calculate total exposure
            gamma = sum(
                c.gamma * c.open_interest * 100  # Convert to shares
                for c in chain
            )
            
            vanna = sum(
                (c.delta * c.vega) * c.open_interest
                for c in chain
            )
            
            charm = sum(
                c.theta * c.delta * c.open_interest
                for c in chain
            )
            
            return {
                "gamma": float(gamma),
                "vanna": float(vanna),
                "charm": float(charm)
            }
            
        except Exception as e:
            logger.error(f"Error calculating Greeks exposure: {str(e)}")
            return {
                "gamma": 0.0,
                "vanna": 0.0,
                "charm": 0.0
            }

    async def get_real_time_flow(
        self,
        symbol: str,
        window_minutes: int = 5
    ) -> OptionsFlowAnalysis:
        """Get real-time options flow analysis."""
        try:
            analysis = await self.get_options_flow_analysis(
                symbol=symbol,
                lookback_minutes=window_minutes
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                f"Error getting real-time options flow for {symbol}: {str(e)}"
            )
            raise

# Global options flow service instance
options_flow_service = OptionsFlowService()
