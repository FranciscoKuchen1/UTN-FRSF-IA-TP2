import { useState, useCallback, useEffect } from 'react'
import { useAuth } from './AuthContext'
import EscalationPanel from './components/EscalationPanel'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/** Formatea bytes en KB / MB legibles */
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Icono de documento */
function DocIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="shrink-0">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
    </svg>
  )
}

/** Fila de un documento ya subido */
function UploadedRow({ item }) {
  const ok = item.status === 'ok'
  return (
    <div className={`flex items-start gap-3 px-4 py-3 rounded-md border ${ok ? 'border-line bg-white/40' : 'border-stamp/30 bg-stamp/5'}`}>
      <span className={ok ? 'text-ledger mt-0.5' : 'text-stamp mt-0.5'}>
        <DocIcon />
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-body text-sm text-ink font-medium truncate">{item.name}</p>
        {ok ? (
          <p className="font-mono text-[11px] text-ink/50 mt-0.5">
            {item.chunks} chunks generados · {item.size}
          </p>
        ) : (
          <p className="font-mono text-[11px] text-stamp mt-0.5">{item.error}</p>
        )}
      </div>
      <span className={`font-mono text-[10px] uppercase tracking-wide shrink-0 mt-0.5 ${ok ? 'text-ledger' : 'text-stamp'}`}>
        {ok ? 'Indexado' : 'Error'}
      </span>
    </div>
  )
}

