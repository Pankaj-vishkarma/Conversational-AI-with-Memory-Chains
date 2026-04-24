import { useState, useEffect } from 'react';
import { getEntities, getGraph, getSummary, getTokens, getMemoryCompare } from '../services/api';
import Loader from './Loader';
import ReactMarkdown from "react-markdown"; // ADD THIS

const TABS = [
  { key: 'summary', label: 'Summary' },
  { key: 'entities', label: 'Entities' },
  { key: 'graph', label: 'Knowledge Graph' },
  { key: 'tokens', label: 'Token Usage' },
  { key: 'compare', label: 'Comparison' },
];

export default function MemoryTabs({ conversationId, refreshKey = 0 }) {
  const [active, setActive] = useState('summary');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;

    async function fetchTab() {
      setLoading(true);
      setError('');
      setData(null);
      try {
        let result;
        switch (active) {
          case 'summary':
            result = await getSummary(conversationId);
            break;
          case 'entities':
            result = await getEntities(conversationId);
            break;
          case 'graph':
            result = await getGraph(conversationId);
            break;
          case 'tokens':
            result = await getTokens(conversationId);
            break;
          case 'compare':
            result = await getMemoryCompare(conversationId);
            break;
          default:
            result = null;
        }
        if (!cancelled) setData(result?.data ?? result);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchTab();
    return () => { cancelled = true; };
  }, [active, conversationId, refreshKey]);

  if (!conversationId) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        Select a conversation to view memory
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-white/5 px-1 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`px-4 py-3 text-sm font-medium whitespace-nowrap transition-all duration-150 border-b-2 ${active === t.key
              ? 'text-emerald-400 border-emerald-400'
              : 'text-gray-400 border-transparent hover:text-gray-200'
              }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loading && <Loader />}
        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}
        {!loading && !error && data !== null && (
          <TabContent tab={active} data={data} />
        )}
      </div>
    </div>
  );
}





function TabContent({ tab, data }) {
  switch (tab) {
    case 'summary': {
      const summaryText =
        typeof data === 'string'
          ? data
          : data.summary || data.content || JSON.stringify(data, null, 2);

      return (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-200">
            Conversation Summary
          </h3>

          {/* SAME container, only rendering changed */}
          <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
            <ReactMarkdown>
              {summaryText}
            </ReactMarkdown>
          </div>
        </div>
      );
    }

    case 'entities':
      return <EntitiesView data={data} />;

    case 'graph':
      return <GraphView data={data} />;

    case 'tokens':
      return <TokensView data={data} />;

    case 'compare':
      return <CompareView data={data} />;

    default:
      return (
        <pre className="text-gray-300 text-xs">
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
}

function EntitiesView({ data }) {
  const entities = Array.isArray(data) ? data : data.entities || data.data || [];

  if (entities.length === 0) {
    return <p className="text-gray-500 text-sm">No entities found</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10">
            <th className="text-left py-2 px-3 text-gray-400 font-medium">Name</th>
            <th className="text-left py-2 px-3 text-gray-400 font-medium">Type</th>
            <th className="text-left py-2 px-3 text-gray-400 font-medium">Details</th>
          </tr>
        </thead>
        <tbody>
          {entities.map((e, i) => (
            <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02] transition">
              <td className="py-2 px-3 text-emerald-300 font-medium">{e.name || e.entity || '-'}</td>
              <td className="py-2 px-3 text-gray-300">{e.type || e.entity_type || '-'}</td>
              <td className="py-2 px-3 text-gray-400 max-w-xs truncate">{e.description || e.details || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GraphView({ data }) {
  const triples = Array.isArray(data) ? data : [];
  const nodes = data.nodes || data.vertices || [];
  const edges = triples.length > 0 ? triples : data.edges || data.relationships || [];

  return (
    <div className="space-y-6">
      {nodes.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-200 mb-3">Nodes</h3>
          <div className="space-y-2">
            {nodes.map((n, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-2 bg-white/5 rounded-lg border border-white/5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                <span className="text-sm text-gray-200">{n.name || n.label || n.id || `Node ${i}`}</span>
                {n.type && <span className="text-xs text-gray-500 ml-auto">{n.type}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {edges.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-200 mb-3">Relationships</h3>
          <div className="space-y-2">
            {edges.map((e, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg border border-white/5 text-sm">
                <span className="text-emerald-300">{e.source || e.from || e.subject || '?'}</span>
                <span className="text-gray-500">--{e.label || e.type || e.predicate || '?'}--&gt;</span>
                <span className="text-blue-300">{e.target || e.to || e.object || '?'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {nodes.length === 0 && edges.length === 0 && (
        <p className="text-gray-500 text-sm">No graph data available</p>
      )}
    </div>
  );
}

function TokensView({ data }) {
  const tokens = typeof data === 'object' ? data : { tokens: data };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-200">Token Usage</h3>
      <div className="grid grid-cols-2 gap-3">
        {Object.entries(tokens).map(([key, val]) => (
          <div key={key} className="bg-white/5 border border-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-400 mb-1 capitalize">{key.replace(/_/g, ' ')}</p>
            <p className="text-2xl font-bold text-white">{typeof val === 'number' ? val.toLocaleString() : String(val)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CompareView({ data }) {
  const items = Array.isArray(data) ? data : data.comparisons || data.results || [];

  if (items.length === 0 && data && typeof data === 'object') {
    return (
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-200">Memory Comparison</h3>
        <div className="space-y-3">
          {Object.entries(data)
            .filter(([key]) => key !== 'input')
            .map(([key, value]) => (
              <div key={key} className="bg-white/5 border border-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-400 mb-2 capitalize">{key.replace(/_/g, ' ')}</p>
                <p className="text-sm text-gray-200 whitespace-pre-wrap">{String(value || '-')}</p>
              </div>
            ))}
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return <p className="text-gray-500 text-sm">No comparison data available</p>;
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-200">Memory Comparison</h3>
      <div className="space-y-3">
        {items.map((item, i) => (
          <div key={i} className="grid grid-cols-2 gap-3">
            <div className="bg-white/5 border border-white/5 rounded-xl p-4">
              <p className="text-xs text-gray-400 mb-2">With Memory</p>
              <p className="text-sm text-gray-200 whitespace-pre-wrap">
                {item.with_memory || item.with || item.response_with || '-'}
              </p>
            </div>
            <div className="bg-white/5 border border-white/5 rounded-xl p-4">
              <p className="text-xs text-gray-400 mb-2">Without Memory</p>
              <p className="text-sm text-gray-200 whitespace-pre-wrap">
                {item.without_memory || item.without || item.response_without || '-'}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
