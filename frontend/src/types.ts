export interface Message {
  id: string;
  type: 'user' | 'assistant' | 'filler' | 'error' | 'insight';
  text: string;
  timestamp: Date;
  generationId?: number;
  interrupted?: boolean;
}

export interface ChartData {
  chartType: 'bar' | 'line' | 'pie' | 'area' | 'scatter' | 'stacked_bar' | 'horizontal_bar' | 'composed';
  data: any[];
  title: string;
  generationId?: number;
  responseType?: 'chart' | 'table' | 'insight' | 'chart_and_insight';
  insights?: string;
  tableData?: any[];
  tableColumns?: string[];
}

export type WebSocketMessage = 
  | { type: 'query'; text: string; generationId: number }
  | { type: 'interrupt'; generationId: number }
  | { type: 'status'; state: 'listening' | 'processing' | 'speaking' | 'idle'; generationId: number }
  | { type: 'transcript'; text: string; generationId: number; isFiller: boolean; isInsight?: boolean }
  | { type: 'audio'; data: string; generationId: number; isFinal: boolean }
  | { type: 'chart'; chartType: string; data: any[]; title: string; generationId: number; responseType?: string; insights?: string; tableData?: any[]; tableColumns?: string[] }
  | { type: 'error'; message: string; generationId: number }
  | { type: 'interrupted'; generationId: number };

export type AppState = 'idle' | 'listening' | 'processing' | 'speaking';

export interface Dataset {
  id: string;
  name: string;
  description: string;
  rowCount: number;
  columns: string[];
}
