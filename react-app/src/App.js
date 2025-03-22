import React, { useState, useEffect, useCallback } from 'react';
import ReactApexChart from 'react-apexcharts';
import './App.css';

function App() {
  const [chartData, setChartData] = useState({
    series: [{ data: [] }],
    options: {
      chart: {
        type: 'candlestick',
        height: 'auto',
        animations: {
          enabled: false,
        },
      },
      title: {
        text: '',
        align: 'center'
      },
      xaxis: {
        type: 'datetime'
      },
      yaxis: {
        tooltip: {
          enabled: true
        }
      }
    }
  });
  const [activeExchange, setActiveExchange] = useState('Binance');
  const [activeCurrency, setActiveCurrency] = useState('Bitcoin');
  const [startDate, setStartDate] = useState(new Date(Date.parse('2017-08-01')));
  const [endDate, setEndDate] = useState(new Date(Date.parse('2024-03-01')));
  const [noAnomalies, setNoAnomalies] = useState(false);
  const [anomalies, setAnomalies] = useState([]);
  
  const fetchData = useCallback(async () => {
    const response = await fetch(`http://127.0.0.1:5000/rates?currency_name=${activeCurrency}&market_name=${activeExchange}`);
    const data = await response.json();
    setChartData(prevState => ({
      ...prevState,
      series: [{ data: data.map(item => ({ x: new Date(Date.parse(item.date)), 
      y: [parseFloat(item.open_price.replace(/[^0-9.]/g, "")),
      parseFloat(item.high_price.replace(/[^0-9.]/g, "")), 
      parseFloat(item.low_price.replace(/[^0-9.]/g, "")), 
      parseFloat(item.close_price.replace(/[^0-9.]/g, ""))] })) }],
      options: {
        ...prevState.options,
        annotations: {
          xaxis: []
        }
      }
    }));
    setNoAnomalies(false);
  }, [activeCurrency, activeExchange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAnalyze = async () => {
    const response = await fetch('http://127.0.0.1:5000/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        currency: activeCurrency, 
        market: activeExchange,
        start_date: startDate,
        end_date: endDate,
      }),
    });
    const data = await response.json();
    setAnomalies(data.anomalies);
    if (data.anomalies.length === 0) {
      setNoAnomalies(true);
    } else {
        setNoAnomalies(false);
    }
    const anomalyAnnotations = data.anomalies.map(anomaly => ({
      x: new Date(anomaly.date).getTime(),
      borderColor: '#ff0000',
      label: {
        style: {
          color: '#fff',
          background: '#ff0000'
        },
        text: 'Anomaly Z-Score'
      }
    }));
    setChartData(prevState => ({
      ...prevState,
      options: {
        ...prevState.options,
        annotations: {
          xaxis: anomalyAnnotations
        }
      }
    }));
  };

  const handleAnalyzeIQR = async () => {
    const response = await fetch('http://127.0.0.1:5000/analyze_iqr', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        currency: activeCurrency, 
        market: activeExchange,
        start_date: startDate,
        end_date: endDate,
      }),
    });
    const data = await response.json();
    setAnomalies(data.anomalies);
    if (data.anomalies.length === 0) {
      setNoAnomalies(true);
    } else {
      setNoAnomalies(false);
    }
    const anomalyAnnotations = data.anomalies.map(anomaly => ({
      x: new Date(anomaly.date).getTime(),
      borderColor: '#ff0000',
      label: {
        style: {
          color: '#fff',
          background: '#ff0000'
        },
        text: 'Anomaly IQR'
      }
    }));
    setChartData(prevState => ({
      ...prevState,
      options: {
        ...prevState.options,
        annotations: {
          xaxis: anomalyAnnotations
        }
      }
    }));
  };

  return (
    <div className="App">
      <header className="app-header">
        <Dropdown title={activeExchange} hint="Market" items={['Binance', 'Kucoin']} setActiveItem={setActiveExchange} />
        <Dropdown title={activeCurrency} hint="Currency" items={['Bitcoin', 'Ethereum', 'BNB', 'Cardano', 'Ripple']} setActiveItem={setActiveCurrency} />
        <input type="date" id="start-date-input" className="date-input" onChange={(e) => setStartDate(e.target.value)}/>
        <input type="date" id="end-date-input" className="date-input" onChange={(e) => setEndDate(e.target.value)}/>
        <button className="analyze-btn" onClick={handleAnalyze} title="Identifies anomalies by finding data points that are too far from the mean.">Analyze (Z-Score)</button>
        <button className="analyze-btn" onClick={handleAnalyzeIQR} title="Identifies anomalies by finding data points that are too far from the median in terms of interquartile range.">Analyze (IQR)</button>
        <div style={{ width: '250px'}}>
          {noAnomalies && <p className='anomaly-message'>No anomalies were detected.</p>}
        </div>
      </header>
      <div className="chart-container">
        <ReactApexChart options={chartData.options} series={chartData.series} type="candlestick" height={800}/>
      </div>
      <Footer />
    </div>
  );
}

const Dropdown = React.memo(({ title, items, setActiveItem, hint }) => (
  <div className="dropdown">
    <button className="dropbtn" title={hint}>{title}</button>
    <div className="dropdown-content">
      {items.map((item, index) => (
        <button key={index} onClick={() => setActiveItem(item)}>{item}</button>
      ))}
    </div>
  </div>
));

const Footer = React.memo(() => (
  <footer className="footer">
    <p>Copyright © 2024 Insony</p>
  </footer>
));

export default App;
