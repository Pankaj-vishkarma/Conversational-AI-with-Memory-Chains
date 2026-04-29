import { useState } from 'react';

export default function InputBox({ onSend, disabled }) {
  const [text, setText] = useState('');

  function handleSubmit(e) {
    e.preventDefault();

    if (disabled) return;

    const trimmed = text.trim();
    if (!trimmed) return;

    onSend(trimmed);

    // clear input immediately to prevent duplicate sends
    setText('');
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-3 p-4 border-t border-white/5">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type a message..."
        disabled={disabled}
        className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 transition disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-emerald-600/20"
      >
        Send
      </button>
    </form>
  );
}
