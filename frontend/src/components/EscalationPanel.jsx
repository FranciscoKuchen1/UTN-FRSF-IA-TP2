import { useState, useEffect } from 'react'
import { useAuth } from '../AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function EscalationPanel() {
  const { token } = useAuth()
  const [escalations, setEscalations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // State for delete modal
  const [ticketToDelete, setTicketToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

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

  async function confirmDelete() {
    if (!ticketToDelete) return
    setIsDeleting(true)
    
    try {
      const res = await fetch(`${API_URL}/admin/escalations/${ticketToDelete}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      })

      if (!res.ok) throw new Error('No se pudo eliminar el ticket')

      // Remove from list
      setEscalations(prev => prev.filter(e => e.id !== ticketToDelete))
      setTicketToDelete(null)
    } catch (err) {
      alert(err.message)
    } finally {
      setIsDeleting(false)
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

            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setTicketToDelete(esc.id)}
                className="flex items-center gap-2 bg-ledger/10 text-ledger px-4 py-2 rounded-md font-medium text-sm hover:bg-ledger/20 transition-colors"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                Marcar como respondida
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Delete Confirmation Modal */}
      {ticketToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40 backdrop-blur-sm">
          <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6 border border-line">
            <h3 className="text-lg font-display font-semibold text-ink mb-2">
              ¿Confirmar acción?
            </h3>
            <p className="text-sm text-ink/70 font-body mb-6">
              Esta acción eliminará el ticket de la base de datos permanentemente. Asegurate de haberte comunicado con el cliente por tu cuenta antes de marcarla como respondida.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setTicketToDelete(null)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-ink/60 hover:text-ink transition-colors disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={confirmDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium bg-ledger text-paper rounded hover:bg-ink transition-colors disabled:opacity-50"
              >
                {isDeleting ? 'Eliminando...' : 'Sí, marcar y eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
