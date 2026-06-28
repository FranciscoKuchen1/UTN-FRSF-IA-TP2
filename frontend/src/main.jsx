import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

import { AuthProvider, useAuth } from './AuthContext.jsx'
import LoginPage   from './LoginPage.jsx'
import AdminPanel  from './AdminPanel.jsx'
import App         from './App.jsx'

/**
 * Router condicional basado en el token y el rol.
 * No usa react-router-dom — el estado en AuthContext es suficiente.
 *
 *  sin token  → LoginPage
 *  role=admin → AdminPanel
 *  role=*     → App (chat)
 */
function Root() {
  const { token, role } = useAuth()

  if (!token)              return <LoginPage />
  if (role === 'admin')    return <AdminPanel />
  return <App />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <Root />
    </AuthProvider>
  </React.StrictMode>,
)
