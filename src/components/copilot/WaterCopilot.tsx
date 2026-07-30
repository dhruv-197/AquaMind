import React, { FormEvent, useState } from 'react';
import { ChevronDown, LoaderCircle, Send } from 'lucide-react';
import { apiPost } from '../../services/apiClient';
import { AquaBotLogo } from './AquaBotLogo';

type Message = {
  role: 'user' | 'assistant';
  text: string;
  summarized?: boolean;
  source?: string;
  suggestions?: string[];
};

const starters = [
  'Today’s water shortage risk in Gujarat',
  'Rain forecast for Ahmedabad',
  'Groundwater depletion in Delhi',
];

export const WaterCopilot: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);

  const ask = async (question: string) => {
    const message = question.trim();
    if (!message || loading) return;

    const history = messages.map((item) => ({ role: item.role, text: item.text }));
    setMessages((items) => [...items, { role: 'user', text: message }]);
    setInput('');
    setLoading(true);

    try {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 45000);
      const body = await apiPost<{ data: any }>(
        '/ai/copilot/chat',
        { message, history },
        { signal: controller.signal }
      );
      window.clearTimeout(timeoutId);
      const data = body.data;
      setMessages((items) => [
        ...items,
        {
          role: 'assistant',
          text: data.answer,
          summarized: Boolean(data.summarized),
          source: data.source,
          suggestions: data.suggestions,
        },
      ]);
    } catch (error) {
      const timedOut =
        error instanceof DOMException && error.name === 'AbortError'
          ? 'AquaAI took too long to reply. Please try again.'
          : null;
      setMessages((items) => [
        ...items,
        {
          role: 'assistant',
          text: timedOut || (error instanceof Error ? error.message : 'AquaAI is unavailable.'),
          source: 'error',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    ask(input);
  };

  return (
    <div className="fixed right-4 bottom-4 z-50 w-[min(27rem,calc(100vw-2rem))]">
      {open && (
        <section
          className="mb-3 overflow-hidden rounded-2xl border border-sky-200/80 bg-gradient-to-b from-white via-[#f7fbff] to-[#eef7fb] shadow-[0_18px_50px_rgba(14,116,144,0.14)]"
        >
          <header className="flex items-center justify-between border-b border-sky-100 bg-white/90 px-4 py-3 backdrop-blur-sm">
            <div className="flex items-center gap-2.5">
              <AquaBotLogo size={34} className="drop-shadow-sm" />
              <div>
                <h2 className="text-[15px] font-bold text-slate-800">AquaAI</h2>
                <p className="text-[16px] font-medium text-slate-500">Your water-intelligence assistant</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close AquaAI"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-sky-50 hover:text-slate-700"
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </header>

          <div className="max-h-[26rem] min-h-44 space-y-3 overflow-y-auto px-4 py-3">
            {!messages.length && (
              <div className="space-y-3">
                <div className="rounded-2xl border border-sky-100 bg-white/80 px-3 py-3 shadow-sm">
                  <p className="text-[14px] leading-relaxed text-slate-600">
                    Hi, I'm AquaAI. Ask about rainfall, shortages, leaks, or groundwater. I’ll keep answers short and numeric.
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {starters.map((starter) => (
                    <button
                      key={starter}
                      type="button"
                      onClick={() => ask(starter)}
                      className="rounded-full border border-sky-200 bg-white px-2.5 py-1 text-left text-[16px] font-medium text-sky-800 shadow-sm transition hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800"
                    >
                      {starter}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, index) => (
              <article
                key={`${message.role}-${index}`}
                className={`rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed shadow-sm ${
                  message.role === 'user'
                    ? 'ml-8 bg-gradient-to-br from-sky-500 to-teal-500 text-white'
                    : 'mr-2 border border-sky-100 bg-white text-slate-800'
                }`}
              >
                {message.role === 'assistant' && (
                  <p className="mb-1.5 text-[15px] font-bold uppercase tracking-wide text-teal-600">
                    AquaAI
                  </p>
                )}
                <p className={`whitespace-pre-wrap ${message.role === 'user' ? 'text-white' : 'text-slate-800'}`}>
                  {message.text}
                </p>
                {message.suggestions && message.suggestions.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {message.suggestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        onClick={() => ask(suggestion)}
                        className="rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-[15px] font-semibold text-sky-800 transition hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
                {message.source && message.source !== 'local' && message.source !== 'error' && (
                  <p className="mt-2 text-[15px] font-medium text-slate-400">
                    {message.summarized ? 'AquaAI · key points' : 'Answered by AquaAI'}
                  </p>
                )}
              </article>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-[14px] font-medium text-slate-500">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin text-teal-500" />
                Asking AquaAI…
              </div>
            )}
          </div>

          <form onSubmit={submit} className="flex gap-2 border-t border-sky-100 bg-white/90 p-3 backdrop-blur-sm">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              maxLength={700}
              placeholder="Ask anything about water…"
              className="min-w-0 flex-1 rounded-xl border border-sky-200 bg-white px-3 py-2 text-[14px] text-slate-800 outline-none placeholder:text-slate-400 focus:border-teal-400 focus:ring-2 focus:ring-teal-100"
            />
            <button
              disabled={loading || !input.trim()}
              className="rounded-xl bg-gradient-to-br from-sky-500 to-teal-500 p-2.5 text-white shadow-md shadow-sky-200/60 transition hover:from-sky-400 hover:to-teal-400 disabled:opacity-45"
              aria-label="Send question"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="ml-auto flex items-center gap-2 rounded-2xl border border-sky-200 bg-white px-3.5 py-2.5 text-[14px] font-bold text-slate-800 shadow-lg shadow-sky-200/50 transition hover:border-teal-300 hover:bg-sky-50"
      >
        <AquaBotLogo size={28} />
        Ask AquaAI
      </button>
    </div>
  );
};
