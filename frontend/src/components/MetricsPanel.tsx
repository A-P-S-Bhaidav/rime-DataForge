import React, { useState, useEffect } from 'react';

interface Metrics {
  averageFillerLatency: number;
  averageLlmLatency: number;
  averageTtsLatency: number;
  totalQueries: number;
}

export const MetricsPanel: React.FC = () => {
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const baseUrl = import.meta.env.VITE_API_URL || '';
        const res = await fetch(`${baseUrl}/api/metrics`);
        if (res.ok) {
          const data = await res.json();
          setMetrics(data);
        }
      } catch (error) {
        console.error('Failed to fetch metrics:', error);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!metrics) return null;

  const getLatencyColor = (ms: number) => {
    if (ms < 1000) return 'var(--success-color)';
    if (ms <= 3000) return '#f59e0b';
    return 'var(--danger-color)';
  };

  const MetricBar = ({ label, value }: { label: string, value: number }) => (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '4px' }}>
        <span>{label}</span>
        <span>{Math.round(value)}ms</span>
      </div>
      <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ 
          height: '100%', 
          width: `${Math.min((value / 5000) * 100, 100)}%`, 
          background: getLatencyColor(value) 
        }} />
      </div>
    </div>
  );

  return (
    <div className="metrics-panel glass-card" style={{ padding: '16px' }}>
      <h3 className="panel-title">System Metrics</h3>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px', fontSize: '0.85rem' }}>
        <span>Total Queries</span>
        <span style={{ fontWeight: 'bold' }}>{metrics.totalQueries}</span>
      </div>
      <MetricBar label="Filler Latency" value={metrics.averageFillerLatency} />
      <MetricBar label="LLM Latency" value={metrics.averageLlmLatency} />
      <MetricBar label="TTS Latency" value={metrics.averageTtsLatency} />
    </div>
  );
};