export default function AdminPanel() {
  const { token, logout } = useAuth()

  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [dropError, setDropError] = useState(null)
  const [currentTab, setCurrentTab] = useState('upload')

  // Estado para la pestaña de configuración
  const [contactInfo, setContactInfo] = useState('')
  const [savingContact, setSavingContact] = useState(false)
  const [contactSaved, setContactSaved] = useState(false)

  // Cargar info de contacto
  useEffect(() => {
    if (currentTab === 'settings') {
      fetch(`${API_URL}/settings/contact`)
        .then(res => res.json())
        .then(data => setContactInfo(data.contact_info || ''))
        .catch(() => {})
    }
  }, [currentTab])

  async function handleSaveContact(e) {
    e.preventDefault()
    setSavingContact(true)
    setContactSaved(false)
    try {
      await fetch(`${API_URL}/admin/settings/contact`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ contact_info: contactInfo })
      })
      setContactSaved(true)
      setTimeout(() => setContactSaved(false), 3000)
    } catch (err) {
      console.error(err)
    } finally {
      setSavingContact(false)
    }
  }

  // ── Validación de archivo ────────────────────────────────────────────────
  function validateFile(file) {
    const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    const allowedExt = ['.pdf', '.docx']
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!allowed.includes(file.type) && !allowedExt.includes(ext)) {
      return `"${file.name}" no es un PDF ni un .docx válido.`
    }
    if (file.size > 20 * 1024 * 1024) {
      return `"${file.name}" supera el límite de 20 MB.`
    }
    return null
  }

  // ── Upload ───────────────────────────────────────────────────────────────
  const uploadFile = useCallback(async (file) => {
    const validationError = validateFile(file)
    if (validationError) {
      setDropError(validationError)
      return
    }

    setDropError(null)
    setUploading(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_URL}/admin/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setUploadedFiles(prev => [...prev, {
          name: file.name,
          size: formatBytes(file.size),
          status: 'error',
          error: data.detail || `Error ${res.status}`,
        }])
        return
      }

      const data = await res.json()
      setUploadedFiles(prev => [...prev, {
        name: data.nombre ?? file.name,
        size: formatBytes(file.size),
        chunks: data.chunks_generados ?? '—',
        status: 'ok',
      }])

    } catch {
      setUploadedFiles(prev => [...prev, {
        name: file.name,
        size: formatBytes(file.size),
        status: 'error',
        error: 'No se pudo contactar al servidor.',
      }])
    } finally {
      setUploading(false)
    }
  }, [token])

  // ── Drag & Drop ─────────────────────────────────────────────────────────
  function onDragOver(e) {
    e.preventDefault()
    setIsDragging(true)
  }
  function onDragLeave() { setIsDragging(false) }
  function onDrop(e) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }

  function onFileInputChange(e) {
    const file = e.target.files[0]
    if (file) uploadFile(file)
    e.target.value = ''   // permite seleccionar el mismo archivo dos veces
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-8 md:py-12">
      <div className="w-full max-w-xl flex flex-col gap-6">

        {/* Encabezado */}
        <div className="bg-white border border-line rounded-lg shadow-sm p-6 sm:p-8">

          {/* Pestañas */}
          <div className="flex gap-6 border-b border-line mb-8">
            <button
              className={`pb-3 text-sm font-medium transition-colors relative ${currentTab === 'upload' ? 'text-ink' : 'text-ink/50 hover:text-ink'}`}
              onClick={() => setCurrentTab('upload')}
            >
              Documentos RAG
              {currentTab === 'upload' && <span className="absolute bottom-0 left-0 w-full h-[2px] bg-brass rounded-t-sm" />}
            </button>
            <button
              className={`pb-3 text-sm font-medium transition-colors relative ${currentTab === 'escalations' ? 'text-ink' : 'text-ink/50 hover:text-ink'}`}
              onClick={() => setCurrentTab('escalations')}
            >
              Derivaciones a Humano
              {currentTab === 'escalations' && <span className="absolute bottom-0 left-0 w-full h-[2px] bg-brass rounded-t-sm" />}
            </button>
            <button
              className={`pb-3 text-sm font-medium transition-colors relative ${currentTab === 'settings' ? 'text-ink' : 'text-ink/50 hover:text-ink'}`}
              onClick={() => setCurrentTab('settings')}
            >
              Configuración
              {currentTab === 'settings' && <span className="absolute bottom-0 left-0 w-full h-[2px] bg-brass rounded-t-sm" />}
            </button>
          </div>

          {currentTab === 'upload' ? (
            <>
              <header className="mb-6">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-stamp mb-1">
                      Panel de Administración · Contador
                    </p>
                    <h1 className="font-display text-2xl md:text-3xl text-ink font-semibold">
                      Base de Conocimiento
                    </h1>
                  </div>
                  <button
                    onClick={logout}
                    className="font-body text-xs text-ink/50 border border-line rounded px-2.5 py-1.5 hover:border-stamp/50 hover:text-stamp transition-colors"
                  >
                    Cerrar sesión
                  </button>
                </div>
                <p className="font-body text-sm text-ink/50 mt-2">
                  Cargá documentos PDF o Word para actualizar la base de conocimiento del agente.
                </p>
              </header>

              {/* Zona drag & drop */}
              <div
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                className={`
            relative border-2 border-dashed rounded-lg px-6 py-12 flex flex-col items-center justify-center gap-3 transition-colors
            ${isDragging
                    ? 'border-brass bg-brass/5 scale-[1.01]'
                    : 'border-line bg-white/30 hover:border-brass/50 hover:bg-white/50'}
          `}
              >
                {/* Icono */}
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3"
                  className={`transition-colors ${isDragging ? 'text-brass' : 'text-ink/30'}`}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>

                <p className="font-body text-sm text-ink/60 text-center">
                  {isDragging
                    ? 'Soltá el archivo para subirlo'
                    : 'Arrastrá un archivo PDF o Word acá, o hacé clic para seleccionar'}
                </p>
                <p className="font-mono text-[11px] text-ink/40 uppercase tracking-wide">
                  .pdf · .docx · máx. 20 MB
                </p>

                {/* Input oculto */}
                <label className={`
            mt-1 inline-flex items-center gap-2 bg-ink text-paper font-body text-sm font-medium
            px-4 py-2 rounded-md cursor-pointer hover:bg-ledger transition-colors
            ${uploading ? 'opacity-40 pointer-events-none' : ''}
          `}>
                  {uploading ? (
                    <>
                      <span className="inline-block w-4 h-4 border-2 border-paper/30 border-t-paper rounded-full animate-spin" />
                      Subiendo…
                    </>
                  ) : (
                    'Seleccionar archivo'
                  )}
                  <input
                    type="file"
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    className="hidden"
                    disabled={uploading}
                    onChange={onFileInputChange}
                  />
                </label>
              </div>

              {/* Error de validación */}
              {dropError && (
                <div role="alert" className="text-sm text-stamp border border-stamp/30 bg-stamp/5 rounded-sm px-3 py-2 font-body">
                  {dropError}
                </div>
              )}

              {/* Listado de subidas */}
              {uploadedFiles.length > 0 && (
                <section>
                  <h2 className="font-mono text-[11px] uppercase tracking-widest text-ink/50 mb-3">
                    Documentos subidos en esta sesión
                  </h2>
                  <div className="flex flex-col gap-2">
                    {uploadedFiles.map((item, i) => (
                      <UploadedRow key={i} item={item} />
                    ))}
                  </div>
                </section>
              )}
            </>) : currentTab === 'escalations' ? (
            <div className="-mx-6 -my-4">
              <EscalationPanel />
            </div>
          ) : (
            <div>
              <header className="mb-6">
                <h2 className="font-display text-xl text-ink font-semibold">Configuración General</h2>
                <p className="font-body text-sm text-ink/50 mt-1">
                  Ajustá el teléfono o email de contacto que el bot le dará a los clientes al derivar.
                </p>
              </header>
              
              <form onSubmit={handleSaveContact} className="max-w-md">
                <div className="mb-4">
                  <label className="block text-sm font-medium text-ink mb-2">Teléfono o Email de Contacto</label>
                  <input 
                    type="text" 
                    value={contactInfo} 
                    onChange={(e) => setContactInfo(e.target.value)}
                    placeholder="Ej: info@estudio.com o 0800-123-4567"
                    className="w-full bg-white/60 border border-line rounded-md px-3 py-2 font-body text-sm text-ink focus:outline-none focus:ring-1 focus:ring-brass focus:border-brass"
                  />
                </div>
                <button 
                  type="submit" 
                  disabled={savingContact}
                  className="bg-ink text-paper text-sm font-medium px-4 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                >
                  {savingContact ? 'Guardando...' : 'Guardar Contacto'}
                </button>
                {contactSaved && <p className="text-ledger text-sm mt-3 font-medium">¡Guardado exitosamente!</p>}
              </form>
            </div>
          )}

          <p className="text-center font-mono text-[10px] uppercase tracking-widest text-ink/25 mt-8">
            Sistema de atención al cliente · TP2 · UTN FRSF
          </p>
        </div>
      </div>
    </div>
  )
}
