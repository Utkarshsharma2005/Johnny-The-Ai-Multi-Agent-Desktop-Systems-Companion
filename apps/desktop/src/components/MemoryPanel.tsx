import React, { useState, useEffect } from 'react';
import { Database, Search, Plus, Trash2, Tag, Layers, RefreshCw } from 'lucide-react';
import { MemoryItem } from '../hooks/useJohnnyApi';

interface MemoryPanelProps {
  memoryItems: MemoryItem[];
  queryMemory: (term?: string, tier?: string) => Promise<any>;
  recordMemory: (tier: string, key: string, value: string, tags?: string[]) => Promise<boolean>;
  clearMemoryTier: (tier: string) => Promise<boolean>;
}

export const MemoryPanel: React.FC<MemoryPanelProps> = ({
  memoryItems,
  queryMemory,
  recordMemory,
  clearMemoryTier
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTier, setSelectedTier] = useState<string>('all');
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [newTags, setNewTags] = useState('');
  const [newTier, setNewTier] = useState<string>('project');
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    queryMemory(searchTerm, selectedTier === 'all' ? undefined : selectedTier);
  }, [searchTerm, selectedTier, queryMemory]);

  const handleRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim()) return;
    const tagArray = newTags.split(',').map((t) => t.trim()).filter(Boolean);
    const success = await recordMemory(newTier, newKey, newValue, tagArray);
    if (success) {
      setNewKey('');
      setNewValue('');
      setNewTags('');
      setShowAddForm(false);
    }
  };

  const handleClearTier = async (tier: string) => {
    if (confirm(`Are you sure you want to clear memory tier '${tier}'?`)) {
      await clearMemoryTier(tier);
    }
  };

  return (
    <div className="flex flex-col gap-4 text-slate-200 text-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-purple-400" />
          <h3 className="font-semibold text-slate-100">Memory Subsystem (V0.8)</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddForm((prev) => !prev)}
            className="flex items-center gap-1 rounded bg-purple-600/20 px-2 py-1 text-xs text-purple-300 border border-purple-500/30 hover:bg-purple-600/30 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Record Memory
          </button>
          <button
            onClick={() => queryMemory(searchTerm, selectedTier === 'all' ? undefined : selectedTier)}
            className="rounded p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200"
            title="Refresh Memory"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Record New Memory Form Drawer */}
      {showAddForm && (
        <form onSubmit={handleRecord} className="flex flex-col gap-2 rounded-lg bg-slate-900 border border-purple-500/40 p-3">
          <span className="text-xs font-semibold text-purple-300">Add Memory Entry</span>
          <div className="grid grid-cols-3 gap-2">
            <select
              value={newTier}
              onChange={(e) => setNewTier(e.target.value)}
              className="rounded bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-200"
            >
              <option value="short_term">Short-Term</option>
              <option value="project">Project Memory</option>
              <option value="long_term">Long-Term Preferences</option>
            </select>
            <input
              type="text"
              placeholder="Key identifier..."
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className="rounded bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-200 placeholder-slate-500"
            />
            <input
              type="text"
              placeholder="Tags (comma separated)..."
              value={newTags}
              onChange={(e) => setNewTags(e.target.value)}
              className="rounded bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-200 placeholder-slate-500"
            />
          </div>
          <textarea
            placeholder="Memory content or value..."
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            rows={2}
            className="rounded bg-slate-950 border border-slate-700 p-2 text-xs text-slate-200 placeholder-slate-500"
          />
          <button
            type="submit"
            className="self-end rounded bg-purple-600 px-3 py-1 text-xs font-medium text-white hover:bg-purple-500"
          >
            Save to Memory
          </button>
        </form>
      )}

      {/* Search & Tier Filter Bar */}
      <div className="flex flex-col gap-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search memory entries..."
            className="w-full rounded-md bg-slate-900 border border-slate-800 pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500"
          />
        </div>

        <div className="flex items-center gap-1.5 text-xs">
          <Layers className="h-3.5 w-3.5 text-slate-400 mr-1" />
          {['all', 'short_term', 'project', 'long_term'].map((tier) => (
            <button
              key={tier}
              onClick={() => setSelectedTier(tier)}
              className={`rounded px-2.5 py-1 capitalize transition-colors ${
                selectedTier === tier
                  ? 'bg-purple-600 text-white font-medium'
                  : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              {tier.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Memory Items List */}
      <div className="flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
        {memoryItems.length === 0 ? (
          <div className="rounded-lg bg-slate-900/40 border border-slate-800 p-4 text-center text-xs text-slate-500">
            No memory entries found. Record or query memory.
          </div>
        ) : (
          memoryItems.map((item, idx) => (
            <div
              key={idx}
              className="flex flex-col gap-1 rounded-lg bg-slate-900/60 border border-slate-800 p-2.5 hover:border-purple-500/30 transition-colors"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-purple-300 truncate">{item.key}</span>
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase text-slate-400">
                  {item.tier}
                </span>
              </div>
              <div className="text-xs text-slate-300 whitespace-pre-wrap font-mono bg-slate-950/60 rounded p-1.5 border border-slate-900">
                {item.value}
              </div>
              {item.tags && item.tags.length > 0 && (
                <div className="flex items-center gap-1 pt-1">
                  <Tag className="h-3 w-3 text-slate-500" />
                  {item.tags.map((t, i) => (
                    <span key={i} className="rounded bg-purple-500/10 px-1 py-0.2 text-[10px] text-purple-400">
                      #{t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Clear Tier Action */}
      {selectedTier !== 'all' && (
        <button
          onClick={() => handleClearTier(selectedTier)}
          className="self-start flex items-center gap-1 text-xs text-rose-400 hover:text-rose-300 pt-1"
        >
          <Trash2 className="h-3.5 w-3.5" /> Clear '{selectedTier.replace('_', ' ')}' Memory Tier
        </button>
      )}
    </div>
  );
};
