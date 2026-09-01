import React, { useEffect, useRef } from 'react';
import type { Message } from '../types';

interface ChatTranscriptProps {
  messages: Message[];
  isSpeaking: boolean;
}

export const ChatTranscript: React.FC<ChatTranscriptProps> = ({ messages, isSpeaking }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isSpeaking]);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="chat-container glass-card" style={{ height: '100%' }}>
      <div className="messages-list" ref={scrollRef}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '40px' }}>
            <p>Your conversation will appear here.</p>
          </div>
        )}
        
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.type} ${msg.interrupted ? 'interrupted' : ''}`}>
            <div>
              {msg.text}
              {msg.interrupted && <span className="interrupted-badge">Interrupted</span>}
            </div>
            <div style={{ 
              fontSize: '0.7rem', 
              opacity: 0.7, 
              marginTop: '4px',
              textAlign: msg.type === 'user' ? 'right' : 'left'
            }}>
              {formatTime(msg.timestamp)}
            </div>
          </div>
        ))}
        
        {isSpeaking && (
          <div className="message assistant" style={{ display: 'inline-block', alignSelf: 'flex-start' }}>
            <div className="speaking-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
