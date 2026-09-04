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
      <div className="chat-header">Conversation</div>
      <div className="messages-list" ref={scrollRef}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '40px', fontSize: '0.85rem' }}>
            <p>Your conversation will appear here.</p>
          </div>
        )}
        
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.type} ${msg.interrupted ? 'interrupted' : ''}`}>
            <div>
              {msg.type === 'insight' ? (
                <div className="insight-message-content">
                  {msg.text.split('\n').filter(l => l.trim()).map((line, i) => {
                    const cleaned = line.replace(/^[-•*]\s*/, '').trim();
                    if (!cleaned) return null;
                    return (
                      <div key={i} className="insight-line">
                        <span dangerouslySetInnerHTML={{ __html: cleaned.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
                      </div>
                    );
                  })}
                </div>
              ) : (
                <>
                  {msg.text}
                  {msg.interrupted && <span className="interrupted-badge">Interrupted</span>}
                </>
              )}
            </div>
            <div className="message-time" style={{ textAlign: msg.type === 'user' ? 'right' : 'left' }}>
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
