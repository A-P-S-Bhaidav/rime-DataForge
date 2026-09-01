export interface Message {
  id: string;
  type: 'user' | 'assistant' | 'filler' | 'error';
  text: string;
  timestamp: Date;
  generationId?: number;
  interrupted?: boolean;
}

export interface ChartData {
  chartType: 'bar' | 'line' | 'pie' | 'area';
  data: any[];
  title: string;
  generationId?: number;
}

export type WebSocketMessage = 
  | { type: 'query'; text: string; generationId: number }
  | { type: 'interrupt'; generationId: number }
  | { type: 'status'; state: 'listening' | 'processing' | 'speaking' | 'idle'; generationId: number }
  | { type: 'transcript'; text: string; generationId: number; isFiller: boolean }
  | { type: 'audio'; data: string; generationId: number; isFinal: boolean }
  | { type: 'chart'; chartType: 'bar' | 'line' | 'pie' | 'area'; data: any[]; title: string; generationId: number }
  | { type: 'error'; message: string; generationId: number }
  | { type: 'interrupted'; generationId: number };

export type AppState = 'idle' | 'listening' | 'processing' | 'speaking';

export interface Dataset {
  id: string;
  name: string;
  description: string;
  rowCount: number;
  columns: string[];
  icon: string;
}
