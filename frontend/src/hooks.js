import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

/** Load data from the API; returns {data, error, loading, reload, setData}. */
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: !!path })
  const seq = useRef(0)
  const load = useCallback(async () => {
    if (!path) return
    const id = ++seq.current
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await api(path)
      if (id === seq.current) setState({ data, error: null, loading: false })
    } catch (error) {
      if (id === seq.current) setState((s) => ({ ...s, error, loading: false }))
    }
  }, [path])
  useEffect(() => { load() }, [load, ...deps]) // eslint-disable-line react-hooks/exhaustive-deps
  const setData = (fn) => setState((s) => ({ ...s, data: typeof fn === 'function' ? fn(s.data) : fn }))
  return { ...state, reload: load, setData }
}

export function useTitle(title) {
  useEffect(() => { document.title = title ? `${title} · AgriExpert` : 'AgriExpert' }, [title])
}
