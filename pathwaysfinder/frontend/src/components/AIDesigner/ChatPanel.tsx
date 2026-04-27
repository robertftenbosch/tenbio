import { useEffect, useRef, useState } from 'react'
import { streamChat } from '../../api/design'
import { ChatMessage, DesignIntent } from '../../types/design'

interface Props {
  /**
   * Optional DesignIntent the user just parsed. When set, follow-up
   * questions are streamed with the intent as system context so the
   * model stays grounded.
   */
  intent: DesignIntent | null
}

interface UIMessage extends ChatMessage {
  /** Local-only id so React keys don't collide on rapid sends. */
  id: string
}

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function ChatPanel({ intent }: Props) {
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Scroll the transcript to the bottom as new tokens arrive.
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    setError(null)
    setInput('')

    const userMsg: UIMessage = { id: newId(), role: 'user', content: text }
    const assistantMsg: UIMessage = { id: newId(), role: 'assistant', content: '' }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const history: ChatMessage[] = [
        ...messages.map((m) => ({ role: m.role, content: m.content })),
        { role: 'user', content: text },
      ]
      const stream = streamChat(
        { messages: history, intent: intent ?? null },
        controller.signal
      )
      for await (const evt of stream) {
        if ('token' in evt) {
          setMessages((prev) => {
            const next = prev.slice()
            const last = next[next.length - 1]
            if (last && last.id === assistantMsg.id) {
              next[next.length - 1] = { ...last, content: last.content + evt.token }
            }
            return next
          })
        } else if ('error' in evt) {
          setError(evt.error)
        }
        // 'done' is implicit in stream completion; nothing to do.
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        // User-initiated stop -- preserve whatever tokens already rendered.
        return
      }
      setError(e instanceof Error ? e.message : 'Streaming failed')
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const stop = () => {
    abortRef.current?.abort()
  }

  const clear = () => {
    if (streaming) abortRef.current?.abort()
    setMessages([])
    setError(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
        <div>
          <h3 className="font-semibold text-gray-900">Chat with the model</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {intent
              ? 'Follow-up questions are grounded in the parsed intent above.'
              : 'No intent parsed yet — questions are answered without design context.'}
          </p>
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={clear}
            className="text-xs text-gray-600 hover:text-gray-900 underline"
          >
            Clear
          </button>
        )}
      </div>

      <div
        ref={scrollRef}
        className="px-5 py-4 max-h-96 overflow-y-auto space-y-3 text-sm"
      >
        {messages.length === 0 && (
          <div className="text-gray-500 italic">
            {intent ? (
              <>
                Probeer iets als <em>"Waarom is anammox zo traag?"</em> of{' '}
                <em>"Welke host past beter dan E. coli en waarom?"</em>.
              </>
            ) : (
              <>
                Stel een synthetisch-biologie-vraag. Voor pathway-specifieke
                follow-ups, parse eerst een doel hierboven.
              </>
            )}
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`whitespace-pre-wrap ${
              m.role === 'user' ? 'text-gray-900' : 'text-gray-800'
            }`}
          >
            <div
              className={`text-xs uppercase tracking-wide font-medium mb-0.5 ${
                m.role === 'user' ? 'text-bio-green-700' : 'text-gray-500'
              }`}
            >
              {m.role === 'user' ? 'You' : 'Assistant'}
            </div>
            <div className="leading-relaxed">
              {m.content || (m.role === 'assistant' && streaming ? '…' : '')}
            </div>
          </div>
        ))}
        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded">
            {error}
          </div>
        )}
      </div>

      <div className="px-5 py-3 border-t border-gray-100">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          placeholder={
            intent
              ? 'Ask a follow-up about the parsed intent (Enter to send)…'
              : 'Ask anything synthetic-biology related (Enter to send)…'
          }
          disabled={streaming}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-bio-green-500 focus:border-transparent text-sm disabled:bg-gray-50"
        />
        <div className="flex items-center justify-between mt-2">
          <div className="text-xs text-gray-500">
            Press Enter to send · Shift+Enter for newline
          </div>
          <div className="flex items-center gap-2">
            {streaming && (
              <button
                type="button"
                onClick={stop}
                className="px-3 py-1.5 text-sm bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition"
              >
                Stop
              </button>
            )}
            <button
              type="button"
              onClick={send}
              disabled={streaming || input.trim().length === 0}
              className="px-4 py-1.5 bg-bio-green-700 text-white text-sm rounded font-medium hover:bg-bio-green-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
            >
              {streaming ? 'Streaming…' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
