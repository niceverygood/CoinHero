import React from 'react';
import { 
  ResponsiveContainer, 
  ComposedChart, 
  Line, 
  Bar,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip,
  ReferenceLine
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="glass-card p-3 rounded-lg border border-crypto-border text-sm">
        <p className="text-gray-400 mb-2">{new Date(label).toLocaleDateString('ko-KR')}</p>
        <div className="space-y-1">
          <p className="text-white">시가: ₩{data.open?.toLocaleString()}</p>
          <p className="text-crypto-green">고가: ₩{data.high?.toLocaleString()}</p>
          <p className="text-crypto-red">저가: ₩{data.low?.toLocaleString()}</p>
          <p className="text-crypto-accent">종가: ₩{data.close?.toLocaleString()}</p>
          <p className="text-gray-400">거래량: {data.volume?.toLocaleString()}</p>
        </div>
      </div>
    );
  }
  return null;
};

function PriceChart({ ticker, data }) {
  // 데이터 포맷 변환
  const chartData = data.map(item => ({
    ...item,
    date: item.index || item.date,
    change: item.close - item.open,
    changePercent: ((item.close - item.open) / item.open * 100).toFixed(2)
  }));

  // 가격 범위 계산
  const prices = chartData.map(d => [d.high, d.low]).flat().filter(Boolean);
  const minPrice = Math.min(...prices) * 0.99;
  const maxPrice = Math.max(...prices) * 1.01;
  const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;

  if (!data || data.length === 0) {
    return (
      <div className="h-80 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 border-4 border-crypto-border border-t-crypto-accent rounded-full animate-spin"></div>
          <p>차트 데이터 로딩 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#58a6ff" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#58a6ff" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#a371f7" stopOpacity={0.5}/>
              <stop offset="95%" stopColor="#a371f7" stopOpacity={0.1}/>
            </linearGradient>
          </defs>
          
          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke="#30363d" 
            vertical={false}
          />
          
          <XAxis 
            dataKey="date" 
            tick={{ fill: '#6e7681', fontSize: 10 }}
            tickLine={{ stroke: '#30363d' }}
            axisLine={{ stroke: '#30363d' }}
            tickFormatter={(value) => {
              if (!value) return '';
              const date = new Date(value);
              return `${date.getMonth() + 1}/${date.getDate()}`;
            }}
          />
          
          <YAxis 
            yAxisId="price"
            domain={[minPrice, maxPrice]}
            tick={{ fill: '#6e7681', fontSize: 10 }}
            tickLine={{ stroke: '#30363d' }}
            axisLine={{ stroke: '#30363d' }}
            tickFormatter={(value) => {
              if (value >= 1000000) return `${(value / 1000000).toFixed(0)}M`;
              if (value >= 1000) return `${(value / 1000).toFixed(0)}K`;
              return value.toFixed(0);
            }}
            width={60}
          />
          
          <YAxis 
            yAxisId="volume"
            orientation="right"
            tick={false}
            axisLine={false}
            tickLine={false}
            width={0}
          />
          
          <Tooltip content={<CustomTooltip />} />
          
          <ReferenceLine 
            yAxisId="price"
            y={avgPrice} 
            stroke="#d29922" 
            strokeDasharray="5 5"
            strokeOpacity={0.5}
          />
          
          <Bar 
            yAxisId="volume"
            dataKey="volume" 
            fill="url(#volumeGradient)"
            opacity={0.3}
          />
          
          <Line 
            yAxisId="price"
            type="monotone" 
            dataKey="close" 
            stroke="#58a6ff" 
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#58a6ff' }}
          />
          
          <Line 
            yAxisId="price"
            type="monotone" 
            dataKey="high" 
            stroke="#3fb950" 
            strokeWidth={1}
            strokeDasharray="3 3"
            dot={false}
            opacity={0.5}
          />
          
          <Line 
            yAxisId="price"
            type="monotone" 
            dataKey="low" 
            stroke="#f85149" 
            strokeWidth={1}
            strokeDasharray="3 3"
            dot={false}
            opacity={0.5}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PriceChart;



