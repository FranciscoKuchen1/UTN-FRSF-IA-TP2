import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

/**
 * Provee token, role, user_id y las acciones login/logout.
 * El token se guarda SOLO en estado React (memoria), nunca en localStorage
 * ni sessionStorage, por lo que se pierde al cerrar/recargar la pestaña.
 */
export function AuthProvider({ children }) {
  const [auth, setAuth] = useState({
    token: null,   // JWT emitido por el backend
    role: null,   // 'cliente' | 'admin'
    userId: null,   // user_id devuelto por /auth/login
    name: null,     // nombre del usuario
  })

  function login(token, role, userId, name) {
    setAuth({ token, role, userId, name })
  }

  function logout() {
    setAuth({ token: null, role: null, userId: null, name: null })
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
