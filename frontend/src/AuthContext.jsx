import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

/**
 * Provee token, role, user_id y las acciones login/logout.
 * El token se guarda en localStorage para mantener la sesión activa al recargar.
 */
export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    const storedAuth = localStorage.getItem('auth')
    if (storedAuth) {
      try {
        return JSON.parse(storedAuth)
      } catch (e) {
        console.error('Error parsing auth from localStorage', e)
      }
    }
    return {
      token: null,
      role: null,
      userId: null,
      name: null,
    }
  })

  function login(token, role, userId, name) {
    const newAuth = { token, role, userId, name }
    setAuth(newAuth)
    localStorage.setItem('auth', JSON.stringify(newAuth))
  }

  function logout() {
    setAuth({ token: null, role: null, userId: null, name: null })
    localStorage.removeItem('auth')
  }

  return (
    <AuthContext.Provider value={{ ...auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

/** Hook de acceso rápido al contexto de auth */
export function useAuth() {
  return useContext(AuthContext)
}
