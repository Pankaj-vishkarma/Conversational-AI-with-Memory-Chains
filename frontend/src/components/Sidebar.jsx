export default function Sidebar({ conversations, activeId, onSelect, onNew, onDelete }) {
  return (
    <aside className="w-72 h-full bg-white/[0.02] border-r border-white/5 flex flex-col">
      <div className="p-4 border-b border-white/5">
        <button
          onClick={onNew}
          className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl transition-all duration-200 shadow-lg shadow-emerald-600/20"
        >
          + New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {conversations.length === 0 && (
          <p className="text-gray-500 text-sm text-center py-8">No conversations yet</p>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`group w-full flex items-center gap-2 px-2 py-1 rounded-xl text-sm transition-all duration-150 ${
              c.id === activeId
                ? 'bg-emerald-600/20 border border-emerald-500/30'
                : 'hover:bg-white/5'
            }`}
          >
            <button
              onClick={() => onSelect(c.id)}
              className={`flex-1 min-w-0 text-left px-2 py-2 rounded-lg ${
                c.id === activeId ? 'text-emerald-300' : 'text-gray-300 group-hover:text-white'
              }`}
            >
              <span className="block truncate">{c.title || `Chat ${c.id?.slice(0, 8)}`}</span>
            </button>

            <button
              onClick={() => onDelete?.(c.id)}
              aria-label="Delete conversation"
              title="Delete conversation"
              className="shrink-0 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity duration-150 p-1"
            >
              🗑
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
