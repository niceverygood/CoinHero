import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

// 코인 아이콘 색상
const coinColors = {
  'BTC': '#F7931A',
  'ETH': '#627EEA',
  'XRP': '#23292F',
  'SOL': '#9945FF',
  'DOGE': '#C2A633',
  'ADA': '#0033AD',
  'DOT': '#E6007A',
  'MATIC': '#8247E5',
  'AVAX': '#E84142',
  'LINK': '#2A5ADA',
};

function CoinList({ prices, onSelect, selected }) {
  const [prevPrices, setPrevPrices] = useState({});
  const [priceChanges, setPriceChanges] = useState({});

  // 가격 변동 감지
  useEffect(() => {
    const changes = {};
    Object.keys(prices).forEach(ticker => {
      if (prevPrices[ticker] !== undefined) {
        if (prices[ticker] > prevPrices[ticker]) {
          changes[ticker] = 'up';
        } else if (prices[ticker] < prevPrices[ticker]) {
          changes[ticker] = 'down';
        }
      }
    });
    setPriceChanges(changes);
    setPrevPrices(prices);

    // 변동 애니메이션 리셋
    const timer = setTimeout(() => {
      setPriceChanges({});
    }, 1000);

    return () => clearTimeout(timer);
  }, [prices]);

  const coins = Object.entries(prices).map(([ticker, price]) => {
    const coin = ticker.replace('KRW-', '');
    return {
      ticker,
      coin,
      price,
      color: coinColors[coin] || '#58a6ff'
    };
  });

  return (
    <div className="glass-card rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-crypto-green" />
        <span className="text-sm text-gray-400">실시간 시세</span>
      </div>
      
      <div className="space-y-2">
        {coins.map(({ ticker, coin, price, color }) => {
          const isSelected = selected === ticker;
          const change = priceChanges[ticker];
          
          return (
            <button
              key={ticker}
              onClick={() => onSelect(ticker)}
              className={`w-full p-3 rounded-xl flex items-center justify-between transition-all hover:scale-[1.02] ${
                isSelected 
                  ? 'bg-crypto-accent/10 border border-crypto-accent/30' 
                  : 'bg-crypto-darker/50 border border-transparent hover:bg-crypto-darker'
              }`}
            >
              <div className="flex items-center gap-3">
                <div 
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
                  style={{ backgroundColor: color }}
                >
                  {coin.slice(0, 2)}
                </div>
                <div className="text-left">
                  <div className="text-white font-medium">{coin}</div>
                  <div className="text-xs text-gray-500">{ticker}</div>
                </div>
              </div>
              
              <div className="text-right">
                <div className={`font-mono transition-all duration-300 ${
                  change === 'up' 
                    ? 'text-crypto-green glow-green' 
                    : change === 'down' 
                      ? 'text-crypto-red glow-red' 
                      : 'text-white'
                }`}>
                  ₩{price?.toLocaleString() || '---'}
                </div>
                <div className="flex items-center justify-end gap-1 text-xs">
                  {change === 'up' && (
                    <>
                      <TrendingUp className="w-3 h-3 text-crypto-green" />
                      <span className="text-crypto-green">↑</span>
                    </>
                  )}
                  {change === 'down' && (
                    <>
                      <TrendingDown className="w-3 h-3 text-crypto-red" />
                      <span className="text-crypto-red">↓</span>
                    </>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default CoinList;







