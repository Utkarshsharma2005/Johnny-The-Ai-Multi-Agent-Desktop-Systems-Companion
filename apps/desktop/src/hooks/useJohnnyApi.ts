import { useState, useCallback, useRef } from 'react';

export interface TelemetryData {
  routing_ms: number;
  model_ms: number;
  tool_ms?: number;
  total_ms: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'johnny';
  text: string;
  timestamp: string;
  modelUsed?: string;
  telemetry?: TelemetryData;
  isStreaming?: boolean;
}

export interface ScreenState {
  status: 'OBSERVING' | 'PAUSED' | string;
  mode: 'AMBIENT' | 'ATTENTIVE' | 'TASK' | 'PAUSED' | string;
  last_escalation_level: number;
  last_diff_score: number;
  screen_summary: string;
  active_window: string;
  total_captures: number;
  total_escalations: number;
  mode_config?: {
    interval_seconds: number;
    diff_threshold: number;
    description: string;
  };
}

export interface RequirementQuestion {
  id: string;
  question: string;
  description: string;
  options: string[];
  default_option: string;
}

export interface RequirementState {
  status: 'UNCOMPILED' | 'QUESTIONNAIRE_READY' | 'LOCKED';
  goal: string;
  known_requirements: Record<string, any>;
  questions: RequirementQuestion[];
  locked_requirements: Record<string, any>;
}

export interface ToolMetadata {
  name: string;
  description: string;
  security_level: number;
  parameters: Record<string, any>;
}

export interface ToolExecutionResult {
  success: boolean;
  approval_required?: boolean;
  tool_name: string;
  result?: any;
  error?: string;
  security_level: number;
  latency_ms: number;
}

export interface VerificationCheckDetail {
  check_name: string;
  passed: boolean;
  output: string;
  latency_ms: number;
}

export interface VerificationReport {
  is_verified: boolean;
  confidence_score: number;
  passed_checks: string[];
  failed_checks: string[];
  check_details: Record<string, VerificationCheckDetail>;
  total_latency_ms: number;
  timestamp: number;
}

export interface TaskStepState {
  step_number: number;
  description: string;
  tool_name?: string;
  tool_args?: Record<string, any>;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  output?: any;
  latency_ms: number;
}

export interface TaskState {
  id: string;
  goal: string;
  locked_requirements: Record<string, any>;
  status: 'PLANNING' | 'EXECUTION' | 'VERIFYING' | 'RECOVERING' | 'COMPLETED' | 'FAILED';
  steps: TaskStepState[];
  verification_report?: VerificationReport | null;
  recovery_attempts: number;
  logs: string[];
  created_at: number;
  updated_at: number;
}

export interface BrowserStatusState {
  is_connected: boolean;
  active_url: string | null;
  active_title: string;
  last_action: string;
  content_length: number;
}

