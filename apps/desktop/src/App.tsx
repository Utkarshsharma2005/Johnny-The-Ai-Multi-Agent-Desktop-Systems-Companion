/**
 * App.tsx — Root component for Johnny Desktop AI Pet.
 *
 * Architecture:
 *  - PetLayer owns the physics engine + rAF loop + drag + skill wheel.
 *  - ChatConsole is the slide-in panel (existing component, now styled by tokens).
 *  - VisionBadge shows screen intelligence cooldown near the pet.
 *  - agentState is derived from backend activity and forwarded to PetLayer
 *    so the pet's behavior reacts to what Johnny is actually doing.
 *
 * Console position: fixed right-side panel, vertically centered.
 * When opened, the pet receives a "step-away" hint via the Director.
 */

import React, { useState, useCallback, useMemo } from 'react';
import { PetLayer }       from './components/PetLayer';
import { ChatConsole }    from './components/ChatConsole';
import { PermissionModal } from './components/PermissionModal';
import { useJohnnyApi }   from './hooks/useJohnnyApi';
import type { AgentState } from './engine/Director';

export function App() {
  const [isConsoleOpen, setIsConsoleOpen] = useState(false);
  const [activeTab, setActiveTab]         = useState<string>('chat');
  const [character, setCharacter]         = useState<string>(() => localStorage.getItem('johnny_character') || 'spongebob');

  const handleSelectCharacter = useCallback((char: string) => {
    setCharacter(char);
    localStorage.setItem('johnny_character', char);
  }, []);

  const api = useJohnnyApi();

  /* ── Derive AgentState from backend activity ──────────────────── */
  const agentState: AgentState = useMemo(() => {
    if (api.isProcessing) return 'THINKING';
    if (
      api.activeTask?.status === 'EXECUTION' ||
      api.activeTask?.status === 'PLANNING'  ||
      api.activeTask?.status === 'VERIFYING'
    ) return 'WORKING';
    if (api.activeTask?.status === 'COMPLETED') return 'COMPLETED';
    if (api.activeTask?.status === 'FAILED')    return 'ERROR';
    return 'IDLE';
  }, [api.isProcessing, api.activeTask]);

  /* ── Speech bubble text ───────────────────────────────────────── */
  const speechText = useMemo(() => {
    if (api.isProcessing)                          return 'Thinking with Llama 70B…';
    if (api.activeTask?.status === 'PLANNING')     return `Planning task…`;
    if (api.activeTask?.status === 'EXECUTION')    return `Executing: ${api.activeTask.goal.slice(0, 40)}`;
    if (api.activeTask?.status === 'VERIFYING')    return 'Verifying results…';
    if (api.activeTask?.status === 'COMPLETED')    return '✅ Task complete!';
    if (api.activeTask?.status === 'FAILED')       return '❌ Something went wrong. Check the console.';
    if (api.browserStatus?.active_url)             return `Browsing: ${api.browserStatus.active_url}`;
    if (api.screenState?.mode === 'ATTENTIVE')     return 'Watching your screen…';
    return isConsoleOpen
      ? 'Console open — ask me anything!'
      : 'Click me to open the console 🐾';
  }, [api, isConsoleOpen]);

  /* ── Console open / close ─────────────────────────────────────── */
  const openConsole = useCallback((tab?: string) => {
    if (tab) setActiveTab(tab);
    setIsConsoleOpen(true);
  }, []);

  const toggleConsole = useCallback(() => {
    setIsConsoleOpen((prev) => !prev);
  }, []);

  const closeConsole = useCallback(() => {
    setIsConsoleOpen(false);
  }, []);

  /* ── Skill wheel actions ──────────────────────────────────────── */
  const handleOpenConsole  = useCallback((tab?: string) => openConsole(tab || 'chat'), [openConsole]);
  const handleOpenTasks    = useCallback(() => openConsole('tasks'),    [openConsole]);
  const handleOpenMemory   = useCallback(() => openConsole('memory'),   [openConsole]);
  const handleOpenTools    = useCallback(() => openConsole('tools'),    [openConsole]);
  const handleOpenSettings = useCallback(() => openConsole('settings'), [openConsole]);
  const handleTriggerVision = useCallback(async () => {
    await api.triggerScreenCapture(true, 'Manual vision trigger from skill wheel');
  }, [api]);

  /* ── 3-Mode Notification State ────────────────────────────────── */
  // Green:  IDLE / Ready
  // Yellow: Medium / Complex task (Planning, Execution, Verifying, Processing)
  // Red:    Hard / Frequent Browser / Critical Task / Error
  const notificationMode: 'green' | 'yellow' | 'red' = useMemo(() => {
    if (
      agentState === 'ERROR' ||
      api.activeTask?.status === 'FAILED' ||
      Boolean(api.browserStatus?.is_connected && api.browserStatus?.active_url)
    ) {
      return 'red';
    }
    if (
      api.isProcessing ||
      agentState === 'WORKING' ||
      agentState === 'THINKING' ||
      api.activeTask?.status === 'PLANNING' ||
      api.activeTask?.status === 'EXECUTION' ||
      api.activeTask?.status === 'VERIFYING'
    ) {
      return 'yellow';
    }
    return 'green';
  }, [agentState, api.isProcessing, api.activeTask, api.browserStatus]);

  return (
    <>
      {/* ── Pet Overlay (always present, physics-driven) ───────────── */}
      <PetLayer
        agentState={agentState}
        speechText={speechText}
        character={character}
        isConsoleOpen={isConsoleOpen}
        notificationMode={notificationMode}
        onToggleConsole={toggleConsole}
        onOpenConsole={handleOpenConsole}
        onTriggerVision={handleTriggerVision}
        onOpenTasks={handleOpenTasks}
        onOpenMemory={handleOpenMemory}
        onOpenTools={handleOpenTools}
        onOpenSettings={handleOpenSettings}
        onSelectCharacter={handleSelectCharacter}
        onTerminateTasks={api.terminateAllTasks}
      />

      {/* ── Console panel (slide-in from right, glass design) ──────── */}
      <div
        className={`console-panel${isConsoleOpen ? '' : ' is-hidden'}`}
        style={{
          width: 'auto',
          height: 'auto',
          maxHeight: 'none',
          background: 'transparent',
          border: 'none',
          boxShadow: 'none',
        }}
        role="complementary"
        aria-label="Johnny Console"
      >
        <ChatConsole
          messages={api.messages}
          onSendMessage={api.sendMessage}
          isProcessing={api.isProcessing}
          telemetry={api.latestTelemetry}
          screenState={api.screenState}
          fetchScreenState={api.fetchScreenState}
          setScreenMode={api.setScreenMode}
          triggerScreenCapture={api.triggerScreenCapture}
          toggleScreenPause={api.toggleScreenPause}
          requirementState={api.requirementState}
          fetchRequirementState={api.fetchRequirementState}
          compileRequirements={api.compileRequirements}
          lockRequirements={api.lockRequirements}
          resetRequirements={api.resetRequirements}
          toolsList={api.toolsList}
          fetchTools={api.fetchTools}
          executeTool={api.executeTool}
          lastToolResult={api.lastToolResult}
          verificationReport={api.verificationReport}
          runVerification={api.runVerification}
          tasksList={api.tasksList}
          activeTask={api.activeTask}
          fetchTasks={api.fetchTasks}
          createTask={api.createTask}
          executeTask={api.executeTask}
          browserStatus={api.browserStatus}
          fetchBrowserStatus={api.fetchBrowserStatus}
          navigateBrowser={api.navigateBrowser}
          executeBrowserAction={api.executeBrowserAction}
          memoryItems={api.memoryItems}
          queryMemory={api.queryMemory}
          recordMemory={api.recordMemory}
          clearMemoryTier={api.clearMemoryTier}
          onStopGenerating={api.stopGenerating}
          onClose={closeConsole}
          defaultTab={activeTab}
          character={character}
          onSelectCharacter={handleSelectCharacter}
        />
      </div>
      {/* ── Permission Modal (always-on, appears when agent needs approval) ── */}
      <PermissionModal />
    </>
  );
}

export default App;
