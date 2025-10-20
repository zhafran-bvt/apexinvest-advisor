import React, { useEffect, useState } from 'react';
import axios from 'axios';
import StockChart from './components/StockChart';
import Recommendations from './components/Recommendations';

// Backend API base URL.  In development this points to localhost; in
// production it should be replaced with the service address exposed
// through your Kubernetes ingress or reverse proxy.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function App() {
  const [tickers, setTickers] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState('');
  const [stockData, setStockData] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [riskProfile, setRiskProfile] = useState('medium');

  // Fetch list of available stocks on mount
  useEffect(() => {
    axios.get(`${BACKEND_URL}/stocks`).then((res) => {
      setTickers(res.data);
      if (res.data.length > 0) {
        setSelectedTicker(res.data[0]);
      }
    }).catch((err) => {
      console.error('Failed to load stocks', err);
    });
  }, []);

  // Fetch stock details whenever the selected ticker changes
  useEffect(() => {
    if (!selectedTicker) return;
    axios.get(`${BACKEND_URL}/stock/${selectedTicker}`).then((res) => {
      setStockData(res.data);
    }).catch((err) => {
      console.error('Failed to load stock data', err);
    });
  }, [selectedTicker]);

  // Fetch recommendations whenever risk profile or selected tickers change
  useEffect(() => {
    if (tickers.length === 0) return;
    axios.post(`${BACKEND_URL}/recommendations`, {
      tickers: tickers,
      risk_profile: riskProfile,
      top_n: 5,
    }).then((res) => {
      setRecommendations(res.data);
    }).catch((err) => {
      console.error('Failed to load recommendations', err);
    });
  }, [tickers, riskProfile]);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-4">
      <header className="mb-6">
        <h1 className="text-3xl font-bold">ApexInvest Advisor</h1>
        <p className="text-sm text-gray-400">Personalised stock recommendations and market insights</p>
      </header>
      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <div className="mb-4">
            <label htmlFor="ticker" className="mr-2">Select stock:</label>
            <select
              id="ticker"
              value={selectedTicker}
              onChange={(e) => setSelectedTicker(e.target.value)}
              className="bg-gray-800 text-gray-100 p-2 rounded"
            >
              {tickers.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          {stockData && <StockChart data={stockData} />}
        </div>
        <div>
          <div className="mb-4">
            <label htmlFor="risk" className="mr-2">Risk profile:</label>
            <select
              id="risk"
              value={riskProfile}
              onChange={(e) => setRiskProfile(e.target.value)}
              className="bg-gray-800 text-gray-100 p-2 rounded"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <Recommendations items={recommendations} />
        </div>
      </div>
    </div>
  );
}

export default App;