import { useState, useEffect } from 'react'
import { useAuth } from '../AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function EscalationPanel() {
  const { token } = useAuth()
  const [escalations, setEscalations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // State for reply inputs
  const [replies, setReplies] = useState({})
  const [sending, setSending] = useState({})

  useEffect(() => {
    fetchEscalations()
  }, [])

  async function fetchEscalations() {
    try {
      const res = await fetch(`${API_URL}/admin/escalations`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Error al cargar las derivaciones')
      const data = await res.json()
      setEscalations(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleReplyChange(id, text) {
    setReplies(prev => ({ ...prev, [id]: text }))
  }

  async function handleSendReply(id) {
    const text = replies[id]?.trim()
    if (!text) return

    setSending(prev => ({ ...prev, [id]: true }))
    try {
      const res = await fetch(`${API_URL}/admin/escalations/${id}/reply`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ message: text })
      })

      if (!res.ok) throw new Error('No se pudo enviar la respuesta')

      // Remove from list
      setEscalations(prev => prev.filter(e => e.id !== id))
      // Clear reply state
      setReplies(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    } catch (err) {
      alert(err.message)
    } finally {
      setSending(prev => ({ ...prev, [id]: false }))
    }
  }

  if (loading) return <div className="p-8 text-center text-ink/60">Cargando derivaciones...</div>
  if (error) return <div className="p-8 text-center text-stamp">{error}</div>

  if (escalations.length === 0) {
    return (
      <div className="p-12 text-center">
        <p className="text-lg text-ink/70">No hay derivaciones pendientes 🎉</p>
        <p className="text-sm text-ink/40 mt-2">Todas las consultas fueron resueltas por el agente o por contadores.</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="mb-8">
        <h2 className="text-2xl font-display font-semibold text-ink">Derivaciones Pendientes</h2>
        <p className="text-ink/60 text-sm mt-1">Consultas que el asistente no pudo responder y requieren atención profesional.</p>
      </div>

      <div className="grid gap-6">
        {escalations.map((esc) => (
          <div key={esc.id} className="bg-white border border-line rounded-lg shadow-sm p-5 flex flex-col gap-4">
            <div className="flex justify-between items-start border-b border-line/50 pb-3">
              <div>
                <p className="text-xs font-mono uppercase tracking-wider text-ink/40">Ticket ID: {esc.id.split('-')[0]}</p>
                <p className="text-sm text-ink/60 font-medium">Usuario: {esc.user_name || esc.user_id}</p>
              </div>
              <span className="text-xs text-ink/40 font-mono">
                {new Date(esc.created_at).toLocaleString('es-AR')}
              </span>
            </div>

            <div className="bg-slate-50 border border-line p-4 rounded-md space-y-4">
              <div>
                <h3 className="text-xs font-bold text-ink/50 uppercase tracking-widest mb-1 flex items-center gap-2">
                  <span className="text-brass">●</span> Resumen del caso
                </h3>
                <p className="text-ink text-[14px]">
                  {esc.summary}
                </p>
              </div>
              <div className="border-t border-line/50 pt-4">
                <h3 className="text-xs font-bold text-ink/50 uppercase tracking-widest mb-1 flex items-center gap-2">
                  <span className="text-brass">●</span> Última pregunta del usuario
                </h3>
                <p className="text-ink text-[15px] font-medium">
                  {esc.original_query}
                </p>
              </div>
            </div>

            <div className="mt-2">
              <textarea
                value={replies[esc.id] || ''}
                onChange={(e) => handleReplyChange(esc.id, e.target.value)}
                placeholder="Escribe la respuesta que recibirá el cliente..."
                className="w-full h-24 p-3 border border-line rounded-md text-sm focus:outline-none focus:border-brass focus:ring-1 focus:ring-brass transition-colors resize-none"
              />
              <div className="flex justify-end mt-3">
                <button
                  onClick={() => handleSendReply(esc.id)}
                  disabled={!replies[esc.id]?.trim() || sending[esc.id]}
                  className="bg-ledger text-paper px-5 py-2 rounded font-medium text-sm disabled:opacity-50 hover:bg-ink transition-colors"
                >
                  {sending[esc.id] ? 'Enviando...' : 'Enviar Respuesta'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
