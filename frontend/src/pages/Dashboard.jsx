import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import ChatWindow from '../components/ChatWindow';
import MemoryTabs from '../components/MemoryTabs';
import {
  getConversations,
  createConversation,
  deleteConversation,
  getMessages,
  sendMessage,
  getPersonas,
  logout,
  exportConversation,
} from '../services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState({});
  const [personas, setPersonas] = useState([]);
  const [activePersona, setActivePersona] = useState(null);
  const [sending, setSending] = useState(false);
  const [exportData, setExportData] = useState(null);
  const [showExport, setShowExport] = useState(false);
  const [memoryVersion, setMemoryVersion] = useState(0);
  const [showMobileMemory, setShowMobileMemory] = useState(false);
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);

  const loadConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      const list = Array.isArray(data) ? data : data.conversations || data.data || [];
      setConversations(list);
    } catch {
      // handled by api.js redirect
    }
  }, []);

  const loadPersonas = useCallback(async () => {
    try {
      const data = await getPersonas();
      const list = Array.isArray(data) ? data : data.personas || [];
      setPersonas(list);
      if (list.length > 0 && !activePersona) {
        setActivePersona(list[0].id);
      }
    } catch {
      // personas may not be available
    }
  }, [activePersona]);

  useEffect(() => {
    loadConversations();
    loadPersonas();
  }, [loadConversations, loadPersonas]);

  useEffect(() => {
    if (!activeId && conversations.length > 0) {
      handleSelect(conversations[0].id);
    }
  }, [activeId, conversations]);

  async function handleNewChat() {
    try {
      const data = await createConversation({ persona_id: activePersona });
      const conv = data.conversation || data;
      setConversations((prev) => [conv, ...prev]);
      setActiveId(conv.id);
      setMessages((prev) => ({ ...prev, [conv.id]: [] }));
    } catch (err) {
      alert(err.message || 'Failed to create conversation');
    }
  }

  function handleSelect(id) {
    setActiveId(id);
    setShowExport(false);
    setExportData(null);
    if (messages[id]) return;

    getMessages(id)
      .then((data) => {
        const list = Array.isArray(data) ? data : data.messages || data.data || [];
        setMessages((prev) => ({ ...prev, [id]: list }));
      })
      .catch((err) => {
        alert(err.message || 'Failed to load messages');
        setMessages((prev) => ({ ...prev, [id]: [] }));
      });
  }

  async function handleSend(text) {
    let conversationId = activeId;

    if (!conversationId) {
      try {
        const conversationData = await createConversation({ persona_id: activePersona });
        const conv = conversationData.conversation || conversationData;
        conversationId = conv.id;

        setConversations((prev) => {
          if (prev.some((item) => item.id === conv.id)) return prev;
          return [conv, ...prev];
        });
        setActiveId(conv.id);
        setMessages((prev) => ({ ...prev, [conv.id]: prev[conv.id] || [] }));
      } catch (err) {
        alert(err.message || 'Failed to create conversation');
        return;
      }
    }

    const userMsg = { role: 'user', content: text };
    setMessages((prev) => ({
      ...prev,
      [conversationId]: [...(prev[conversationId] || []), userMsg],
    }));

    setSending(true);

    try {
      const data = await sendMessage({
        conversation_id: conversationId,
        message: text,
        persona_id: activePersona,
      });

      const payload = data.data || data;

      const aiMsg = {
        role: 'assistant',
        content:
          payload.response ||
          payload.message ||
          payload.content ||
          'No response',
      };

      setMessages((prev) => ({
        ...prev,
        [conversationId]: [...(prev[conversationId] || []), aiMsg],
      }));

      setMemoryVersion((prev) => prev + 1);
    } catch (err) {
      alert(err.message || 'Failed to get response');

      const errMsg = {
        role: 'assistant',
        content: 'Failed to get response. Please try again.',
      };

      setMessages((prev) => ({
        ...prev,
        [conversationId]: [...(prev[conversationId] || []), errMsg],
      }));
    } finally {
      setSending(false);
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } finally {
      localStorage.removeItem('token');
      navigate('/login', { replace: true });
    }
  }

  async function handleExport() {
    if (!activeId) return;
    try {
      const data = await exportConversation(activeId);
      setExportData(data.data || data);
      setShowExport(true);
    } catch (err) {
      alert(err.message || 'Failed to export conversation');
    }
  }

  async function handleDeleteConversation(conversationId) {
    const confirmed = window.confirm('Delete this conversation?');
    if (!confirmed) return;

    try {
      await deleteConversation(conversationId);

      setConversations((prev) => {
        const nextList = prev.filter((c) => c.id !== conversationId);

        setMessages((prevMessages) => {
          const copy = { ...prevMessages };
          delete copy[conversationId];
          return copy;
        });

        if (activeId === conversationId) {
          const nextActive = nextList[0]?.id || null;
          setActiveId(nextActive);
          setShowExport(false);
          setExportData(null);
        }

        return nextList;
      });
    } catch (err) {
      alert(err.message || 'Failed to delete conversation');
    }
  }

  function handleOpenMemory() {
    if (window.matchMedia('(max-width: 1023px)').matches) {
      setShowMobileMemory(true);
    }
  }

  const activeMessages = activeId ? messages[activeId] || [] : [];

  return (
    <div className="h-screen max-w-full overflow-x-hidden flex bg-gray-950 text-white overflow-hidden">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNewChat}
        onDelete={handleDeleteConversation}
        onOpenMemory={handleOpenMemory}
        onExport={activeId ? handleExport : undefined}
        onLogout={handleLogout}
        mobileOpen={showMobileSidebar}
        onCloseMobile={() => setShowMobileSidebar(false)}
      />

      <div className="flex-1 flex flex-col min-w-0 max-w-full">
        <Topbar
          personas={personas}
          activePersona={activePersona}
          onPersonaChange={setActivePersona}
          onMenuToggle={() => setShowMobileSidebar(true)}
          onOpenMemory={handleOpenMemory}
          onExport={activeId ? handleExport : null}
          onLogout={handleLogout}
        />

        <div className="flex-1 flex min-h-0 max-w-full overflow-hidden">
          <div className="flex-1 min-w-0 max-w-full">
            {showExport && exportData ? (
              <ExportView data={exportData} onClose={() => setShowExport(false)} />
            ) : (
              <ChatWindow
                messages={activeMessages}
                onSend={handleSend}
                loading={sending}
              />
            )}
          </div>

          <div className="w-96 border-l border-white/5 bg-white/[0.01] hidden lg:block">
            <MemoryTabs conversationId={activeId} refreshKey={memoryVersion} />
          </div>
        </div>
      </div>

      {showMobileMemory && (
        <div className="fixed inset-0 z-50 block lg:hidden">
          <button
            aria-label="Close memory panel"
            className="absolute inset-0 bg-black/40"
            onClick={() => setShowMobileMemory(false)}
          />
          <div className="absolute bottom-0 left-0 right-0 h-[70vh] bg-gray-950 border-t border-white/10 rounded-t-2xl overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-white/5">
              <h2 className="text-sm font-medium text-gray-200">Memory</h2>
              <button
                onClick={() => setShowMobileMemory(false)}
                className="px-3 py-1.5 text-sm text-gray-300 hover:text-white bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition"
              >
                Close
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <MemoryTabs conversationId={activeId} refreshKey={memoryVersion} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ExportView({ data, onClose }) {
  const json = JSON.stringify(data, null, 2);

  return (
    <div className="flex flex-col h-full p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Export Preview</h2>
        <button
          onClick={onClose}
          className="px-3 py-1.5 text-sm text-gray-400 hover:text-white bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition"
        >
          Back to Chat
        </button>
      </div>
      <div className="flex-1 overflow-auto bg-white/[0.03] border border-white/5 rounded-xl p-4">
        <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">{json}</pre>
      </div>
      <button
        onClick={() => {
          const blob = new Blob([json], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'conversation-export.json';
          a.click();
          URL.revokeObjectURL(url);
        }}
        className="mt-4 w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl transition-all duration-200 shadow-lg shadow-emerald-600/20"
      >
        Download JSON
      </button>
    </div>
  );
}
