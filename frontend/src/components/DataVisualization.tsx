import React from 'react';
import type { ChartData } from '../types';
import { 
  BarChart, Bar, LineChart, Line, PieChart, Pie, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ComposedChart
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
  
  // CRITICAL FIX: compute xAxisKey FIRST, then exclude from dataKeys
  const xAxisKey = data.length > 0 
    ? Object.keys(data[0]).find(k => k === 'name' || k === 'label') || Object.keys(data[0])[0] 
    : 'name';
  const dataKeys = data.length > 0 
    ? Object.keys(data[0]).filter(k => k !== 'name' && k !== 'id' && k !== 'label' && k !== xAxisKey) 
    : [];
  // Filter to only numeric keys for chart rendering
  const numericDataKeys = dataKeys.filter(k => 
    data.length > 0 && typeof data[0][k] === 'number'
  );
  const effectiveDataKeys = numericDataKeys.length > 0 ? numericDataKeys : dataKeys;

  // Shared axis props — properly formatted
  const xAxisProps = {
    dataKey: xAxisKey,
    stroke: "transparent",
    tick: { fill: '#64748b', fontSize: 11, angle: -35, textAnchor: 'end' as const },
    height: 60,
    tickMargin: 8,
  };
  const yAxisProps = {
    stroke: "transparent",
    tick: { fill: '#64748b', fontSize: 11 },
    width: 65,
    tickFormatter: (value: any) => {
      if (typeof value !== 'number') return value;
      if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
      if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
      return value % 1 === 0 ? value.toString() : value.toFixed(1);
    },
  };
  const gridStroke = 'rgba(255,255,255,0.06)';
  const margins = { top: 10, right: 20, left: 10, bottom: 20 };

  const renderChart = () => {
    switch (chartType) {
      case 'bar':
        return (
          <BarChart data={data} margin={margins}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis {...xAxisProps} />
            <YAxis {...yAxisProps} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {effectiveDataKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} animationDuration={800} />
            ))}
          </BarChart>
        );
      
      case 'stacked_bar':
        return (
          <BarChart data={data} margin={margins}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis {...xAxisProps} />
            <YAxis {...yAxisProps} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {effectiveDataKeys.map((key, i) => (
              <Bar key={key} dataKey={key} stackId="stack" fill={COLORS[i % COLORS.length]} animationDuration={800} />
            ))}
          </BarChart>
        );

      case 'horizontal_bar':
        return (
          <BarChart data={data} layout="vertical" margin={{ ...margins, left: 80 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} horizontal={false} />
            <XAxis type="number" {...yAxisProps} />
            <YAxis type="category" dataKey={xAxisKey} stroke="transparent" tick={{ fill: '#64748b', fontSize: 11 }} width={75} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {effectiveDataKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[0, 4, 4, 0]} animationDuration={800} />
            ))}
          </BarChart>
        );
      
      case 'line':
        return (
          <LineChart data={data} margin={margins}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis {...xAxisProps} />
            <YAxis {...yAxisProps} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {effectiveDataKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={2.5} dot={{ r: 3, fill: COLORS[i % COLORS.length], strokeWidth: 0 }} activeDot={{ r: 5 }} animationDuration={800} />
            ))}
          </LineChart>
        );
        
      case 'area':
        return (
          <AreaChart data={data} margin={margins}>
            <defs>
              {effectiveDataKeys.map((key, i) => (
                <linearGradient key={`color-${key}`} id={`color${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0}/>
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis {...xAxisProps} />
            <YAxis {...yAxisProps} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {effectiveDataKeys.map((key, i) => (
              <Area key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} fillOpacity={1} fill={`url(#color${key})`} strokeWidth={2} animationDuration={800} />
            ))}
          </AreaChart>
        );

      case 'scatter': {
        const xKey = effectiveDataKeys[0] || xAxisKey;
        const yKey = effectiveDataKeys[1] || effectiveDataKeys[0];
        return (
          <ScatterChart margin={margins}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
            <XAxis dataKey={xKey} name={xKey} stroke="transparent" tick={{ fill: '#64748b', fontSize: 11 }} />
            <YAxis dataKey={yKey} name={yKey} {...yAxisProps} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            <Scatter name={`${xKey} vs ${yKey}`} data={data} fill={COLORS[0]} animationDuration={800} />
          </ScatterChart>
        );
      }

      case 'composed': {
        const barKey = effectiveDataKeys[0];
        const lineKey = effectiveDataKeys[1] || effectiveDataKeys[0];
        return (
          <ComposedChart data={data} margin={margins}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis {...xAxisProps} />
            <YAxis {...yAxisProps} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            {barKey && <Bar dataKey={barKey} fill={COLORS[0]} radius={[4, 4, 0, 0]} animationDuration={800} />}
            {lineKey && lineKey !== barKey && <Line type="monotone" dataKey={lineKey} stroke={COLORS[2]} strokeWidth={2.5} dot={{ r: 3 }} animationDuration={800} />}
          </ComposedChart>
        );
      }

      case 'pie': {
        const valueKey = effectiveDataKeys[0];
        return (
          <PieChart>
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '0.75rem' }} />
            <Pie data={data} cx="50%" cy="50%" labelLine={false} outerRadius={110} innerRadius={50} fill="#8884d8" dataKey={valueKey} nameKey={xAxisKey} animationDuration={800} stroke="rgba(0,0,0,0.3)" strokeWidth={1}>
              {data.map((_entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
          </PieChart>
        );
      }
        
      default:
        return <div style={{ color: 'var(--text-muted)' }}>Unsupported chart type: {chartType}</div>;
    }
  };

  // Render data table
  const renderTable = () => {
    const tableData = chart.tableData || data;
    const columns = chart.tableColumns || (tableData.length > 0 ? Object.keys(tableData[0]) : []);
    if (!tableData.length) return null;
    
    return (
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col}>{col.replace(/_/g, ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableData.slice(0, 50).map((row: any, i: number) => (
              <tr key={i}>
                {columns.map(col => (
                  <td key={col}>
                    {typeof row[col] === 'number' ? row[col].toLocaleString() : String(row[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {tableData.length > 50 && (
          <div className="table-footer">Showing 50 of {tableData.length} rows</div>
        )}
      </div>
    );
  };

  // Render insights panel
  const renderInsights = () => {
    if (!chart.insights) return null;
    return (
      <div className="insights-panel">
        <div className="insights-header">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
          Key Insights
        </div>
        <div className="insights-content">
          {chart.insights.split('\n').filter(l => l.trim()).map((line, i) => {
            const cleaned = line.replace(/^[-•*]\s*/, '').trim();
            if (!cleaned) return null;
            return (
              <div key={i} className="insight-item">
                <span className="insight-bullet">•</span>
                <span dangerouslySetInnerHTML={{ __html: cleaned.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const responseType = chart.responseType || 'chart';
  const showChart = responseType === 'chart' || responseType === 'chart_and_insight';
  const showTable = responseType === 'table';
  const showInsights = !!chart.insights && (responseType === 'chart_and_insight' || responseType === 'insight');

  return (
    <div className="viz-container glass-card" style={{ height: '100%' }}>
      <div className="chart-header">
        <h2 className="chart-title">{title}</h2>
      </div>
      
      {showChart && data.length > 0 && (
        <div className="chart-wrapper">
          <ResponsiveContainer key={chart.generationId || title} width="100%" height="100%">
            {renderChart()}
          </ResponsiveContainer>
        </div>
      )}

      {showTable && renderTable()}
      {showInsights && renderInsights()}
    </div>
  );
};
