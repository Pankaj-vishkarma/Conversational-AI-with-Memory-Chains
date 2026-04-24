import { useState, useRef, useEffect } from 'react';

export default function Topbar({
  personas,
  activePersona,
  onPersonaChange,
  onMenuToggle,
  onExport,
  onLogout,
  onOpenMemory,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const activeName = personas.find((p) => p.id === activePersona)?.name || 'Select persona';

  return (
    <header className="h-14 bg-white/[0.02] border-b border-white/5 flex items-center justify-between px-5">
      <button
        onClick={onMenuToggle}
        className="lg:hidden px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-gray-200 hover:bg-white/10 transition"
        aria-label="Open sidebar"
      >
        ☰
      </button>

      <div className="relative lg:ml-0 ml-auto" ref={ref}>
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-gray-200 hover:bg-white/10 transition"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          {activeName}
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-2 w-56 bg-gray-900 border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
            {personas.length === 0 && (
              <p className="px-4 py-3 text-gray-500 text-sm">No personas available</p>
            )}
            {personas.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  onPersonaChange(p.id);
                  setOpen(false);
                }}
                className={`w-full text-left px-4 py-2.5 text-sm transition hover:bg-white/5 ${p.id === activePersona ? 'text-emerald-400 bg-emerald-500/10' : 'text-gray-300'
                  }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="hidden lg:flex items-center gap-3">
        {/* <button
          onClick={onOpenMemory}
          className="px-4 py-2 text-sm text-gray-300 hover:text-white bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition"
        >
          Memory
        </button> */}
        {onExport && (
          <button
            onClick={onExport}
            className="px-4 py-2 text-sm text-gray-300 hover:text-white bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition"
          >
            Export
          </button>
        )}
        <button
          onClick={onLogout}
          className="px-4 py-2 text-sm text-gray-300 hover:text-red-400 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
