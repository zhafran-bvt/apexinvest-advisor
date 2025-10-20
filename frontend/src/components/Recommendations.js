import React from 'react';

function Recommendations({ items }) {
  if (!items || items.length === 0) {
    return <div className="bg-gray-800 p-4 rounded text-gray-400">No recommendations available.</div>;
  }
  return (
    <div className="bg-gray-800 p-4 rounded shadow">
      <h2 className="text-xl mb-2">Top Recommendations</h2>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.ticker} className="flex justify-between items-center bg-gray-700 px-3 py-2 rounded">
            <span className="font-semibold">{item.ticker}</span>
            <span className={
              item.signal === 'Buy' ? 'text-green-400' : item.signal === 'Sell' ? 'text-red-400' : 'text-yellow-400'
            }>
              {item.signal}
            </span>
            <span className="text-sm text-gray-300">{item.confidence.toFixed(2)}%</span>
            <span className="text-xs px-2 py-1 rounded bg-gray-600 text-gray-100">Risk: {item.risk}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default Recommendations;