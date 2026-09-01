import React, { useState, useRef } from 'react';
import type { Dataset } from '../types';

interface DatasetPanelProps {
  datasets: Dataset[];
  activeDatasetId: string;
  onSelectDataset: (id: string) => void;
  onQuickQuery: (query: string) => void;
  onUploadDataset: (dataset: Dataset) => void;
}

/* SVG icons per dataset ID — no emojis */
const DatasetIcon: React.FC<{ id: string }> = ({ id }) => {
  if (id === 'sales') {
    return (
      <div className="dataset-icon sales">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      </div>
    );
  }
  if (id === 'users') {
    return (
      <div className="dataset-icon users">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      </div>
    );
  }
  return (
    <div className="dataset-icon financials">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    </div>
  );
};

export const DatasetPanel: React.FC<DatasetPanelProps> = ({ 
  datasets, 
  activeDatasetId, 
  onSelectDataset,
  onQuickQuery,
  onUploadDataset
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadStatus('Uploading...');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const baseUrl = import.meta.env.VITE_API_URL || '';
      const response = await fetch(`${baseUrl}/api/upload-csv`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) throw new Error('Upload failed');
      
      const data = await response.json();
      onUploadDataset({
        id: data.id,
        name: data.name,
        description: `Uploaded CSV (${data.row_count} rows)`,
        rowCount: data.row_count,
        columns: data.columns,
      });
      setUploadStatus('Success!');
      setTimeout(() => setUploadStatus(''), 3000);
    } catch (error) {
      console.error(error);
      setUploadStatus('Error uploading file');
      setTimeout(() => setUploadStatus(''), 3000);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="dataset-panel glass-card" style={{ flex: 1, minHeight: 0 }}>
      <div className="upload-section" onClick={() => !uploading && fileInputRef.current?.click()}>
        <input 
          type="file" 
          accept=".csv" 
          style={{ display: 'none' }} 
          ref={fileInputRef}
          onChange={handleFileChange}
        />
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <div style={{ marginTop: '8px' }}>
          {uploading ? uploadStatus : 'Upload CSV'}
        </div>
        {!uploading && uploadStatus && <div style={{ fontSize: '0.75rem', color: 'var(--success-color)', marginTop: '4px' }}>{uploadStatus}</div>}
      </div>

      <h3 className="panel-title">Data Sources</h3>
      
      {datasets.map(dataset => (
        <div 
          key={dataset.id}
          className={`dataset-card ${dataset.id === activeDatasetId ? 'active' : ''}`}
          onClick={() => onSelectDataset(dataset.id)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <DatasetIcon id={dataset.id} />
            <div className="dataset-name">{dataset.name}</div>
          </div>
          
          <div className="dataset-desc">{dataset.description}</div>
          
          <div className="dataset-stats">
            <div>
              <span style={{ opacity: 0.6 }}>Rows:</span> {dataset.rowCount.toLocaleString()}
            </div>
            <div>
              <span style={{ opacity: 0.6 }}>Cols:</span> {dataset.columns.length}
            </div>
          </div>
          
          {dataset.id === activeDatasetId && (
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Quick queries</div>
              <div className="chips" style={{ justifyContent: 'flex-start' }}>
                <div className="chip" onClick={(e) => { e.stopPropagation(); onQuickQuery(`Show me an overview of ${dataset.name}`); }}>Overview</div>
                <div className="chip" onClick={(e) => { e.stopPropagation(); onQuickQuery(`What are the key trends in ${dataset.name}?`); }}>Trends</div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
