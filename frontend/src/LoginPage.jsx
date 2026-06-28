import { useState } from 'react'
import { useAuth } from './AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (loading) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Email o contraseña incorrectos.')
        return
      }

      const data = await res.json()
      // data = { access_token, user_id, role, name }
      login(data.access_token, data.role ?? 'cliente', data.user_id, data.name)

    } catch {
      setError('No se pudo conectar con el servidor. Verificá que el backend esté activo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">

      {/* Tarjeta tipo carátula de expediente */}
      <div className="w-full max-w-sm">

        {/* Encabezado */}
        <div className="border-b-2 border-ink/80 pb-5 mb-7 text-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-stamp mb-1">
            Estudio Contable · Acceso al Sistema
          </p>
          <h1 className="font-display text-3xl text-ink font-semibold">
            Asistente Virtual
          </h1>
          <p className="font-body text-sm text-ink/50 mt-1">
            Ingresá con tus credenciales para continuar
          </p>
        </div>

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="space-y-4">

          {/* Email */}
          <div>
            <label
              htmlFor="login-email"
              className="block font-mono text-[11px] uppercase tracking-widest text-ink/60 mb-1.5"
            >
              Correo electrónico
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="usuario@estudio.com"
              className="w-full bg-white/60 border border-line rounded-md px-3 py-2.5 font-body text-[15px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-brass/50 focus:border-brass transition-colors"
            />
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="login-password"
              className="block font-mono text-[11px] uppercase tracking-widest text-ink/60 mb-1.5"
            >
              Contraseña
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-white/60 border border-line rounded-md px-3 py-2.5 font-body text-[15px] text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-brass/50 focus:border-brass transition-colors"
            />
          </div>

          {/* Error inline */}
          {error && (
            <div
              role="alert"
              className="text-sm text-stamp border border-stamp/30 bg-stamp/5 rounded-sm px-3 py-2 font-body"
            >
              {error}
            </div>
          )}

          {/* Botón */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-ink text-paper font-body text-sm font-medium py-2.5 rounded-md disabled:opacity-40 disabled:cursor-not-allowed hover:bg-ledger transition-colors mt-2"
          >
            {loading ? 'Verificando…' : 'Ingresar'}
          </button>

        </form>

        {/* Pie */}
        <p className="mt-8 text-center font-mono text-[10px] uppercase tracking-widest text-ink/30">
          Sistema de atención al cliente · TP2 · UTN FRSF
        </p>
      </div>
    </div>
  )
}
