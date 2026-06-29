import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { useAuth } from './AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Detecta si la respuesta menciona una fuente documental
function extraerFuente(texto) {
  if (!texto || typeof texto !== 'string') return null
  const match = texto.match(/\(?[Ff]uente:\s*([^).\n]+)\)?/)
  return match ? match[1].trim() : null
}

const SUGGESTIONS = [
  '¿Cuándo vence mi declaración de IVA este mes?',
  '¿Qué documentación necesito para inscribirme como responsable inscripto?',
  '¿En qué categoría de monotributo entro si facturo $15M al año?',
]

// ── Sub-componentes ──────────────────────────────────────────────────────────

function Avatar({ role }) {
  if (role === 'user') {
    return (
      <div className="w-8 h-8 rounded-sm bg-ledger text-paper flex items-center justify-center text-xs font-body font-medium shrink-0">
        Vos
      </div>
    )
  }
  return (
    <div className="w-8 h-8 rounded-sm border border-brass/60 bg-paper text-ledger flex items-center justify-center shrink-0">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M4 4h12l4 4v12H4z" />
        <path d="M16 4v4h4" />
        <path d="M8 12h8M8 16h5" />
      </svg>
    </div>
  )
}

function SourceBadge({ source }) {
  return (
    <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-1 border border-stamp/40 text-stamp text-[11px] font-mono uppercase tracking-wide rotate-[-0.4deg] rounded-sm">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
      </svg>
      fuente · {source}
    </div>
  )
}

function Message({ role, content }) {
  const isUser = role === 'user'
  const safeContent = typeof content === 'string' ? content : ''
  const source = !isUser ? extraerFuente(safeContent) : null
  const displayContent = !isUser && source ? safeContent.replace(/\(?[Ff]uente:\s*([^).\n]+)\)?/, '').trim() : safeContent

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <Avatar role={role} />
      <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div
          className={
            isUser
              ? 'bg-ledger text-paper rounded-lg rounded-tr-sm px-4 py-2.5 font-body text-[15px] leading-relaxed'
              : 'bg-white/70 text-ink border border-line rounded-lg rounded-tl-sm px-4 py-2.5 font-body text-[15px] leading-relaxed shadow-sm'
          }
        >
          {isUser ? (
            displayContent
          ) : (
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-headings:my-2 prose-headings:text-ink prose-strong:text-ink prose-a:text-stamp">
              <ReactMarkdown>
                {displayContent}
              </ReactMarkdown>
            </div>
          )}
        </div>
        {source && <SourceBadge source={source} />}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <Avatar role="assistant" />
      <div className="bg-white/70 border border-line rounded-lg rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-ledger/50 dot-blink" style={{ animationDelay: '0s' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-ledger/50 dot-blink" style={{ animationDelay: '0.2s' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-ledger/50 dot-blink" style={{ animationDelay: '0.4s' }} />
      </div>
    </div>
  )
}

// ── Componente principal ─────────────────────────────────────────────────────

export default function App() {
  const { token, userId, name, logout } = useAuth()

  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Hola, soy el asistente virtual del estudio. Puedo ayudarte con vencimientos, categorías de monotributo y trámites frecuentes. ¿En qué te puedo ayudar?',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage(text) {
    const message = text.trim()
    if (!message || loading) return

    setMessages((prev) => [...prev, { role: 'user', content: message }])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,  // JWT — el backend extrae el user_id
        },
        body: JSON.stringify({ message }),  // sin session_id
      })

      if (res.status === 401) {
        logout()
        return
      }
      if (!res.ok) {
        throw new Error(`The server responded with status ${res.status}`)
      }

      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }])
    } catch (err) {
      setError('No se pudo contactar al asistente. Verificá que el backend esté corriendo.')
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    sendMessage(input)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-6 md:py-10">
      <div className="w-full max-w-2xl flex flex-col h-[88vh]">

        {/* Header styled like an accounting file cover */}
        <header className="border-b-2 border-ink/80 pb-4 mb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-stamp mb-1">
                Estudio Contable · Atención al Cliente
              </p>
              <h1 className="font-display text-2xl md:text-3xl text-ink font-semibold">
                Asistente Virtual
              </h1>
            </div>
            <div className="flex flex-col items-end gap-2">
              <span className="font-mono text-[10px] text-ink/40 truncate max-w-[140px]">
                {name}
              </span>
              <button
                onClick={logout}
                className="font-body text-xs text-ink/50 border border-line rounded px-2.5 py-1 hover:border-stamp/50 hover:text-stamp transition-colors"
              >
                Cerrar sesión
              </button>
            </div>
          </div>
        </header>

        {/* Message list */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto scroll-ledger pr-1 space-y-5">
          {messages.map((m, i) => (
            <Message key={i} role={m.role} content={m.content} />
          ))}
          {loading && <TypingIndicator />}
        </div>

        {/* Error global */}
        {error && (
          <div role="alert" className="mt-3 text-sm text-stamp border border-stamp/40 bg-stamp/5 rounded-sm px-3 py-2 font-body">
            {error}
          </div>
        )}

        {/* Quick suggestions, shown only at the start */}
        {messages.length === 1 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => sendMessage(s)}
                className="text-xs font-body text-ledger border border-ledger/30 rounded-full px-3 py-1.5 hover:bg-ledger hover:text-paper transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Input + acciones */}
        <div className="mt-4 border-t border-line pt-4 space-y-2">
          <form onSubmit={handleSubmit} className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage(input)
                }
              }}
              placeholder="Escribí tu consulta…"
              rows={1}
              className="flex-1 resize-none bg-white/60 border border-line rounded-md px-3 py-2.5 font-body text-[15px] text-ink placeholder:text-ink/40 focus:outline-none focus:ring-2 focus:ring-brass/50 focus:border-brass"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="bg-ink text-paper font-body text-sm font-medium px-4 py-2.5 rounded-md disabled:opacity-30 disabled:cursor-not-allowed hover:bg-ledger transition-colors"
            >
              Enviar
            </button>
          </form>

          {/* Botón de derivación manual */}
        </div>

      </div>
    </div>
  )
}
