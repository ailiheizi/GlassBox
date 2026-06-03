import { useEffect, useRef, useCallback } from 'react'

interface UseSSEOptions {
  onMessage: (data: unknown) => void
  onError?: (error: Event) => void
  onOpen?: () => void
}

export function useSSE(url: string | null, options: UseSSEOptions) {
  const eventSourceRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    if (!url) return

    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      options.onOpen?.()
    }

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        options.onMessage(data)
      } catch {
        options.onMessage(event.data)
      }
    }

    eventSource.onerror = (error) => {
      options.onError?.(error)
    }

    return () => {
      eventSource.close()
    }
  }, [url, options])

  useEffect(() => {
    const cleanup = connect()
    return () => {
      cleanup?.()
      eventSourceRef.current?.close()
    }
  }, [connect])

  const close = useCallback(() => {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
  }, [])

  return { close }
}

// 轮询Hook
export function usePolling(
  callback: () => Promise<void>,
  interval: number,
  enabled = true
) {
  useEffect(() => {
    if (!enabled) return

    callback()
    const id = setInterval(callback, interval)

    return () => clearInterval(id)
  }, [callback, interval, enabled])
}
