import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioPlayer } from './hooks/useAudioPlayer';
import { useSpeechRecognition } from './hooks/useSpeechRecognition';
import { Header } from './components/Header';
import { VoiceControl } from './components/VoiceControl';
import { DataVisualization } from './components/DataVisualization';
import { ChatTranscript } from './components/ChatTranscript';
import { DatasetPanel } from './components/DatasetPanel';
import type { AppState, Message, ChartData, Dataset } from './types';
import './styles/index.css';

const DATASETS: Dataset[] = [
  {
    id: 'sales',
    name: 'Sales Performance',
    description: 'Transactions by region, product, quarter, and sales rep.',
    rowCount: 200,
    columns: ['region', 'product', 'quarter', 'sales_rep', 'amount', 'units'],
  },
  {
    id: 'users',
    name: 'User Analytics',
    description: 'Daily active users, sessions, bounce rate, and page views.',
    rowCount: 365,
    columns: ['date', 'daily_active_users', 'sessions', 'bounce_rate', 'new_users', 'page_views'],
  },
  {
    id: 'financials',
    name: 'Financial Records',
    description: 'Monthly revenue, expenses, profit by category.',
    rowCount: 60,
    columns: ['month', 'revenue', 'expenses', 'profit', 'category', 'headcount'],
  }
];

const SUGGESTED_QUERIES = [
  "Sales by region",
  "Monthly revenue trend",
  "Top selling products",
  "User growth over time"
];

/**
 * Determine the WebSocket URL based on environment.
 * In production (Vercel), use VITE_WS_URL env var.
 * In dev, connect directly to the local backend.
 */
function getWsUrl(): string {
  // Check for explicit env var first
  const envUrl = import.meta.env.VITE_WS_URL;
  if (envUrl) return envUrl;

  // In production, derive from window.location
  if (import.meta.env.PROD) {
    const apiBase = import.meta.env.VITE_API_URL;
    if (apiBase) {
      const url = new URL(apiBase);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      url.pathname = '/ws';
      return url.toString();
    }
  }

  // Default: local dev backend
  return 'ws://localhost:8000/ws';
}

function App() {
  const [appState, setAppState] = useState<AppState>('idle');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentChart, setCurrentChart] = useState<ChartData | null>(null);
  const [generationIdCounter, setGenerationIdCounter] = useState(1);
  const [activeDatasetId, setActiveDatasetId] = useState<string>(DATASETS[0].id);

  const wsUrl = getWsUrl();
  const { sendMessage, lastMessage, connectionState } = useWebSocket(wsUrl);
  const { isPlaying, playChunk, stop: stopAudio } = useAudioPlayer();
  const { transcript, interimTranscript, isListening, startListening, stopListening, isSupported } = useSpeechRecognition();

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    switch (lastMessage.type) {
      case 'status':
        setAppState(lastMessage.state);
        break;
      
      case 'transcript':
        setMessages(prev => {
          const existingIdx = prev.findIndex(
            m => m.generationId === lastMessage.generationId && m.type === (lastMessage.isFiller ? 'filler' : 'assistant')
          );
          
          if (existingIdx >= 0) {
            const updated = [...prev];
            updated[existingIdx] = { ...updated[existingIdx], text: lastMessage.text };
            return updated;
          }
          return [...prev, {
            id: crypto.randomUUID(),
            type: lastMessage.isFiller ? 'filler' : 'assistant',
            text: lastMessage.text,
            timestamp: new Date(),
            generationId: lastMessage.generationId
          }];
        });
        break;

      case 'audio':
        if (lastMessage.data) {
          playChunk(lastMessage.data, lastMessage.generationId, lastMessage.isFinal);
        }
        break;

      case 'chart':
        setCurrentChart({
          chartType: lastMessage.chartType,
          data: lastMessage.data,
          title: lastMessage.title,
          generationId: lastMessage.generationId
        });
        break;

      case 'error':
        setMessages(prev => [...prev, {
          id: crypto.randomUUID(),
          type: 'error',
          text: lastMessage.message,
          timestamp: new Date(),
          generationId: lastMessage.generationId
        }]);
        setAppState('idle');
        break;

      case 'interrupted':
        setMessages(prev => prev.map(m => 
          m.generationId === lastMessage.generationId ? { ...m, interrupted: true } : m
        ));
        setAppState('idle');
        break;
    }
  }, [lastMessage, playChunk]);

  // Handle end of speech recognition
  useEffect(() => {
    if (!isListening && transcript && appState === 'listening') {
      handleSendQuery(transcript);
    }
  }, [isListening, transcript, appState]);

  const handleToggleListening = useCallback(() => {
    if (!isSupported) {
      alert("Speech recognition requires Chrome or Edge. Use the text input instead.");
      return;
    }

    if (appState === 'speaking') {
      handleInterrupt();
      return;
    }

    if (isListening) {
      stopListening();
    } else {
      setAppState('listening');
      startListening();
    }
  }, [isListening, appState, isSupported, startListening, stopListening]);

  const handleSendQuery = useCallback((query: string) => {
    if (!query.trim()) return;
    
    stopListening();
    const newGenId = generationIdCounter;
    setGenerationIdCounter(prev => prev + 1);
    
    setMessages(prev => [...prev, {
      id: crypto.randomUUID(),
      type: 'user',
      text: query,
      timestamp: new Date(),
      generationId: newGenId
    }]);
    
    setAppState('processing');
    
    sendMessage({
      type: 'query',
      text: query,
      generationId: newGenId
    });
  }, [generationIdCounter, sendMessage, stopListening]);

  const handleInterrupt = useCallback(() => {
    stopListening();
    stopAudio();
    
    if (appState === 'processing' || appState === 'speaking') {
      sendMessage({
        type: 'interrupt',
        generationId: generationIdCounter - 1
      });
    }
    
    setAppState('idle');
  }, [appState, stopListening, stopAudio, sendMessage, generationIdCounter]);

  return (
    <div className="app-container">
      <Header connectionState={connectionState} appState={appState} />
      
      <main className="main-content">
        <ChatTranscript messages={messages} isSpeaking={appState === 'speaking' || isPlaying} />
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: '100%', minHeight: 0 }}>
          <DataVisualization chart={currentChart} />
          
          <VoiceControl 
            appState={appState}
            isListening={isListening}
            transcript={transcript}
            interimTranscript={interimTranscript}
            onToggleListening={handleToggleListening}
            onInterrupt={handleInterrupt}
            onSendQuery={handleSendQuery}
            suggestedQueries={SUGGESTED_QUERIES}
          />
        </div>
        
        <DatasetPanel 
          datasets={DATASETS}
          activeDatasetId={activeDatasetId}
          onSelectDataset={setActiveDatasetId}
          onQuickQuery={handleSendQuery}
        />
      </main>
    </div>
  );
}

export default App;
