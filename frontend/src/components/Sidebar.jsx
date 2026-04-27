export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onOpenMemory,
  onExport,
  onLogout,
  mobileOpen,
  onCloseMobile,
}) {
  const actionButtons = (
    <div className="p-3 border-t border-white/5 space-y-2">
      <button
        onClick={onOpenMemory}
        className="w-full px-4 py-2 text-sm text-gray-300 hover:text-white bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition text-left"
      >
        Memory
      </button>
      <button
        onClick={onExport}
        disabled={!onExport}
        className={`w-full px-4 py-2 text-sm border rounded-xl transition text-left ${onExport
            ? 'text-gray-300 hover:text-white bg-white/5 border-white/10 hover:bg-white/10'
            : 'text-gray-500 bg-white/5 border-white/5 cursor-not-allowed'
          }`}
      >
        Export
      </button>
      <button
        onClick={onLogout}
        className="w-full px-4 py-2 text-sm text-gray-300 hover:text-red-400 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition text-left"
      >
        Logout
      </button>
    </div>
  );

  const conversationList = (
    <div className="flex-1 overflow-y-auto p-2 space-y-1">
      {conversations.length === 0 && (
        <p className="text-gray-500 text-sm text-center py-8">No conversations yet</p>
      )}
      {conversations.map((c) => (
        <div
          key={c.id}
          className={`group w-full flex items-center gap-2 px-2 py-1 rounded-xl text-sm transition-all duration-150 ${c.id === activeId ? 'bg-emerald-600/20 border border-emerald-500/30' : 'hover:bg-white/5'
            }`}
        >
          <button
            onClick={() => onSelect(c.id)}
            className={`flex-1 min-w-0 text-left px-2 py-2 rounded-lg ${c.id === activeId ? 'text-emerald-300' : 'text-gray-300 group-hover:text-white'
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
  );

  return (
    <>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close sidebar"
            className="absolute inset-0 bg-black/40"
            onClick={onCloseMobile}
          />
          <aside className="absolute left-0 top-0 w-72 h-full bg-gray-950 border-r border-white/10 overflow-hidden flex flex-col justify-between">
            <div className="min-h-0 flex flex-col">
              <div className="p-4 border-b border-white/5">
                <button
                  onClick={onNew}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl transition-all duration-200 shadow-lg shadow-emerald-600/20"
                >
                  + New Chat
                </button>
              </div>
              {conversationList}
            </div>
            {actionButtons}
          </aside>
        </div>
      )}

      <aside className="hidden lg:flex w-72 h-full bg-white/[0.02] border-r border-white/5 flex-col">
        <div className="p-4 border-b border-white/5">
          <button
            onClick={onNew}
            className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl transition-all duration-200 shadow-lg shadow-emerald-600/20"
          >
            + New Chat
          </button>
        </div>
        {conversationList}
      </aside>
    </>
  );
}
