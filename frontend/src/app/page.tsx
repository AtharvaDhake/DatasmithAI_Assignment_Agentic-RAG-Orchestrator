"use client";

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';

type Citation = {
  text: string;
  page: number;
  source: string;
};

type Message = {
  id: string;
  role: 'user' | 'bot';
  content: string;
  citations?: Citation[];
  isTyping?: boolean;
  isClarification?: boolean;
  extractedText?: string;
  executionLog?: string[];
  fileName?: string;
  fileUrl?: string;
  fileType?: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileUrl, setSelectedFileUrl] = useState<string | null>(null);
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set());
  const [expandedTexts, setExpandedTexts] = useState<Set<string>>(new Set());
  const [showUploadMenu, setShowUploadMenu] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMenuRef = useRef<HTMLDivElement>(null);
  const uploadButtonRef = useRef<HTMLButtonElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        showUploadMenu &&
        uploadMenuRef.current &&
        !uploadMenuRef.current.contains(event.target as Node) &&
        uploadButtonRef.current &&
        !uploadButtonRef.current.contains(event.target as Node)
      ) {
        setShowUploadMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showUploadMenu]);

  const handleUploadOptionClick = (type: 'image' | 'pdf' | 'audio') => {
    if (!fileInputRef.current) return;
    
    if (type === 'image') {
      fileInputRef.current.accept = 'image/jpeg,image/png,image/jpg';
    } else if (type === 'pdf') {
      fileInputRef.current.accept = 'application/pdf';
    } else if (type === 'audio') {
      fileInputRef.current.accept = 'audio/mpeg,audio/wav,audio/mp4,audio/m4a,audio/x-m4a';
    }
    
    fileInputRef.current.click();
    setShowUploadMenu(false);
  };



  const playSound = (type: 'send' | 'receive' | 'typing') => {
    try {
      const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'send') {
        osc.type = 'square';
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1);
        osc.start();
        osc.stop(ctx.currentTime + 0.1);
      } else if (type === 'receive') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
        osc.start();
        osc.stop(ctx.currentTime + 0.15);
      } else if (type === 'typing') {
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(600, ctx.currentTime);
        gain.gain.setValueAtTime(0.02, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
        osc.start();
        osc.stop(ctx.currentTime + 0.05);
      }
    } catch (e) {
      // audio can fail on some browsers, not critical
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }, [theme]);

  // Automatic height adjustment removed to maintain stable text box size

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLoading) {
      interval = setInterval(() => { playSound('typing'); }, 400);
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  const toggleLog = (msgId: string) => {
    setExpandedLogs(prev => {
      const next = new Set(prev);
      next.has(msgId) ? next.delete(msgId) : next.add(msgId);
      return next;
    });
  };

  const toggleText = (msgId: string) => {
    setExpandedTexts(prev => {
      const next = new Set(prev);
      next.has(msgId) ? next.delete(msgId) : next.add(msgId);
      return next;
    });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setSelectedFileUrl(URL.createObjectURL(file));
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    setSelectedFileUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) {
          e.preventDefault();
          setSelectedFile(file);
          setSelectedFileUrl(URL.createObjectURL(file));
          break;
        }
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && !selectedFile) || isLoading) return;

    playSound('send');

    const currentInput = input;
    const currentFile = selectedFile;
    const currentFileUrl = selectedFileUrl;

    const displayContent = currentInput.trim();

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: displayContent,
      fileName: currentFile?.name,
      fileUrl: currentFileUrl || undefined,
      fileType: currentFile?.type,
    };
    setMessages(prev => [...prev, userMsg]);

    setInput('');
    clearFile();
    setIsLoading(true);

    const typingId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, { id: typingId, role: 'bot', content: '', isTyping: true }]);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

      const formData = new FormData();
      formData.append('query', currentInput);
      if (currentFile) {
        formData.append('file', currentFile);
      }

      const historyPayload = messages.map(msg => ({
        role: msg.role,
        content: msg.content,
        extractedText: msg.extractedText
      }));
      formData.append('history', JSON.stringify(historyPayload));

      const res = await fetch(`${apiUrl}/process`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || `Server error: ${res.status}`);
      }

      const data = await res.json();
      playSound('receive');

      const isClarification = data.response_type === 'clarification';

      setMessages(prev =>
        prev.map(msg =>
          msg.id === typingId
            ? {
                ...msg,
                isTyping: false,
                content: data.result,
                citations: data.metadata?.citations,
                isClarification,
                extractedText: data.extracted_text || undefined,
                executionLog: data.execution_log || undefined,
              }
            : msg
        )
      );
    } catch (error: any) {
      playSound('receive');
      setMessages(prev =>
        prev.map(msg =>
          msg.id === typingId
            ? { ...msg, isTyping: false, content: `Error: ${error.message || 'Connection failed'}` }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-brand">
          <div className="header-avatar">A</div>
          <div className="header-text-container">
            <h1 className="header-title">Agentic-RAG-Orchestrator</h1>
            <p className="header-subtitle">DatasmithAI</p>
          </div>
        </div>
        <button
          onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
          className="theme-toggle"
        >
          {theme === 'dark' ? 'LIGHT' : 'DARK'}
        </button>
      </header>

      <main className="chat-container">
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '50px', color: '#666', fontFamily: 'JetBrains Mono' }}>
            <p style={{ fontSize: '1rem', marginBottom: '8px' }}>System ready. Awaiting input.</p>
            <p style={{ fontSize: '0.75rem', color: '#555' }}>
              Upload images, PDFs, audio files, or type a query.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`message-wrapper ${msg.role}`}>
            <div className={`avatar ${msg.role}`}>
              {msg.role === 'user' ? 'U' : 'A'}
            </div>
            
            <div className="message-content-area">
              <div className={`message-bubble ${msg.isClarification ? 'clarification-bubble' : ''}`}>
                {msg.isTyping ? (
                  <div className="typing-dots">
                    <div className="dot"></div>
                    <div className="dot"></div>
                    <div className="dot"></div>
                  </div>
                ) : (
                  <div className="markdown-body">
                    {msg.fileUrl && msg.fileType && (
                      <div style={{ marginBottom: msg.content ? '10px' : '0' }}>
                        {msg.fileType.startsWith('image/') && (
                          <img src={msg.fileUrl} alt="uploaded" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '8px' }} />
                        )}
                        {msg.fileType.startsWith('audio/') && (
                          <audio controls src={msg.fileUrl} style={{ width: '100%', outline: 'none' }} />
                        )}
                        {msg.fileType === 'application/pdf' && (
                          <embed src={msg.fileUrl} type="application/pdf" width="100%" height="300px" style={{ borderRadius: '8px' }} />
                        )}
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                          📎 {msg.fileName}
                        </div>
                      </div>
                    )}
                    {msg.content && (
                      msg.role === 'user' ? (
                        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit' }}>
                          {msg.content}
                        </div>
                      ) : (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code(props) {
                              const { children, className, node, ref, ...rest } = props as any;
                              const match = /language-(\w+)/.exec(className || '');
                              return match ? (
                                <SyntaxHighlighter
                                  {...rest}
                                  PreTag="div"
                                  children={String(children).replace(/\n$/, '')}
                                  language={match[1]}
                                  style={theme === 'dark' ? vscDarkPlus : vs}
                                  customStyle={{ borderRadius: '8px', padding: '12px', fontSize: '0.9rem', margin: '10px 0' }}
                                />
                              ) : (
                                <code {...rest} className={className}>
                                  {children}
                                </code>
                              );
                            }
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      )
                    )}
                  </div>
                )}
              </div>

              {msg.extractedText && (
                <div className="extracted-panel">
                  <button className="panel-toggle" onClick={() => toggleText(msg.id)}>
                    {expandedTexts.has(msg.id) ? '▾' : '▸'} Extracted Text ({msg.extractedText.split(/\s+/).length} words)
                  </button>
                  {expandedTexts.has(msg.id) && (
                    <pre className="panel-content">{msg.extractedText}</pre>
                  )}
                </div>
              )}

              {msg.executionLog && msg.executionLog.length > 0 && (
                <div className="log-panel">
                  <button className="panel-toggle" onClick={() => toggleLog(msg.id)}>
                    {expandedLogs.has(msg.id) ? '▾' : '▸'} Execution Log ({msg.executionLog.length} steps)
                  </button>
                  {expandedLogs.has(msg.id) && (
                    <div className="panel-content log-content">
                      {msg.executionLog.map((step, i) => (
                        <div key={i} className="log-step">{step}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {msg.citations && msg.citations.length > 0 && (
                <div className="citations-container">
                  {msg.citations.map((cit, idx) => (
                    <button
                      key={idx}
                      className="citation-chip"
                      onClick={() => setActiveCitation(cit)}
                    >
                      [{idx + 1}] (p.{cit.page})
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </main>

      {selectedFile && selectedFileUrl && (
        <div className="file-badge" style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '10px', alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
            <span>📎 {selectedFile.name}</span>
            <button type="button" onClick={clearFile} className="file-badge-x">×</button>
          </div>
          <div style={{ width: '100%', maxWidth: '300px' }}>
             {selectedFile.type.startsWith('image/') && <img src={selectedFileUrl} style={{ maxWidth: '100%', maxHeight: '150px', borderRadius: '4px' }} alt="preview" />}
             {selectedFile.type.startsWith('audio/') && <audio controls src={selectedFileUrl} style={{ width: '100%', outline: 'none', height: '40px' }} />}
             {selectedFile.type === 'application/pdf' && <embed src={selectedFileUrl} type="application/pdf" width="100%" height="150px" style={{ borderRadius: '4px' }} />}
          </div>
        </div>
      )}

      <form className="input-container" onSubmit={handleSubmit}>
        {showUploadMenu && (
          <div className="upload-menu" ref={uploadMenuRef}>
            <button
              type="button"
              className="upload-menu-item"
              onClick={() => handleUploadOptionClick('image')}
            >
              <span className="upload-menu-icon">🖼️</span>
              <div className="upload-menu-text">
                <span className="upload-menu-title">Image (JPG/PNG)</span>
                <span className="upload-menu-desc">Analyze or extract text from images</span>
              </div>
            </button>
            <button
              type="button"
              className="upload-menu-item"
              onClick={() => handleUploadOptionClick('pdf')}
            >
              <span className="upload-menu-icon">📄</span>
              <div className="upload-menu-text">
                <span className="upload-menu-title">PDF (text or scanned)</span>
                <span className="upload-menu-desc">Query document contents and search pages</span>
              </div>
            </button>
            <button
              type="button"
              className="upload-menu-item"
              onClick={() => handleUploadOptionClick('audio')}
            >
              <span className="upload-menu-icon">🎵</span>
              <div className="upload-menu-text">
                <span className="upload-menu-title">Audio (MP3/WAV/M4A)</span>
                <span className="upload-menu-desc">Transcribe and query voice recordings</span>
              </div>
            </button>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/jpg,application/pdf,audio/mpeg,audio/wav,audio/mp4,audio/m4a,audio/x-m4a"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          id="file-upload"
        />
        <button
          ref={uploadButtonRef}
          type="button"
          className="upload-button"
          onClick={() => setShowUploadMenu(s => !s)}
          disabled={isLoading}
          title="Upload Image, PDF, or Audio"
        >
          📎
        </button>
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPaste={handlePaste}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (input.trim() || selectedFile) {
                handleSubmit(e as any);
              }
            }
          }}
          placeholder="Enter query or paste code (Shift+Enter for newline)..."
          disabled={isLoading}
          rows={1}
          style={{ resize: 'none', overflowY: 'auto' }}
        />
        <button type="submit" className="send-button" disabled={isLoading || (!input.trim() && !selectedFile)}>
          {isLoading ? '...' : 'SEND'}
        </button>
      </form>

      {/* Citation Modal */}
      {activeCitation && (
        <div className="modal-overlay" onClick={() => setActiveCitation(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setActiveCitation(null)}>×</button>
            <h3 style={{ marginBottom: '15px', fontFamily: 'JetBrains Mono', fontSize: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
              Citation Source (Page {activeCitation.page})
            </h3>
            <p className="modal-text">
              {activeCitation.text}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
