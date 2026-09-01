import React, { useState } from "react";
import type { KeyboardEvent } from 'react';
import type { AppState } from '../types';

interface VoiceControlProps {
  appState: AppState;
  isListening: boolean;
  transcript: string;
  interimTranscript: string;
  onToggleListening: () => void;
  onInterrupt: () => void;
  onSendQuery: (query: string) => void;
  suggestedQueries: string[];
}

export const VoiceControl: React.FC<VoiceControlProps> = ({
  appState,
  isListening,
  transcript,
  interimTranscript,
  onToggleListening,
  onInterrupt,
  onSendQuery,
  suggestedQueries
}) => {
  const [textInput, setTextInput] = useState('');

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && textInput.trim()) {
      onSendQuery(textInput.trim());
      setTextInput('');
    }
  };

  const getMicIcon = () => {
    if (appState === 'speaking') {
      return (
        <svg className="mic-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.35 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM18.584 5.106a.75.75 0 011.06 0c3.808 3.807 3.808 9.98 0 13.788a.75.75 0 11-1.06-1.06 8.25 8.25 0 000-11.668.75.75 0 010-1.06z" fill="currentColor"/>
          <path d="M15.932 7.757a.75.75 0 011.061 0 6 6 0 010 8.486.75.75 0 01-1.06-1.061 4.5 4.5 0 000-6.364.75.75 0 010-1.06z" fill="currentColor"/>
        </svg>
      );
    }
    
    if (appState === 'processing') {
      return <div className="spinner"></div>;
    }

    return (
      <svg className="mic-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 14C13.6569 14 15 12.6569 15 11V5C15 3.34315 13.6569 2 12 2C10.3431 2 9 3.34315 9 5V11C9 12.6569 10.3431 14 12 14Z" fill="currentColor"/>
        <path d="M19 10V11C19 14.866 15.866 18 12 18C8.13401 18 5 14.866 5 11V10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M12 18V22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M8 22H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    );
  };

  const displayTranscript = () => {
    if (appState === 'listening' || isListening) {
      return (
        <div className="live-transcript">
          {transcript} <span style={{ opacity: 0.5 }}>{interimTranscript}</span>
          {!transcript && !interimTranscript && <span style={{ opacity: 0.3 }}>Listening...</span>}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="voice-control glass-card">
      {displayTranscript()}
      
      <button 
        className={`mic-button ${appState}`} 
        onClick={onToggleListening}
        disabled={appState === 'processing'}
        title={isListening ? "Stop listening" : "Start speaking"}
      >
        {getMicIcon()}
      </button>

      <div className="status-label">
        {appState === 'idle' && !isListening && 'Tap to speak'}
        {appState === 'listening' && 'Listening...'}
        {appState === 'processing' && 'Analyzing...'}
        {appState === 'speaking' && (
          <div className="waveform">
            <div className="waveform-bar"></div>
            <div className="waveform-bar"></div>
            <div className="waveform-bar"></div>
            <div className="waveform-bar"></div>
            <div className="waveform-bar"></div>
          </div>
        )}
      </div>

      {appState === 'speaking' && (
        <button className="interrupt-btn" onClick={onInterrupt}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="9" x2="15" y2="15"></line>
            <line x1="15" y1="9" x2="9" y2="15"></line>
          </svg>
          Interrupt
        </button>
      )}

      {appState === 'idle' && (
        <>
          <div className="text-input-container">
            <input 
              type="text" 
              className="text-input" 
              placeholder="Or type your query here..." 
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button 
              className="send-btn" 
              onClick={() => {
                if (textInput.trim()) {
                  onSendQuery(textInput.trim());
                  setTextInput('');
                }
              }}
            >
              Send
            </button>
          </div>
          
          <div className="chips">
            {suggestedQueries.map((q, i) => (
              <div key={i} className="chip" onClick={() => onSendQuery(q)}>
                {q}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
