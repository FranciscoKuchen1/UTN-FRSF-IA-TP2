import { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function ClientChatsPanel({ token }) {
  const [clients, setClients] = useState([])
  const [selectedClient, setSelectedClient] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_URL}/admin/clients`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setClients(data)
        }
      })
      .catch(err => console.error("Error loading clients:", err))
  }, [token])

  useEffect(() => {
    if (!selectedClient) {
      setChatHistory([])
      return
    }

    setLoading(true)
    setError(null)
    fetch(`${API_URL}/admin/chats/${selectedClient}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => {
        if (!res.ok) throw new Error('Error al cargar historial')
        return res.json()
      })
      .then(data => {
        setChatHistory(data || [])
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedClient, token])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-ink">Seleccionar Cliente:</label>
        <select
          value={selectedClient}
          onChange={(e) => setSelectedClient(e.target.value)}
          className="border border-line rounded px-3 py-2 text-sm bg-white"
        >
          <option value="">-- Seleccione un cliente --</option>
          {clients.map(c => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.email})
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-stamp text-sm bg-stamp/5 p-2 rounded">{error}</p>}

      {selectedClient && (
        <div className="border border-line rounded p-4 bg-paper max-h-[500px] overflow-y-auto space-y-4">
          {loading ? (
            <p className="text-sm text-ink/50 text-center">Cargando historial...</p>
          ) : chatHistory.length === 0 ? (
            <p className="text-sm text-ink/50 text-center">Este cliente aún no ha interactuado con el chat.</p>
          ) : (
            chatHistory.map((msg, idx) => (
              <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <span className="text-[10px] uppercase text-ink/40 mb-1">{msg.role === 'user' ? 'Cliente' : 'Agente'}</span>
                <div className={`px-3 py-2 rounded-lg max-w-[80%] text-sm ${msg.role === 'user' ? 'bg-ledger text-white rounded-tr-none' : 'bg-white border border-line rounded-tl-none'}`}>
                  {msg.content}
                </div>
                <span className="text-[10px] text-ink/30 mt-1">{new Date(msg.created_at).toLocaleString()}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
