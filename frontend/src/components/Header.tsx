import React from 'react';
import type { AppState } from '../types';

interface HeaderProps {
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error';
  appState: AppState;
}

export const Header: React.FC<HeaderProps> = ({ connectionState, appState }) => {
  return (
    <header className="header glass-card">
      <div className="logo">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#paint0_linear)"/>
          <path d="M2 17L12 22L22 17" stroke="url(#paint1_linear)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 12L12 17L22 12" stroke="url(#paint2_linear)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <defs>
            <linearGradient id="paint0_linear" x1="2" y1="7" x2="22" y2="7" gradientUnits="userSpaceOnUse">
              <stop stopColor="#6366f1"/>
              <stop offset="1" stopColor="#8b5cf6"/>
            </linearGradient>
            <linearGradient id="paint1_linear" x1="2" y1="19.5" x2="22" y2="19.5" gradientUnits="userSpaceOnUse">
              <stop stopColor="#6366f1"/>
              <stop offset="1" stopColor="#8b5cf6"/>
            </linearGradient>
            <linearGradient id="paint2_linear" x1="2" y1="14.5" x2="22" y2="14.5" gradientUnits="userSpaceOnUse">
              <stop stopColor="#6366f1"/>
              <stop offset="1" stopColor="#8b5cf6"/>
            </linearGradient>
          </defs>
        </svg>
        DataForge
      </div>
      
      <div className="status-badges">
        {appState === 'speaking' && (
          <div className="badge rime">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM10 16.5V7.5L16 12L10 16.5Z" fill="currentColor"/>
            </svg>
            Powered by Rime TTS
          </div>
        )}
        
        <div className="badge">
          <span style={{ textTransform: 'capitalize' }}>{appState}</span>
        </div>
        
        <div className={`badge ${connectionState === 'connected' ? 'connected' : 'disconnected'}`}>
          <div className="dot"></div>
          {connectionState === 'connected' ? 'Connected' : 'Offline'}
        </div>
      </div>
    </header>
  );
};