export interface MemoryItem {
  key: string;
  value: string;
  tier: 'short_term' | 'project' | 'long_term';
  tags: string[];
  timestamp: number;
}

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export function useJohnnyApi() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'johnny',
      text: "Woof! I'm Johnny, your desktop AI companion. How can I help you today?",
      timestamp: new Date().toLocaleTimeString()
    }
  ]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [latestTelemetry, setLatestTelemetry] = useState<TelemetryData | null>(null);
  const [screenState, setScreenState] = useState<ScreenState | null>(null);
  const [requirementState, setRequirementState] = useState<RequirementState | null>(null);
  const [toolsList, setToolsList] = useState<ToolMetadata[]>([]);
  const [lastToolResult, setLastToolResult] = useState<ToolExecutionResult | null>(null);
  const [verificationReport, setVerificationReport] = useState<VerificationReport | null>(null);
  const [tasksList, setTasksList] = useState<TaskState[]>([]);
  const [activeTask, setActiveTask] = useState<TaskState | null>(null);
  const [browserStatus, setBrowserStatus] = useState<BrowserStatusState | null>(null);
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stopGenerating = useCallback(() => {
    if (abortControllerRef.current) {
      // Abort first so running handlers can still pass ownsController() and
      // finalize the cancelled message before we clear the ref.
      abortControllerRef.current.abort();
      // Use a microtask flush so abort event handlers (which check ownsController)
      // run against the current ref before it is cleared.
      setTimeout(() => {
        abortControllerRef.current = null;
        setIsProcessing(false);
      }, 0);
    } else {
      setIsProcessing(false);
    }
  }, []);

  // --- Browser Automation APIs ---
  const fetchBrowserStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/browser/status`);
      if (res.ok) {
        const data = await res.json();
        setBrowserStatus(data);
        return data;
      }
    } catch (e) {
      // Ignore background status errors
    }
    return null;
  }, []);

  const navigateBrowser = useCallback(async (url: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/browser/navigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      await fetchBrowserStatus();
      return data;
    } catch (e: any) {
      return { success: false, error: e.message || 'Navigation failed' };
    }
  }, [fetchBrowserStatus]);

  const executeBrowserAction = useCallback(async (action: string, selector?: string, text?: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/browser/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, selector, text })
      });
      const data = await res.json();
      await fetchBrowserStatus();
      return data;
    } catch (e: any) {
      return { success: false, error: e.message || 'Browser action failed' };
    }
  }, [fetchBrowserStatus]);

  // --- Memory Subsystem APIs ---
  const queryMemory = useCallback(async (term: string = '', tier?: string) => {
    try {
      const params = new URLSearchParams();
      params.append('term', term);
      if (tier) params.append('tier', tier);
      const res = await fetch(`${API_BASE_URL}/memory/query?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setMemoryItems(data || []);
        return data;
      }
    } catch (e) {
      console.error('Failed to query memory:', e);
    }
    return [];
  }, []);

  const recordMemory = useCallback(async (tier: string, key: string, value: string, tags: string[] = []) => {
    try {
      const res = await fetch(`${API_BASE_URL}/memory/record`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier, key, value, tags })
      });
      if (res.ok) {
        await queryMemory('', tier);
        return true;
      }
    } catch (e) {
      console.error('Failed to record memory:', e);
    }
    return false;
  }, [queryMemory]);

  const clearMemoryTier = useCallback(async (tier: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/memory/clear/${tier}`, { method: 'DELETE' });
      if (res.ok) {
        await queryMemory('', tier);
        return true;
      }
    } catch (e) {
      console.error('Failed to clear memory tier:', e);
    }
    return false;
  }, [queryMemory]);

  // --- Verification APIs ---
  const runVerification = useCallback(async (checks?: string[]) => {
    try {
      const res = await fetch(`${API_BASE_URL}/verification/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ checks, target_path: '.' })
      });
      if (res.ok) {
        const data = await res.json();
        setVerificationReport(data);
        return data;
      }
    } catch (e) {
      console.error('Verification failed:', e);
    }
    return null;
  }, []);

  // --- Tasks Engine APIs ---
  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/tasks`);
      if (res.ok) {
        const data = await res.json();
        setTasksList(data.tasks || []);
      }
    } catch (e) {
      // Ignore background fetch errors
    }
  }, []);

  const createTask = useCallback(async (goal: string, lockedRequirements?: Record<string, any>) => {
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal, locked_requirements: lockedRequirements })
      });
      if (res.ok) {
        const data = await res.json();
        setActiveTask(data);
        await fetchTasks();
        return data;
      }
    } catch (e) {
      console.error('Failed to create task:', e);
    }
    return null;
  }, [fetchTasks]);

  const executeTask = useCallback(async (taskId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/${taskId}/execute`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setActiveTask(data);
        await fetchTasks();
        return data;
      }
    } catch (e) {
      console.error('Failed to execute task:', e);
    }
    return null;
  }, [fetchTasks]);

  const terminateAllTasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/terminate-all`, { method: 'POST' });
      if (res.ok) {
        await fetchTasks();
        setActiveTask(null);
        setIsProcessing(false);
        return true;
      }
    } catch (e) {
      console.error('Failed to terminate all tasks:', e);
    }
    return false;
  }, [fetchTasks]);

  // --- Requirement Compiler APIs ---
  const fetchRequirementState = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/requirements/state`);
      if (res.ok) {
        const data = await res.json();
        setRequirementState(data);
      }
    } catch (e) {
      // Ignore background errors
    }
  }, []);

  const compileRequirements = useCallback(async (goal: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/requirements/compile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal, workspace_path: '.' })
      });
      if (res.ok) {
        const data = await res.json();
        setRequirementState(data);
      }
    } catch (e) {
      console.error('Failed to compile requirements:', e);
    }
  }, []);

  const lockRequirements = useCallback(async (answers: Record<string, string>) => {
    try {
      const res = await fetch(`${API_BASE_URL}/requirements/lock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers })
      });
      if (res.ok) {
        const data = await res.json();
        setRequirementState(data);
      }
    } catch (e) {
      console.error('Failed to lock requirements:', e);
    }
  }, []);

  const resetRequirements = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/requirements/reset`, { method: 'POST' });
      if (res.ok) {
        await fetchRequirementState();
      }
    } catch (e) {
      console.error('Failed to reset requirements:', e);
    }
  }, [fetchRequirementState]);

  // --- Controlled Tools APIs ---
  const fetchTools = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/tools`);
      if (res.ok) {
        const data = await res.json();
        setToolsList(data.tools || []);
      }
    } catch (e) {
      // Ignore errors
    }
  }, []);

  const executeTool = useCallback(async (toolName: string, args: Record<string, any>) => {
    try {
      const res = await fetch(`${API_BASE_URL}/tools/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: toolName, arguments: args })
      });
      const data = await res.json();
      setLastToolResult(data);
      return data;
    } catch (e: any) {
      const errorResult: ToolExecutionResult = {
        success: false,
        tool_name: toolName,
        error: e.message || 'Execution failed',
        security_level: 0,
        latency_ms: 0
      };
      setLastToolResult(errorResult);
      return errorResult;
    }
  }, []);

  // --- Screen Intelligence APIs ---
  const fetchScreenState = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/screen/state`);
      if (res.ok) {
        const data = await res.json();
        setScreenState(data);
      }
    } catch (e) {
      // Ignore background state fetch errors when server is offline
    }
  }, []);

  const setScreenMode = useCallback(async (mode: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/screen/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setScreenState(data.state);
      }
    } catch (e) {
      console.error('Failed to set screen mode:', e);
    }
  }, []);

  const triggerScreenCapture = useCallback(async (forceEscalate: boolean = false, promptContext: string = '') => {
    try {
      const res = await fetch(`${API_BASE_URL}/screen/capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force_escalate: forceEscalate, prompt_context: promptContext })
      });
      if (res.ok) {
        await fetchScreenState();
      }
    } catch (e) {
      console.error('Failed to trigger screen capture:', e);
    }
  }, [fetchScreenState]);

  const toggleScreenPause = useCallback(async () => {
    try {
      const isPaused = screenState?.status === 'PAUSED';
      const endpoint = isPaused ? '/screen/resume' : '/screen/pause';
      const res = await fetch(`${API_BASE_URL}${endpoint}`, { method: 'POST' });
      if (res.ok) {
        await fetchScreenState();
      }
    } catch (e) {
      console.error('Failed to toggle screen pause:', e);
    }
  }, [screenState, fetchScreenState]);

  // --- Chat Stream & Vision APIs ---
  const sendMessage = useCallback(async (prompt: string, imagePath?: string) => {
    if (!prompt.trim() && !imagePath) return;

    const userMessageId = `user-${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMessageId,
      sender: 'user',
      text: prompt + (imagePath ? `\n🖼️ Path: ${imagePath}` : ''),
      timestamp: new Date().toLocaleTimeString()
    };

    const johnnyMessageId = `johnny-${Date.now()}`;
    const initialJohnnyMsg: ChatMessage = {
      id: johnnyMessageId,
      sender: 'johnny',
      text: '',
      timestamp: new Date().toLocaleTimeString(),
      isStreaming: true
    };

    setMessages((prev) => [...prev, userMsg, initialJohnnyMsg]);
    setIsProcessing(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const ownsController = () => abortControllerRef.current === controller;

    try {
      if (imagePath) {
        // ── Vision path ──────────────────────────────────────────────────────
        const response = await fetch(`${API_BASE_URL}/image/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image_path: imagePath, prompt }),
          signal: controller.signal
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Image analysis failed');

        if (!ownsController()) return;

        const analysisText = typeof data.vision_result?.analysis_raw === 'string'
          ? data.vision_result.analysis_raw
          : JSON.stringify(data.vision_result?.analysis || data.vision_result, null, 2);

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === johnnyMessageId
              ? {
                  ...msg,
                  text: `📊 **Image Analysis**\nDimensions: ${data.image_metadata?.width}×${data.image_metadata?.height} | Format: ${data.image_metadata?.format}\n\n${analysisText}`,
                  modelUsed: data.vision_result?.model_used || 'minimax/minimax-m3',
                  telemetry: data.telemetry,
                  isStreaming: false
                }
              : msg
          )
        );
        if (data.telemetry) setLatestTelemetry(data.telemetry);

      } else {
        // ── Text chat path ───────────────────────────────────────────────────
        // Build conversation history from all settled (non-streaming) messages,
        // skipping the welcome message and the current empty streaming placeholder.
        // Sliding window of the last 6 messages (3 full turns) to minimize token burn and latency.
        // Long-term facts and project context are already injected via Semantic Memory.
        const historyPayload = messages
          .filter((m) => m.id !== 'welcome' && !m.isStreaming && m.text.trim())
          .slice(-6)
          .map((m) => ({
            role: m.sender === 'user' ? 'user' : 'assistant',
            content: m.text
          }));

        try {
          // Primary: SSE streaming endpoint with interrupt signal support
          const response = await fetch(`${API_BASE_URL}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, stream: true, history: historyPayload }),
            signal: controller.signal
          });

          if (!response.ok || !response.body) {
            if (controller.signal.aborted) {
              const abortErr = new Error('Generation paused');
              abortErr.name = 'AbortError';
              throw abortErr;
            }
            const errBody = await response.text().catch(() => '');
            if (controller.signal.aborted) {
              const abortErr = new Error('Generation paused');
              abortErr.name = 'AbortError';
              throw abortErr;
            }
            throw new Error(`Stream endpoint returned ${response.status}: ${errBody}`);
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let accumulatedText = '';
          let modelUsed = 'meta/llama-3.3-70b-instruct';
          let telemetryResult: TelemetryData | undefined;
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed.startsWith('data: ')) continue;
              const dataContent = trimmed.slice(6).trim();
              if (dataContent === '[DONE]') continue;
              try {
                const parsed = JSON.parse(dataContent);
                if (parsed.type === 'token') {
                  accumulatedText += parsed.token;
                  if (ownsController()) {
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === johnnyMessageId ? { ...msg, text: accumulatedText } : msg
                      )
                    );
                  }
                } else if (parsed.type === 'thought') {
                  if (!accumulatedText && ownsController()) {
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === johnnyMessageId ? { ...msg, text: 'Thinking...' } : msg
                      )
                    );
                  }
                } else if (parsed.type === 'telemetry') {
                  modelUsed = parsed.model_used || modelUsed;
                  telemetryResult = parsed.telemetry;
                  if (telemetryResult && ownsController()) setLatestTelemetry(telemetryResult);
                } else if (parsed.type === 'error') {
                  accumulatedText += parsed.token || '';
                }
              } catch (_) { /* ignore malformed SSE frames */ }
            }
          }

          if (!accumulatedText.trim() && !controller.signal.aborted) {
            throw new Error('Streaming produced no output — falling back to /generate');
          }

          if (ownsController()) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === johnnyMessageId
                  ? { ...msg, text: accumulatedText, modelUsed, telemetry: telemetryResult, isStreaming: false }
                  : msg
              )
            );
          }

        } catch (streamErr: any) {
          if (streamErr?.name === 'AbortError' || controller.signal.aborted) {
            if (ownsController()) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === johnnyMessageId
                    ? { ...msg, text: msg.text ? `${msg.text} ⏸️ (Paused)` : '⏸️ Generation paused.', isStreaming: false }
                    : msg
                )
              );
            }
            return;
          }
          // Fallback: non-streaming /generate endpoint (same history, same routing)
          console.warn('Streaming failed, falling back to /generate:', streamErr);
          const fallbackRes = await fetch(`${API_BASE_URL}/chat/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, stream: false, history: historyPayload }),
            signal: controller.signal
          });
          const fallbackData = await fallbackRes.json();
          if (!fallbackRes.ok) {
            throw new Error(fallbackData.detail || `Backend error ${fallbackRes.status}`);
          }
          if (ownsController()) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === johnnyMessageId
                  ? {
                      ...msg,
                      text: fallbackData.response || fallbackData.reply || '(empty response)',
                      modelUsed: fallbackData.model_used || 'unknown',
                      telemetry: fallbackData.telemetry,
                      isStreaming: false
                    }
                  : msg
              )
            );
            if (fallbackData.telemetry) setLatestTelemetry(fallbackData.telemetry);
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError' || controller.signal.aborted) {
        if (ownsController()) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === johnnyMessageId
                ? { ...msg, text: msg.text ? `${msg.text} ⏸️ (Paused)` : '⏸️ Generation paused.', isStreaming: false }
                : msg
            )
          );
        }
        return;
      }
      if (ownsController()) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === johnnyMessageId
              ? {
                  ...msg,
                  text: `❌ ${err.message || 'Failed to reach backend. Is python backend running on http://127.0.0.1:8000?'}`,
                  isStreaming: false
                }
              : msg
          )
        );
      }
    } finally {
      if (ownsController()) {
        abortControllerRef.current = null;
        setIsProcessing(false);
      }
    }
  }, [messages]);

  return {
    messages,
    sendMessage,
    isProcessing,
    latestTelemetry,
    screenState,
    fetchScreenState,
    setScreenMode,
    triggerScreenCapture,
    toggleScreenPause,
    requirementState,
    fetchRequirementState,
    compileRequirements,
    lockRequirements,
    resetRequirements,
    toolsList,
    fetchTools,
    lastToolResult,
    executeTool,
    verificationReport,
    runVerification,
    tasksList,
    activeTask,
    fetchTasks,
    createTask,
    executeTask,
    terminateAllTasks,
    browserStatus,
    fetchBrowserStatus,
    navigateBrowser,
    executeBrowserAction,
    memoryItems,
    queryMemory,
    recordMemory,
    clearMemoryTier,
    stopGenerating
  };
}
