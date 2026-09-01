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

const MOCK_DATASETS: Dataset[] = [
  {
    id: 'sales_q3',
    name: 'Global Sales Q3',
    description: 'Quarterly sales performance across all regions with product category breakdown.',
    rowCount: 125000,
    columns: ['Region', 'Country', 'Product', 'Revenue', 'Date'],
    icon: '📈'
  },
  {
    id: 'user_growth',
    name: 'User Growth Metrics',
    description: 'Daily active users, retention rates, and acquisition channels.',
    rowCount: 45000,
    columns: ['Date', 'DAU', 'MAU', 'Channel', 'Retention'],
    icon: '👥'
  },
  {
    id: 'inventory',
    name: 'Real-time Inventory',
    description: 'Current stock levels, warehouse locations, and restock predictions.',
    rowCount: 8500,
    columns: ['SKU', 'Warehouse', 'Stock', 'Status', 'RestockDate'],
    icon: '📦'
  }
];

const SUGGESTED_QUERIES = [
  "Sales by region",
  "Monthly revenue trend",
  "Top products",
  "User growth"
];

function App() {
  const [appState, setAppState] = useState<AppState>('idle');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentChart, setCurrentChart] = useState<ChartData | null>(null);
  const [generationIdCounter, setGenerationIdCounter] = useState(1);
  const [activeDatasetId, setActiveDatasetId] = useState<string>(MOCK_DATASETS[0].id);

  const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
  const { sendMessage, lastMessage, connectionState } = useWebSocket(wsUrl);
  const { isPlaying, playChunk, stop: stopAudio,} = useAudioPlayer();
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
          const existingMsgIndex = prev.findIndex(m => m.generationId === lastMessage.generationId && m.type === (lastMessage.isFiller ? 'filler' : 'assistant'));
          
          if (existingMsgIndex >= 0) {
            const newMessages = [...prev];
            newMessages[existingMsgIndex] = {
              ...newMessages[existingMsgIndex],
              text: lastMessage.text
            };
            return newMessages;
          } else {
            return [...prev, {
              id: Math.random().toString(36).substring(7),
              type: lastMessage.isFiller ? 'filler' : 'assistant',
              text: lastMessage.text,
              timestamp: new Date(),
              generationId: lastMessage.generationId
            }];
          }
        });
        break;

      case 'audio':
        playChunk(lastMessage.data, lastMessage.generationId, lastMessage.isFinal);
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
          id: Math.random().toString(36).substring(7),
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

  // Sync Audio player state with App state
  useEffect(() => {
    if (isPlaying && appState !== 'speaking') {
      // Audio might still be playing
    }
  }, [isPlaying, appState]);

  // Handle end of speech
  useEffect(() => {
    if (!isListening && transcript && appState === 'listening') {
      handleSendQuery(transcript);
    }
  }, [isListening, transcript, appState]);

  const handleToggleListening = useCallback(() => {
    if (!isSupported) {
      alert("Speech recognition is not supported in this browser. Please use Chrome.");
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
      id: Math.random().toString(36).substring(7),
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
        generationId: generationIdCounter - 1 // Interrupt the current generation
      });
    }
    
    setAppState('idle');
  }, [appState, stopListening, stopAudio, sendMessage, generationIdCounter]);

  return (
    <div className="app-container">
      <Header connectionState={connectionState} appState={appState} />
      
      <main className="main-content">
        <ChatTranscript messages={messages} isSpeaking={appState === 'speaking' || isPlaying} />
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
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
          datasets={MOCK_DATASETS}
          activeDatasetId={activeDatasetId}
          onSelectDataset={setActiveDatasetId}
          onQuickQuery={handleSendQuery}
        />
      </main>
    </div>
  );
}

export default App;
