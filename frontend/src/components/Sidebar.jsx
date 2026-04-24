export default function Sidebar({ conversations, activeId, onSelect, onNew }) {
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
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={`w-full text-left px-4 py-3 rounded-xl text-sm transition-all duration-150 ${
              c.id === activeId
                ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/30'
                : 'text-gray-300 hover:bg-white/5 hover:text-white'
            }`}
          >
            <span className="block truncate">{c.title || `Chat ${c.id?.slice(0, 8)}`}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}
