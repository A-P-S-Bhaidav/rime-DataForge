import { useState, useEffect, useCallback, useRef } from 'react';

export interface UseSpeechRecognitionReturn {
  transcript: string;
  interimTranscript: string;
  isListening: boolean;
  isSupported: boolean;
  startListening: () => void;
  stopListening: () => void;
  error: string | null;
}

export function useSpeechRecognition(): UseSpeechRecognitionReturn {
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const recognition = useRef<any>(null);
  const isSupported = typeof window !== 'undefined' && 
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  useEffect(() => {
    if (!isSupported) return;
    
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    recognition.current = new SpeechRecognition();
    recognition.current.continuous = true;
    recognition.current.interimResults = true;
    recognition.current.lang = 'en-US';
    
    recognition.current.onresult = (event: any) => {
      let currentTranscript = '';
      let currentInterim = '';
      
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcriptSegment = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          currentTranscript += transcriptSegment + ' ';
        } else {
          currentInterim += transcriptSegment;
        }
      }
      
      if (currentTranscript) {
        setTranscript(prev => prev + currentTranscript);
      }
      setInterimTranscript(currentInterim);
    };
    
    recognition.current.onerror = (event: any) => {
      console.error('Speech recognition error', event.error);
      setError(event.error);
      if (event.error !== 'no-speech') {
        setIsListening(false);
      }
    };
    
    recognition.current.onend = () => {
      // If we're supposed to be listening but it ended, restart
      if (isListening) {
        try {
          recognition.current?.start();
        } catch (e) {
          setIsListening(false);
        }
      } else {
        setIsListening(false);
      }
    };
    
    return () => {
      if (recognition.current) {
        recognition.current.stop();
      }
    };
  }, [isSupported, isListening]);

  const startListening = useCallback(() => {
    setError(null);
    setTranscript('');
    setInterimTranscript('');
    setIsListening(true);
    
    try {
      recognition.current?.start();
    } catch (e) {
      console.error('Could not start recognition', e);
      // Already started or other error
    }
  }, []);

  const stopListening = useCallback(() => {
    setIsListening(false);
    try {
      recognition.current?.stop();
    } catch (e) {}
  }, []);

  return {
    transcript,
    interimTranscript,
    isListening,
    isSupported,
    startListening,
    stopListening,
    error
  };
}
