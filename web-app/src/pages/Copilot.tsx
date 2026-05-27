import { useState, useRef, useEffect, useCallback } from 'react';
import { copilotChat, copilotConfirm, copilotClear } from '../services/api';
import type { NavigateFn } from '../App';

interface Props { navigate: NavigateFn; }

interface ChatMsg {
  role: 'user' | 'bot' | 'confirmation';
  text: string;
  confirmationId?: string;
  imageUrl?: string;
}

const SUGGESTIONS = [
  { label: '💰 Balance', text: 'What is my current account balance?' },
  { label: '📊 Trades', text: 'Show my recent trades' },
  { label: '🤔 Last trade', text: 'Why did you take the last trade?' },
  { label: '📰 News', text: 'Any major news today?' },
  { label: '🛑 Stop bot', text: 'Stop the bot now' },
  { label: '📖 Chart', text: 'Generate a chart for GBPUSD' },
];

export default function Copilot(_props: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: 'bot', text: "👋 Hi, I'm FUTURES. Ask me anything trading related and about your account management." },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setShowSuggestions(false);
    const userMsg: ChatMsg = { role: 'user', text: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const result = await copilotChat(trimmed);
    setLoading(false);

    if (!result) {
      setMessages((prev) => [...prev, { role: 'bot', text: 'Sorry, I could not reach the server. Please try again.' }]);
      return;
    }

    if (result.confirmation_id) {
      setMessages((prev) => [...prev, {
        role: 'confirmation',
        text: result.reply,
        confirmationId: result.confirmation_id,
      }]);
    } else {
      setMessages((prev) => [...prev, { role: 'bot', text: result.reply }]);
    }
  }, [loading]);

  async function handleConfirm(confirmationId: string) {
    setLoading(true);
    const result = await copilotConfirm(confirmationId);
    setLoading(false);
    if (result) {
      setMessages((prev) => prev.map((m) =>
        m.confirmationId === confirmationId ? { ...m, role: 'bot' as const, confirmationId: undefined } : m
      ));
      setMessages((prev) => [...prev, { role: 'bot', text: result.reply }]);
    } else {
      setMessages((prev) => prev.map((m) =>
        m.confirmationId === confirmationId ? { ...m, role: 'bot' as const, confirmationId: undefined } : m
      ));
      setMessages((prev) => [...prev, { role: 'bot', text: 'Confirmation failed. Please try again.' }]);
    }
  }

  function handleCancel(confirmationId: string) {
    setMessages((prev) => prev.map((m) =>
      m.confirmationId === confirmationId ? { ...m, role: 'bot' as const, text: m.text + ' (cancelled)', confirmationId: undefined } : m
    ));
  }

  async function handleClear() {
    await copilotClear();
    setMessages([
      { role: 'bot', text: "👋 Hi, I'm FUTURES. Ask me anything trading related and about your account management." },
    ]);
    setShowSuggestions(true);
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="page page-chat">
      {/* Messages */}
      <div className="chat-area">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role === 'user' ? 'user' : 'bot'}`}>
            <span>{msg.text}</span>
            {msg.imageUrl && <img src={msg.imageUrl} alt="Chart" className="chart-img" loading="lazy" />}
            {msg.role === 'confirmation' && msg.confirmationId && (
              <div className="confirmation-actions">
                <button className="btn-primary btn-sm" onClick={() => handleConfirm(msg.confirmationId!)} disabled={loading}>
                  {loading ? 'Processing...' : '✅ Confirm'}
                </button>
                <button className="btn-secondary btn-sm" onClick={() => handleCancel(msg.confirmationId!)} disabled={loading}>
                  ❌ Cancel
                </button>
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="typing-indicator visible">
            <span></span><span></span><span></span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Suggestions */}
      {showSuggestions && messages.length <= 2 && (
        <div className="suggestions-wrapper">
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s.label} className="chip" onClick={() => sendMessage(s.text)} disabled={loading}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="input-area">
        <button className="btn-icon" onClick={handleClear} title="Clear conversation">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
        <div className="input-wrapper">
          <input ref={inputRef} type="text" className="chat-input" value={input}
            onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
            placeholder="Ask FUTURES..." disabled={loading} />
        </div>
        <button className="btn-icon send" onClick={() => sendMessage(input)} disabled={loading || !input.trim()}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
    </div>
  );
}
