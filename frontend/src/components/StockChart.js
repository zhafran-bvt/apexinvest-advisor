import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

function StockChart({ data }) {
  if (!data || !data.history) return null;
  const labels = data.history.map((h) => new Date(h.date).toLocaleDateString());
  const closes = data.history.map((h) => h.Close);
  const chartData = {
    labels: labels,
    datasets: [
      {
        label: `${data.ticker} Close Price`,
        data: closes,
        borderColor: 'rgba(99, 102, 241, 0.6)',
        backgroundColor: 'rgba(99, 102, 241, 0.3)',
        tension: 0.3,
      },
    ],
  };
  const options = {
    responsive: true,
    plugins: {
      legend: { display: true, labels: { color: '#d1d5db' } },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: {
        ticks: { color: '#9ca3af' },
        grid: { color: '#374151' },
      },
      y: {
        ticks: { color: '#9ca3af' },
        grid: { color: '#374151' },
      },
    },
  };
  return (
    <div className="bg-gray-800 p-4 rounded shadow">
      <h2 className="text-xl mb-2">{data.ticker} Price Chart</h2>
      <Line data={chartData} options={options} />
      <div className="mt-4 text-sm text-gray-400">
        <p>SMA 14: {data.technicals.SMA_14.toFixed(2)}</p>
        <p>EMA 14: {data.technicals.EMA_14.toFixed(2)}</p>
        <p>RSI 14: {data.technicals.RSI_14.toFixed(2)}</p>
        <p>Sentiment: {data.technicals.sentiment.toFixed(2)}</p>
      </div>
    </div>
  );
}

export default StockChart;