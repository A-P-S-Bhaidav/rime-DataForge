import { useState, useEffect, useCallback, useRef } from 'react';
import type { WebSocketMessage } from '../types';

export interface UseWebSocketReturn {
  isConnected: boolean;
  sendMessage: (msg: any) => void;
  lastMessage: WebSocketMessage | null;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error';
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<number | null>(null);
  const messageQueue = useRef<any[]>([]);
  const isComponentMounted = useRef(true);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN || ws.current?.readyState === WebSocket.CONNECTING) return;
    
    setConnectionState('connecting');
    
    try {
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        if (!isComponentMounted.current) return;
        setConnectionState('connected');
        // Flush queue
        while (messageQueue.current.length > 0) {
          const msg = messageQueue.current.shift();
          ws.current?.send(JSON.stringify(msg));
        }
      };
      
      ws.current.onmessage = (event) => {
        if (!isComponentMounted.current) return;
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };
      
      ws.current.onclose = () => {
        if (!isComponentMounted.current) return;
        setConnectionState('disconnected');
        ws.current = null;
        // Reconnect with backoff
        reconnectTimeout.current = window.setTimeout(connect, 3000);
      };
      
      ws.current.onerror = () => {
        if (!isComponentMounted.current) return;
        setConnectionState('error');
      };
      
    } catch (error) {
      if (!isComponentMounted.current) return;
      setConnectionState('error');
      reconnectTimeout.current = window.setTimeout(connect, 5000);
    }
  }, [url]);

  useEffect(() => {
    isComponentMounted.current = true;
    connect();
    
    return () => {
      isComponentMounted.current = false;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg: any) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    } else {
      messageQueue.current.push(msg);
      if (connectionState === 'disconnected' || connectionState === 'error') {
        connect();
      }
    }
  }, [connect, connectionState]);

  return {
    isConnected: connectionState === 'connected',
    sendMessage,
    lastMessage,
    connectionState
  };
}
