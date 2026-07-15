import {
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  ArrowUp,
  BadgeCheck,
  GitFork,
  LoaderCircle,
  Menu,
  MessageSquareText,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_BASE = import.meta.env.VITE_DEMO_API_BASE_URL
  || `${window.location.protocol}//${window.location.hostname}:8788`;

interface ConversationSummary {
  conversation_id: string;
  external_user_id: string;
  title: string;
  parent_conversation_id?: string | null;
  forked_at_item?: number | null;
  last_message: string;
  item_count: number;
  created_at: string;
  updated_at: string;
  charts: string[];
}

interface ChatMessage {
  id: string;
  item_index: number;
  role: 'user' | 'assistant' | 'system';
  text: string;
  charts: string[];
  pending?: boolean;
}

interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[];
}

type SseHandler = (event: string, payload: unknown) => void;

function temporaryId() {
  return `temporary-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatRelativeDate(value: string) {
  const date = new Date(value);
  const now = new Date();
  if (Number.isNaN(date.getTime())) return '';
  if (date.toDateString() === now.toDateString()) {
    return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(date);
  }
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(date);
}

function chartLabel(tool: string) {
  const normalized = tool.toLowerCase();
  if (normalized.includes('qimen') && normalized.includes('yingqi')) return '奇门应期盘';
  if (normalized.includes('qimen')) return '奇门局';
  if (normalized.includes('horoscope')) return '星盘';
  if (normalized.includes('astrolabe') || normalized.includes('ziwei')) return '紫微命盘';
  return tool;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers || {}),
    },
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.detail || data?.error?.message || response.statusText || '请求失败');
  }
  return data as T;
}

function parseSse(buffer: string, handler: SseHandler) {
  const blocks = buffer.split(/\r?\n\r?\n/);
  const tail = blocks.pop() || '';
  for (const block of blocks) {
    let event = 'message';
    const data: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    if (data.length === 0) continue;
    const raw = data.join('\n');
    try {
      handler(event, JSON.parse(raw));
    } catch {
      handler(event, raw);
    }
  }
  return tail;
}

async function streamApi(path: string, body: unknown, handler: SseHandler) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || response.statusText || '流式请求失败');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let streamError = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer = parseSse(buffer + decoder.decode(value, { stream: true }), (event, payload) => {
      if (event === 'error') {
        streamError = String((payload as { message?: string })?.message || '请求失败');
      }
      handler(event, payload);
    });
  }
  if (streamError) throw new Error(streamError);
}

export function App() {
  const [externalUserId, setExternalUserId] = useState(
    () => window.localStorage.getItem('iztro-demo-user') || 'demo-user',
  );
  const [userDraft, setUserDraft] = useState(externalUserId);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState('');
  const [active, setActive] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState('');
  const [editing, setEditing] = useState<ChatMessage | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);

  const loadConversation = useCallback(async (conversationId: string, userId = externalUserId) => {
    const detail = await api<ConversationDetail>(
      `/api/conversations/${encodeURIComponent(conversationId)}?external_user_id=${encodeURIComponent(userId)}`,
    );
    setActiveId(conversationId);
    setActive(detail);
    setMessages(detail.messages);
    setTitleDraft(detail.title);
    setEditing(null);
  }, [externalUserId]);

  const refreshConversations = useCallback(async (
    preferredId?: string,
    userId = externalUserId,
  ) => {
    const data = await api<{ items: ConversationSummary[] }>(
      `/api/conversations?external_user_id=${encodeURIComponent(userId)}`,
    );
    setConversations(data.items);
    const target = preferredId && data.items.some((item) => item.conversation_id === preferredId)
      ? preferredId
      : data.items[0]?.conversation_id;
    if (target) {
      await loadConversation(target, userId);
    } else {
      setActiveId('');
      setActive(null);
      setMessages([]);
    }
  }, [externalUserId, loadConversation]);

  useEffect(() => {
    setLoading(true);
    setError('');
    setActiveId('');
    setActive(null);
    setMessages([]);
    refreshConversations()
      .catch((reason) => setError(reason instanceof Error ? reason.message : '加载失败'))
      .finally(() => setLoading(false));
  }, [refreshConversations]);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const createConversation = async () => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const created = await api<ConversationSummary>('/api/conversations', {
        method: 'POST',
        body: JSON.stringify({ external_user_id: externalUserId, title: '新会话' }),
      });
      await refreshConversations(created.conversation_id);
      setSidebarOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '新建会话失败');
    } finally {
      setBusy(false);
    }
  };

  const selectConversation = async (conversationId: string) => {
    if (busy || conversationId === activeId) return;
    setLoading(true);
    setError('');
    try {
      await loadConversation(conversationId);
      setSidebarOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '加载会话失败');
    } finally {
      setLoading(false);
    }
  };

  const saveTitle = async (event: FormEvent) => {
    event.preventDefault();
    if (!active || !titleDraft.trim()) return;
    setBusy(true);
    try {
      await api(`/api/conversations/${encodeURIComponent(active.conversation_id)}`, {
        method: 'PATCH',
        body: JSON.stringify({ external_user_id: externalUserId, title: titleDraft.trim() }),
      });
      setRenaming(false);
      await refreshConversations(active.conversation_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '重命名失败');
    } finally {
      setBusy(false);
    }
  };

  const forkConversation = async () => {
    if (!active || busy) return;
    setBusy(true);
    setError('');
    try {
      const forked = await api<ConversationSummary>(
        `/api/conversations/${encodeURIComponent(active.conversation_id)}/fork`,
        {
          method: 'POST',
          body: JSON.stringify({ external_user_id: externalUserId }),
        },
      );
      await refreshConversations(forked.conversation_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建分支失败');
    } finally {
      setBusy(false);
    }
  };

  const deleteConversation = async () => {
    if (!active || busy) return;
    if (!window.confirm(`删除“${active.title}”？此操作会删除服务器端会话历史。`)) return;
    setBusy(true);
    setError('');
    try {
      await api(
        `/api/conversations/${encodeURIComponent(active.conversation_id)}?external_user_id=${encodeURIComponent(externalUserId)}`,
        { method: 'DELETE' },
      );
      await refreshConversations();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '删除失败');
    } finally {
      setBusy(false);
    }
  };

  const startEditing = (item: ChatMessage) => {
    if (busy) return;
    setEditing(item);
    setMessage(item.text);
  };

  const cancelEditing = () => {
    setEditing(null);
    setMessage('');
  };

  const sendMessage = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = message.trim();
    if (!active || !text || busy) return;

    const sourceConversationId = active.conversation_id;
    const editedItem = editing;
    const userItemIndex = editedItem?.item_index ?? active.item_count;
    const assistantItemIndex = userItemIndex + 1;
    const pendingUser: ChatMessage = {
      id: temporaryId(),
      item_index: userItemIndex,
      role: 'user',
      text,
      charts: [],
      pending: true,
    };
    const pendingAssistant: ChatMessage = {
      id: temporaryId(),
      item_index: assistantItemIndex,
      role: 'assistant',
      text: '',
      charts: [],
      pending: true,
    };

    setMessages((items) => [
      ...(editedItem
        ? items.filter((item) => item.item_index < editedItem.item_index)
        : items),
      pendingUser,
      pendingAssistant,
    ]);
    setMessage('');
    setEditing(null);
    setBusy(true);
    setError('');

    let targetConversationId = sourceConversationId;
    try {
      const path = editedItem
        ? `/api/conversations/${encodeURIComponent(sourceConversationId)}/messages/${editedItem.item_index}/edit/stream`
        : `/api/conversations/${encodeURIComponent(sourceConversationId)}/messages/stream`;
      await streamApi(
        path,
        { external_user_id: externalUserId, message: text },
        (eventName, payload) => {
          const data = payload as Record<string, unknown>;
          if (eventName === 'conversation' && typeof data.conversation_id === 'string') {
            targetConversationId = data.conversation_id;
            setActiveId(targetConversationId);
            setActive((current) => ({
              ...(current || active),
              ...(data as unknown as ConversationSummary),
              messages: [],
            }));
          }
          if (eventName === 'chart' && Array.isArray(data.tools)) {
            const nextTools = data.tools.map(String);
            setMessages((items) => items.map((item) => (
              item.id === pendingAssistant.id
                ? { ...item, charts: [...new Set([...item.charts, ...nextTools])] }
                : item
            )));
          }
          if (eventName === 'delta' && typeof data.delta === 'string') {
            setMessages((items) => items.map((item) => (
              item.id === pendingAssistant.id
                ? { ...item, text: `${item.text}${data.delta}` }
                : item
            )));
          }
          if (eventName === 'done') {
            if (typeof data.conversation_id === 'string') targetConversationId = data.conversation_id;
            setMessages((items) => items.map((item) => (
              item.id === pendingAssistant.id
                ? {
                    ...item,
                    text: item.text || String(data.text || ''),
                    charts: Array.isArray(data.charts) ? data.charts.map(String) : item.charts,
                    pending: false,
                  }
                : item.id === pendingUser.id ? { ...item, pending: false } : item
            )));
          }
        },
      );
      await refreshConversations(targetConversationId);
    } catch (reason) {
      const textError = reason instanceof Error ? reason.message : '发送失败';
      setError(textError);
      setMessages((items) => items.map((item) => (
        item.id === pendingAssistant.id
          ? { ...item, role: 'system', text: textError, pending: false }
          : item
      )));
    } finally {
      setBusy(false);
    }
  };

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const switchUser = async (event: FormEvent) => {
    event.preventDefault();
    const next = userDraft.trim();
    if (!next || next === externalUserId || busy) return;
    window.localStorage.setItem('iztro-demo-user', next);
    setExternalUserId(next);
  };

  const chartNames = useMemo(
    () => [...new Set(messages.flatMap((item) => item.charts))],
    [messages],
  );

  return (
    <main className="shell">
      <button
        className="mobile-menu"
        type="button"
        aria-label="打开会话列表"
        onClick={() => setSidebarOpen(true)}
      >
        <Menu size={20} />
      </button>

      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark"><Sparkles size={19} /></div>
          <div>
            <b>Iztro Agent</b>
            <span>ChatSession demo</span>
          </div>
          <button className="sidebar-close" type="button" onClick={() => setSidebarOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <button className="new-chat" type="button" onClick={createConversation} disabled={busy}>
          <Plus size={17} />
          新建会话
        </button>

        <div className="conversation-heading">
          <span>最近会话</span>
          <span>{conversations.length}</span>
        </div>
        <nav className="conversation-list" aria-label="会话列表">
          {conversations.map((item) => (
            <button
              type="button"
              key={item.conversation_id}
              className={`conversation-card ${item.conversation_id === activeId ? 'active' : ''}`}
              onClick={() => void selectConversation(item.conversation_id)}
              disabled={busy}
            >
              <span className="conversation-card-top">
                <b>{item.title}</b>
                <time>{formatRelativeDate(item.updated_at)}</time>
              </span>
              <span className="conversation-preview">{item.last_message || '还没有消息'}</span>
              <span className="conversation-meta">
                {item.parent_conversation_id ? <span><GitFork size={12} /> 分支</span> : null}
                {item.charts.slice(0, 2).map((chart) => (
                  <span key={chart}>{chartLabel(chart)}</span>
                ))}
              </span>
            </button>
          ))}
          {!loading && conversations.length === 0 ? (
            <div className="empty-list">新建一个会话开始体验</div>
          ) : null}
        </nav>

        <form className="user-switcher" onSubmit={switchUser}>
          <label htmlFor="user-id">演示用户</label>
          <div>
            <input
              id="user-id"
              value={userDraft}
              onChange={(event) => setUserDraft(event.target.value)}
              disabled={busy}
            />
            <button type="submit" disabled={busy || !userDraft.trim()} aria-label="切换用户">
              <ArrowUp size={14} />
            </button>
          </div>
        </form>
      </aside>

      {sidebarOpen ? <button className="sidebar-backdrop" type="button" onClick={() => setSidebarOpen(false)} /> : null}

      <section className="workspace">
        <header className="chat-header">
          <div className="title-area">
            {renaming && active ? (
              <form className="rename-form" onSubmit={saveTitle}>
                <input
                  autoFocus
                  value={titleDraft}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  maxLength={80}
                />
                <button type="submit" disabled={busy}>保存</button>
                <button type="button" onClick={() => setRenaming(false)}>取消</button>
              </form>
            ) : (
              <>
                <div className="title-line">
                  <h1>{active?.title || 'ChatSession 会话工作台'}</h1>
                  {active ? (
                    <button
                      className="icon-button quiet"
                      type="button"
                      aria-label="重命名"
                      onClick={() => { setTitleDraft(active.title); setRenaming(true); }}
                      disabled={busy}
                    >
                      <Pencil size={15} />
                    </button>
                  ) : null}
                </div>
                <p>
                  {active?.parent_conversation_id
                    ? '这是一个会话分支，原会话历史仍然保留。'
                    : '历史由服务器端 ChatSession 管理，API Key 始终留在后端。'}
                </p>
              </>
            )}
          </div>
          {active ? (
            <div className="header-actions">
              <button type="button" onClick={forkConversation} disabled={busy}>
                <GitFork size={16} />
                Fork
              </button>
              <button className="danger" type="button" onClick={deleteConversation} disabled={busy}>
                <Trash2 size={16} />
                删除
              </button>
            </div>
          ) : null}
        </header>

        <div className="context-bar">
          <div className="session-state">
            <BadgeCheck size={15} />
            <span>{active ? `${active.item_count} 个历史项` : '等待新会话'}</span>
          </div>
          <div className="chart-summary">
            <span>本会话调用</span>
            {chartNames.length ? chartNames.map((chart) => (
              <span className="chart-chip" key={chart}><Sparkles size={12} />{chartLabel(chart)}</span>
            )) : <span className="muted">尚未调用命盘</span>}
          </div>
        </div>

        <section className="messages" aria-live="polite">
          {loading ? (
            <div className="center-state"><LoaderCircle className="spin" size={24} />正在加载会话</div>
          ) : !active ? (
            <div className="welcome">
              <div className="welcome-icon"><MessageSquareText size={28} /></div>
              <p className="overline">OpenAI Agents SDK × Iztro</p>
              <h2>从一个可管理的会话开始</h2>
              <p>新建会话后可以流式聊天、查看调用过的命盘、编辑历史消息并创建分支。</p>
              <button type="button" onClick={createConversation} disabled={busy}>
                <Plus size={16} />新建第一个会话
              </button>
            </div>
          ) : messages.length === 0 ? (
            <div className="welcome conversation-welcome">
              <p className="overline">新会话</p>
              <h2>今天想从哪里开始？</h2>
              <p>你可以直接输入出生年月日、时辰、性别和想了解的问题。</p>
              <div className="suggestions">
                {[
                  '我是 1995-02-23 17 时出生的女性，分析 2026 年事业趋势。',
                  '根据我的命盘，我更适合怎样的工作环境？',
                  '帮我梳理今年感情和人际关系要注意的月份。',
                ].map((suggestion) => (
                  <button key={suggestion} type="button" onClick={() => setMessage(suggestion)}>
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-stack">
              {messages.map((item) => (
                <article key={item.id} className={`message ${item.role} ${item.pending ? 'pending' : ''}`}>
                  <div className="avatar">{item.role === 'user' ? '你' : item.role === 'assistant' ? '紫' : '!'}</div>
                  <div className="message-body">
                    <div className="message-label">
                      <b>{item.role === 'user' ? '你' : item.role === 'assistant' ? 'Iztro Agent' : '系统'}</b>
                      {item.pending ? <span>生成中</span> : null}
                    </div>
                    {item.charts.length ? (
                      <div className="message-charts">
                        {item.charts.map((chart) => (
                          <span key={chart}><Sparkles size={12} />已调用 {chartLabel(chart)}</span>
                        ))}
                      </div>
                    ) : null}
                    {item.role === 'assistant' && item.text ? (
                      <div className="markdown">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            a: ({ node: _node, ...props }) => (
                              <a {...props} target="_blank" rel="noreferrer" />
                            ),
                          }}
                        >
                          {item.text}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p>{item.text || (item.pending ? <span className="typing"><i /><i /><i /></span> : '')}</p>
                    )}
                    {item.role === 'user' && !item.pending ? (
                      <button className="edit-message" type="button" onClick={() => startEditing(item)} disabled={busy}>
                        <Pencil size={13} />编辑并创建分支
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
              <div ref={messagesEnd} />
            </div>
          )}
        </section>

        <footer className="composer-wrap">
          {error ? <div className="error-banner"><span>{error}</span><button type="button" onClick={() => setError('')}><X size={14} /></button></div> : null}
          {editing ? (
            <div className="edit-banner">
              <span><GitFork size={14} />编辑第 {editing.item_index + 1} 个历史项，将保留原会话并创建分支</span>
              <button type="button" onClick={cancelEditing} disabled={busy}><X size={14} />取消</button>
            </div>
          ) : null}
          <form className="composer" onSubmit={sendMessage}>
            <textarea
              rows={1}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder={active ? '输入消息，Enter 发送，Shift + Enter 换行' : '请先新建一个会话'}
              disabled={!active || busy}
            />
            <button className="send-button" type="submit" disabled={!active || !message.trim() || busy} aria-label="发送">
              {busy ? <LoaderCircle className="spin" size={18} /> : <ArrowUp size={18} />}
            </button>
          </form>
          <p className="composer-note">Iztro Agent 可能会犯错；重要决定请结合现实信息判断。</p>
        </footer>
      </section>
    </main>
  );
}
