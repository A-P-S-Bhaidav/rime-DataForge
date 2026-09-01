import React from 'react';
import type { Dataset } from '../types';

interface DatasetPanelProps {
  datasets: Dataset[];
  activeDatasetId: string;
  onSelectDataset: (id: string) => void;
  onQuickQuery: (query: string) => void;
}

export const DatasetPanel: React.FC<DatasetPanelProps> = ({ 
  datasets, 
  activeDatasetId, 
  onSelectDataset,
  onQuickQuery
}) => {
  return (
    <div className="dataset-panel glass-card" style={{ height: '100%' }}>
      <h3 className="panel-title">Data Sources</h3>
      
      {datasets.map(dataset => (
        <div 
          key={dataset.id}
          className={`dataset-card ${dataset.id === activeDatasetId ? 'active' : ''}`}
          onClick={() => onSelectDataset(dataset.id)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <span style={{ fontSize: '1.5rem' }}>{dataset.icon}</span>
            <div className="dataset-name">{dataset.name}</div>
          </div>
          
          <div className="dataset-desc">{dataset.description}</div>
          
          <div className="dataset-stats">
            <div>
              <span style={{ opacity: 0.7 }}>Rows:</span> {dataset.rowCount.toLocaleString()}
            </div>
            <div>
              <span style={{ opacity: 0.7 }}>Cols:</span> {dataset.columns.length}
            </div>
          </div>
          
          {dataset.id === activeDatasetId && (
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Quick Queries:</div>
              <div className="chips" style={{ justifyContent: 'flex-start' }}>
                <div 
                  className="chip" 
                  onClick={(e) => { e.stopPropagation(); onQuickQuery(`Show me an overview of ${dataset.name}`); }}
                >
                  Overview
                </div>
                <div 
                  className="chip" 
                  onClick={(e) => { e.stopPropagation(); onQuickQuery(`What are the key trends?`); }}
                >
                  Key Trends
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
