import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [farm, setFarm] = useState(null)
  const [options, setOptions] = useState(null)
  const [ready, setReady] = useState(false)

  const logout = useCallback(() => { setToken(null); setUser(null); setFarm(null) }, [])

  const refresh = useCallback(async () => {
    if (!getToken()) { setReady(true); return }
    try {
      const me = await api('/me')
      setUser(me.user); setFarm(me.farm)
    } catch (e) {
      if (e.status === 401) logout()
    } finally { setReady(true) }
  }, [logout])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    refresh()
    api('/meta/options').then(setOptions).catch(() => {})
  }, [refresh, logout])

  const signIn = async (path, body) => {
    const res = await api(path, { method: 'POST', body })
    setToken(res.token)
    setUser(res.user)
    const me = await api('/me')
    setFarm(me.farm)
    return me
  }

  return (
    <AuthContext.Provider value={{ user, setUser, farm, setFarm, options, ready, signIn, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
