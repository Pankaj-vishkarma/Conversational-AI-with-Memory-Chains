import ReactMarkdown from 'react-markdown';

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-emerald-600 text-white rounded-br-md'
            : 'bg-white/5 border border-white/10 text-gray-200 rounded-bl-md'
        }`}
      >
        <ReactMarkdown
          components={{
            h1: ({ children }) => (
              <h1 className="mb-3 text-xl font-semibold leading-snug text-white">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="mb-2 mt-3 text-lg font-semibold leading-snug text-white">{children}</h2>
            ),
            h3: ({ children }) => (
              <h3 className="mb-2 mt-3 text-base font-semibold leading-snug text-white">{children}</h3>
            ),
            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
            ul: ({ children }) => (
              <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
            ),
            ol: ({ children }) => (
              <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
            ),
            li: ({ children }) => <li className="pl-1">{children}</li>,
            strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
            code: ({ children }) => (
              <code className="rounded bg-black/30 px-1 py-0.5 text-[0.85em] text-emerald-200">
                {children}
              </code>
            ),
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
