import React from 'react';
import type { ChartData } from '../types';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts';

interface DataVisualizationProps {
  chart: ChartData | null;
}

const COLORS = ['#6366f1', '#8b5cf6', '#10b981', '#1DADC7', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6'];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: 'rgba(15, 23, 42, 0.95)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(99, 102, 241, 0.2)',
        borderRadius: '10px',
        padding: '10px 14px',
        fontSize: '0.8rem',
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      }}>
        <p style={{ margin: '0 0 6px 0', fontWeight: 600, color: '#e2e8f0', fontSize: '0.75rem' }}>{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={`item-${index}`} style={{ margin: '3px 0', color: entry.color, display: 'flex', justifyContent: 'space-between', gap: '16px' }}>
            <span style={{ opacity: 0.8 }}>{entry.name}</span>
            <span style={{ fontWeight: 600 }}>{typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}</span>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export const DataVisualization: React.FC<DataVisualizationProps> = ({ chart }) => {
  if (!chart) {
    return (
      <div className="viz-container glass-card" style={{ height: '100%' }}>
        <div className="empty-state">
          <div className="empty-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
              <line x1="3" y1="20" x2="21" y2="20" />
            </svg>
          </div>
          <h3>Ready for Data</h3>
          <p>Ask a question like "Show me sales by region" to generate a visualization.</p>
        </div>
      </div>
    );
  }

  const { chartType, data, title } = chart;
  
  const dataKeys = data.length > 0 ? Object.keys(data[0]).filter(k => k !== 'name' && k !== 'id' && k !== 'label') : [];
  const xAxisKey = data.length > 0 ? Object.keys(data[0]).find(k => k === 'name' || k === 'label') || Object.keys(data[0])[0] : 'name';

  const renderChart = () => {
    const axisStyle = { fill: '#64748b', fontSize: 11 };
    const gridStroke = 'rgba(255,255,255,0.06)';

    switch (chartType) {
      case 'bar':
        return (
          <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis dataKey={xAxisKey} stroke="transparent" tick={axisStyle} />
            <YAxis stroke="transparent" tick={axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {dataKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} animationDuration={800} />
            ))}
          </BarChart>
        );
      
      case 'line':
        return (
          <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis dataKey={xAxisKey} stroke="transparent" tick={axisStyle} />
            <YAxis stroke="transparent" tick={axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {dataKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={2.5} dot={{ r: 3, fill: COLORS[i % COLORS.length], strokeWidth: 0 }} activeDot={{ r: 5 }} animationDuration={800} />
            ))}
          </LineChart>
        );
        
      case 'area':
        return (
          <AreaChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 16 }}>
            <defs>
              {dataKeys.map((key, i) => (
                <linearGradient key={`color-${key}`} id={`color${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0}/>
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis dataKey={xAxisKey} stroke="transparent" tick={axisStyle} />
            <YAxis stroke="transparent" tick={axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {dataKeys.map((key, i) => (
              <Area key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} fillOpacity={1} fill={`url(#color${key})`} strokeWidth={2} animationDuration={800} />
            ))}
          </AreaChart>
        );
        
      case 'pie': {
        const valueKey = dataKeys[0];
        return (
          <PieChart>
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              outerRadius={110}
              innerRadius={50}
              fill="#8884d8"
              dataKey={valueKey}
              nameKey={xAxisKey}
              animationDuration={800}
              stroke="rgba(0,0,0,0.3)"
              strokeWidth={1}
            >
              {data.map((_entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        );
      }
        
      default:
        return <div style={{ color: 'var(--text-muted)' }}>Unsupported chart type</div>;
    }
  };

  return (
    <div className="viz-container glass-card" style={{ height: '100%' }}>
      <div className="chart-header">
        <h2 className="chart-title">{title}</h2>
      </div>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );
};
