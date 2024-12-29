import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import logging
from uuid import UUID

from app.models.backtest import (
    BacktestConfig,
    BacktestOrder,
    BacktestResult,
    BacktestSignal,
    BacktestStrategy,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionType,
    TradeStats
)
from app.services.market_data import market_data_service
from app.services.technical_analysis import technical_analysis_service
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class BacktestService:
    def __init__(self):
        self.market_data = market_data_service
        self.technical_analysis = technical_analysis_service

    async def run_backtest(
        self,
        strategy: BacktestStrategy,
        config: BacktestConfig
    ) -> BacktestResult:
        """Run a backtest for a given strategy and configuration."""
        try:
            # Initialize backtest state
            portfolio = await self._initialize_portfolio(config)
            
            # Get historical data for all symbols
            data = await self._get_historical_data(config)
            
            # Run simulation
            results = await self._run_simulation(
                data=data,
                strategy=strategy,
                portfolio=portfolio,
                config=config
            )
            
            # Calculate performance metrics
            stats = self._calculate_stats(results)
            
            # Create backtest result
            return BacktestResult(
                config=config,
                stats=stats,
                equity_curve=results['equity_curve'],
                trades=results['trades'],
                positions=results['positions'],
                orders=results['orders'],
                metrics=results['metrics']
            )
            
        except Exception as e:
            logger.error(f"Error running backtest: {str(e)}")
            raise

    async def _initialize_portfolio(
        self,
        config: BacktestConfig
    ) -> Dict:
        """Initialize portfolio state."""
        return {
            'cash': config.initial_capital,
            'equity': config.initial_capital,
            'positions': {},
            'orders': [],
            'trades': [],
            'equity_curve': [{
                'timestamp': config.start_date,
                'equity': config.initial_capital,
                'cash': config.initial_capital,
                'positions_value': 0.0
            }]
        }

    async def _get_historical_data(
        self,
        config: BacktestConfig
    ) -> Dict[str, pd.DataFrame]:
        """Get historical data for all symbols."""
        data = {}
        for symbol in config.symbols:
            # Try to get from cache first
            cache_key = f"backtest_data:{symbol}:{config.timeframe}:{config.start_date}:{config.end_date}"
            cached_data = await redis_client.get_json(cache_key)
            
            if cached_data:
                data[symbol] = pd.DataFrame(cached_data)
            else:
                # Get from market data service
                df = await self.market_data.get_historical_data(
                    symbol=symbol,
                    timeframe=config.timeframe,
                    start_date=config.start_date,
                    end_date=config.end_date
                )
                
                # Cache for 1 hour
                await redis_client.set_json(cache_key, df.to_dict(), 3600)
                data[symbol] = df
                
        return data

    async def _run_simulation(
        self,
        data: Dict[str, pd.DataFrame],
        strategy: BacktestStrategy,
        portfolio: Dict,
        config: BacktestConfig
    ) -> Dict:
        """Run the backtest simulation."""
        # Get all unique timestamps
        timestamps = sorted(set().union(*[df.index for df in data.values()]))
        
        for timestamp in timestamps:
            # Update portfolio state
            await self._update_portfolio_state(
                portfolio=portfolio,
                data=data,
                timestamp=timestamp,
                config=config
            )
            
            # Generate signals
            signals = await self._generate_signals(
                data=data,
                strategy=strategy,
                timestamp=timestamp
            )
            
            # Process signals
            await self._process_signals(
                signals=signals,
                portfolio=portfolio,
                data=data,
                timestamp=timestamp,
                config=config
            )
            
            # Process pending orders
            await self._process_orders(
                portfolio=portfolio,
                data=data,
                timestamp=timestamp,
                config=config
            )
            
            # Update equity curve
            self._update_equity_curve(
                portfolio=portfolio,
                timestamp=timestamp
            )
        
        return {
            'equity_curve': portfolio['equity_curve'],
            'trades': portfolio['trades'],
            'positions': [pos.dict() for pos in portfolio['positions'].values()],
            'orders': [order.dict() for order in portfolio['orders']],
            'metrics': self._calculate_metrics(portfolio)
        }

    async def _update_portfolio_state(
        self,
        portfolio: Dict,
        data: Dict[str, pd.DataFrame],
        timestamp: datetime,
        config: BacktestConfig
    ):
        """Update portfolio state with current market prices."""
        positions_value = 0.0
        
        for symbol, position in portfolio['positions'].items():
            if symbol in data and timestamp in data[symbol].index:
                current_price = data[symbol].loc[timestamp, 'close']
                position.current_price = current_price
                position.current_timestamp = timestamp
                
                # Update unrealized P&L
                old_unrealized_pnl = position.unrealized_pnl
                if position.type == PositionType.LONG:
                    position.unrealized_pnl = (
                        (current_price - position.entry_price) * 
                        position.quantity
                    )
                else:  # SHORT
                    position.unrealized_pnl = (
                        (position.entry_price - current_price) * 
                        position.quantity
                    )
                
                positions_value += (position.quantity * current_price)
                
                # Check stop loss and take profit
                if config.stop_loss:
                    stop_price = (
                        position.entry_price * (1 - config.stop_loss)
                        if position.type == PositionType.LONG
                        else position.entry_price * (1 + config.stop_loss)
                    )
                    if (position.type == PositionType.LONG and current_price <= stop_price) or \
                       (position.type == PositionType.SHORT and current_price >= stop_price):
                        await self._close_position(
                            portfolio=portfolio,
                            symbol=symbol,
                            price=current_price,
                            timestamp=timestamp,
                            reason="stop_loss"
                        )
                        
                if config.take_profit:
                    take_profit_price = (
                        position.entry_price * (1 + config.take_profit)
                        if position.type == PositionType.LONG
                        else position.entry_price * (1 - config.take_profit)
                    )
                    if (position.type == PositionType.LONG and current_price >= take_profit_price) or \
                       (position.type == PositionType.SHORT and current_price <= take_profit_price):
                        await self._close_position(
                            portfolio=portfolio,
                            symbol=symbol,
                            price=current_price,
                            timestamp=timestamp,
                            reason="take_profit"
                        )
        
        portfolio['equity'] = portfolio['cash'] + positions_value

    async def _generate_signals(
        self,
        data: Dict[str, pd.DataFrame],
        strategy: BacktestStrategy,
        timestamp: datetime
    ) -> List[BacktestSignal]:
        """Generate trading signals based on strategy rules."""
        signals = []
        
        for symbol, df in data.items():
            if timestamp not in df.index:
                continue
                
            # Calculate indicators
            indicators = {}
            for name, config in strategy.config.indicators.items():
                indicators[name] = await self.technical_analysis.calculate_indicator(
                    data=df[:timestamp],
                    **config
                )
            
            # Check entry conditions
            for condition in strategy.config.entry_conditions:
                if self._check_condition(condition, indicators, df.loc[timestamp]):
                    signals.append(BacktestSignal(
                        symbol=symbol,
                        timestamp=timestamp,
                        type="ENTRY",
                        direction=TrendDirection.BULLISH if condition.get('side') == 'buy' else TrendDirection.BEARISH,
                        strength=SignalStrength.STRONG,
                        price=df.loc[timestamp, 'close'],
                        metadata={'condition': condition}
                    ))
            
            # Check exit conditions
            for condition in strategy.config.exit_conditions:
                if self._check_condition(condition, indicators, df.loc[timestamp]):
                    signals.append(BacktestSignal(
                        symbol=symbol,
                        timestamp=timestamp,
                        type="EXIT",
                        direction=TrendDirection.BEARISH if condition.get('side') == 'buy' else TrendDirection.BULLISH,
                        strength=SignalStrength.STRONG,
                        price=df.loc[timestamp, 'close'],
                        metadata={'condition': condition}
                    ))
        
        return signals

    def _check_condition(
        self,
        condition: Dict,
        indicators: Dict,
        current_data: pd.Series
    ) -> bool:
        """Check if a condition is met."""
        try:
            indicator = indicators.get(condition['indicator'])
            if indicator is None:
                return False
            
            operator = condition['operator']
            value = condition['value']
            
            if operator == '>':
                return indicator > value
            elif operator == '<':
                return indicator < value
            elif operator == '>=':
                return indicator >= value
            elif operator == '<=':
                return indicator <= value
            elif operator == '==':
                return indicator == value
            elif operator == 'cross_above':
                return (
                    indicators[condition['indicator1']][-2] <= 
                    indicators[condition['indicator2']][-2] and
                    indicators[condition['indicator1']][-1] > 
                    indicators[condition['indicator2']][-1]
                )
            elif operator == 'cross_below':
                return (
                    indicators[condition['indicator1']][-2] >= 
                    indicators[condition['indicator2']][-2] and
                    indicators[condition['indicator1']][-1] < 
                    indicators[condition['indicator2']][-1]
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking condition: {str(e)}")
            return False

    async def _process_signals(
        self,
        signals: List[BacktestSignal],
        portfolio: Dict,
        data: Dict[str, pd.DataFrame],
        timestamp: datetime,
        config: BacktestConfig
    ):
        """Process trading signals and create orders."""
        for signal in signals:
            symbol = signal.symbol
            current_position = portfolio['positions'].get(symbol)
            
            # Skip if we already have a position and it's an entry signal
            if current_position and signal.type == "ENTRY":
                continue
                
            # Skip if we don't have a position and it's an exit signal
            if not current_position and signal.type == "EXIT":
                continue
                
            # Calculate position size
            if signal.type == "ENTRY":
                position_value = portfolio['equity'] * config.position_size
                quantity = position_value / signal.price
                
                # Create order
                order = BacktestOrder(
                    symbol=symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.BUY if signal.direction == TrendDirection.BULLISH else OrderSide.SELL,
                    quantity=quantity,
                    timestamp=timestamp
                )
                portfolio['orders'].append(order)
                
            else:  # EXIT
                # Create order to close position
                order = BacktestOrder(
                    symbol=symbol,
                    type=OrderType.MARKET,
                    side=OrderSide.SELL if current_position.type == PositionType.LONG else OrderSide.BUY,
                    quantity=current_position.quantity,
                    timestamp=timestamp
                )
                portfolio['orders'].append(order)

    async def _process_orders(
        self,
        portfolio: Dict,
        data: Dict[str, pd.DataFrame],
        timestamp: datetime,
        config: BacktestConfig
    ):
        """Process pending orders."""
        for order in portfolio['orders']:
            if order.status != OrderStatus.PENDING:
                continue
                
            if order.symbol not in data or timestamp not in data[order.symbol].index:
                continue
                
            current_price = data[order.symbol].loc[timestamp, 'close']
            
            # Apply slippage
            fill_price = current_price * (
                1 + config.slippage_rate if order.side == OrderSide.BUY
                else 1 - config.slippage_rate
            )
            
            # Calculate commission
            commission = fill_price * order.quantity * config.commission_rate
            
            # Update order
            order.status = OrderStatus.FILLED
            order.fill_price = fill_price
            order.fill_timestamp = timestamp
            order.commission = commission
            order.slippage = abs(fill_price - current_price) * order.quantity
            
            # Update portfolio
            if order.side == OrderSide.BUY:
                cost = (fill_price * order.quantity) + commission
                if cost > portfolio['cash']:
                    order.status = OrderStatus.REJECTED
                    continue
                    
                portfolio['cash'] -= cost
                
                # Create or update position
                if order.symbol not in portfolio['positions']:
                    portfolio['positions'][order.symbol] = Position(
                        symbol=order.symbol,
                        type=PositionType.LONG,
                        quantity=order.quantity,
                        entry_price=fill_price,
                        entry_timestamp=timestamp,
                        current_price=fill_price,
                        current_timestamp=timestamp,
                        unrealized_pnl=0.0,
                        commission_paid=commission
                    )
                else:
                    position = portfolio['positions'][order.symbol]
                    new_quantity = position.quantity + order.quantity
                    position.entry_price = (
                        (position.entry_price * position.quantity + 
                         fill_price * order.quantity) / 
                        new_quantity
                    )
                    position.quantity = new_quantity
                    position.commission_paid += commission
                    
            else:  # SELL
                proceeds = (fill_price * order.quantity) - commission
                portfolio['cash'] += proceeds
                
                position = portfolio['positions'][order.symbol]
                realized_pnl = (
                    (fill_price - position.entry_price) * order.quantity
                    if position.type == PositionType.LONG
                    else (position.entry_price - fill_price) * order.quantity
                )
                
                # Update position
                if order.quantity == position.quantity:
                    # Close position
                    portfolio['trades'].append({
                        'symbol': order.symbol,
                        'entry_price': position.entry_price,
                        'entry_timestamp': position.entry_timestamp,
                        'exit_price': fill_price,
                        'exit_timestamp': timestamp,
                        'quantity': order.quantity,
                        'pnl': realized_pnl,
                        'commission': position.commission_paid + commission,
                        'type': position.type
                    })
                    del portfolio['positions'][order.symbol]
                else:
                    # Partial close
                    position.quantity -= order.quantity
                    position.realized_pnl += realized_pnl
                    position.commission_paid += commission

    def _update_equity_curve(
        self,
        portfolio: Dict,
        timestamp: datetime
    ):
        """Update the equity curve."""
        positions_value = sum(
            pos.quantity * pos.current_price
            for pos in portfolio['positions'].values()
        )
        
        portfolio['equity_curve'].append({
            'timestamp': timestamp,
            'equity': portfolio['equity'],
            'cash': portfolio['cash'],
            'positions_value': positions_value
        })

    def _calculate_metrics(self, portfolio: Dict) -> Dict[str, float]:
        """Calculate performance metrics."""
        if not portfolio['trades']:
            return {}
            
        equity_curve = pd.DataFrame(portfolio['equity_curve'])
        returns = equity_curve['equity'].pct_change().dropna()
        
        return {
            'total_return': (
                equity_curve['equity'].iloc[-1] / 
                equity_curve['equity'].iloc[0] - 1
            ),
            'annualized_return': (
                (1 + (equity_curve['equity'].iloc[-1] / 
                     equity_curve['equity'].iloc[0] - 1)
                ) ** (252 / len(returns)) - 1
            ),
            'sharpe_ratio': (
                np.sqrt(252) * returns.mean() / returns.std()
                if len(returns) > 1 else 0
            ),
            'sortino_ratio': (
                np.sqrt(252) * returns.mean() / 
                returns[returns < 0].std()
                if len(returns[returns < 0]) > 1 else 0
            ),
            'max_drawdown': (
                (equity_curve['equity'].cummax() - 
                 equity_curve['equity']) / 
                equity_curve['equity'].cummax()
            ).max(),
            'win_rate': (
                sum(1 for t in portfolio['trades'] if t['pnl'] > 0) /
                len(portfolio['trades'])
            )
        }

    def _calculate_stats(self, results: Dict) -> TradeStats:
        """Calculate trading statistics."""
        trades = results['trades']
        if not trades:
            return TradeStats()
            
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in trades)
        total_commission = sum(t['commission'] for t in trades)
        
        return TradeStats(
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(trades) if trades else 0.0,
            avg_win=np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0.0,
            avg_loss=np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0.0,
            largest_win=max([t['pnl'] for t in winning_trades]) if winning_trades else 0.0,
            largest_loss=min([t['pnl'] for t in losing_trades]) if losing_trades else 0.0,
            profit_factor=(
                sum(t['pnl'] for t in winning_trades) /
                abs(sum(t['pnl'] for t in losing_trades))
                if losing_trades else float('inf')
            ),
            sharpe_ratio=results['metrics'].get('sharpe_ratio', 0.0),
            sortino_ratio=results['metrics'].get('sortino_ratio', 0.0),
            max_drawdown=results['metrics'].get('max_drawdown', 0.0),
            total_pnl=total_pnl,
            total_commission=total_commission,
            total_slippage=sum(
                order.slippage for order in results['orders']
                if order.status == OrderStatus.FILLED
            )
        )

# Global backtest service instance
backtest_service = BacktestService()
