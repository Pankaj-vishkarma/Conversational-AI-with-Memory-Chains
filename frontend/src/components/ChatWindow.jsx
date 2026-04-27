import { useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import InputBox from './InputBox';
import Loader from './Loader';

export default function ChatWindow({ messages, onSend, loading }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <div className="flex flex-col h-full min-h-0 max-w-full overflow-x-hidden">
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-4 sm:px-6 py-4 pb-28 lg:pb-4 max-w-full break-words">
        {messages.length === 0 && !loading && (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-500 text-sm">Start a conversation</p>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={m.id || `${m.role}-${i}`} message={m} />
        ))}
        {loading && <Loader />}
        <div ref={bottomRef} />
      </div>
      <div className="sticky bottom-0 max-w-full bg-gray-950">
        <InputBox onSend={onSend} disabled={loading} />
      </div>
    </div>
  );
}
