import { useState, useEffect } from 'react';
import { useToast } from './hooks/useToast';
import { useAPIKey } from './hooks/useAPIKey';
import { useChat } from './hooks/useChat';
import { useProjectConfig } from './hooks/useProjectConfig';
import { BRDPProvider, useBRDPContext } from './context/BRDPContext';
import Sidebar from './components/Sidebar';
import ToastContainer from './components/ToastContainer';
import BRDPPage from './pages/BRDPPage';
import SettingsPage from './pages/SettingsPage';
import HomePage from './pages/HomePage';
import DataPage from './pages/DataPage';
import ChatPanel from './components/ChatPanel';
import GenerateModal from './components/GenerateModal';
import BREXdocModal from './components/BREXdocModal/BREXdocModal';
import AIExtractModal from './components/AIExtractModal/AIExtractModal';
import './index.css';
import './App.css';

// Access BRDPContext inside AppContent
function useSelectedBRDP() {
  const { selectedBRDPs } = useBRDPContext();
  return selectedBRDPs.length > 0 ? selectedBRDPs[0] : null;
}

/**
 * Main App component
 * Manages page routing between BRDP and Settings pages
 * @returns {JSX.Element} Application layout with header, sidebar, and main content
 */
function AppContent() {
  const [currentPage, setCurrentPage] = useState('home');
  const [chatOpen, setChatOpen] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showBREXdocModal, setShowBREXdocModal] = useState(false);
  const [showAIExtractModal, setShowAIExtractModal] = useState(false);
  const [chatPanelWidth, setChatPanelWidth] = useState(() => {
    const saved = localStorage.getItem('chatPanelWidth');
    return saved ? parseInt(saved) : 340;
  });
  const { brdps, setBrdps, selectedBRDPs, setSelectedBRDPs } = useBRDPContext();
  const { toasts, showToast } = useToast();
  const { apiKey, modelName, provider, customEndpoint, isConfigured } = useAPIKey();
  const { projectConfig } = useProjectConfig();

  const { messages, sendUserMessage, clearHistory, stopStreaming, isLoading, error } = useChat({
    apiKey,
    modelName,
    provider,
    customEndpoint,
    selectedBRDPs,
  });

  // Save chat panel width to localStorage
  useEffect(() => {
    localStorage.setItem('chatPanelWidth', chatPanelWidth.toString());
  }, [chatPanelWidth]);

  /**
   * Handle opening generate modal
   */
  const openGenerateModal = () => {
    setShowGenerateModal(true);
  };

  const openAIExtractModal = () => {
    setShowAIExtractModal(true);
  };

  const handleImportBRDPs = (newBrdps, mergeMode) => {
    if (mergeMode === 'replace') {
      setBrdps(newBrdps);
    } else {
      setBrdps([...brdps, ...newBrdps]);
    }
  };

  /**
   * Handle opening chat from header
   */
  const handleHeaderChatClick = () => {
    if (currentPage === 'brdp') {
      setChatOpen(!chatOpen);
    }
  };

  const handleCloseChat = () => {
    setChatOpen(false);
  };

  const handleNavigateSettings = () => {
    handleCloseChat();
  };

  return (
    <div className="appContainer">
      <div className="workspaceRow">
        <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
        <main className="mainContent">
          {currentPage === 'home' && <HomePage onNavigate={setCurrentPage} />}
          {currentPage === 'brdp' && (
            <BRDPPage
              showToast={showToast}
              onNavigate={setCurrentPage}
              onChatClick={handleHeaderChatClick}
              chatOpen={chatOpen}
              onOpenGenerateModal={openGenerateModal}
              onOpenBREXdocModal={() => setShowBREXdocModal(true)}
              onOpenAIExtractModal={openAIExtractModal}
            />
          )}
          {currentPage === 'data' && <DataPage showToast={showToast} />}
          {currentPage === 'settings' && <SettingsPage showToast={showToast} />}
        </main>
        {currentPage === 'brdp' && chatOpen && (
          <ChatPanel
            messages={messages}
            onSendMessage={sendUserMessage}
            onClearHistory={clearHistory}
            onStopStreaming={stopStreaming}
            isLoading={isLoading}
            error={error}
            isConfigured={isConfigured}
            onNavigateSettings={handleNavigateSettings}
            onClose={handleCloseChat}
            detailPanelOpen={selectedBRDPs.length > 0}
            selectedBRDPs={selectedBRDPs}
            onDeselectBrdp={() => setSelectedBRDPs([])}
            onOpenGenerateModal={openGenerateModal}
            width={chatPanelWidth}
            onWidthChange={setChatPanelWidth}
          />
        )}
      </div>
      {showGenerateModal && (
        <GenerateModal
          brdps={brdps}
          onClose={() => setShowGenerateModal(false)}
        />
      )}
      {showBREXdocModal && (
        <BREXdocModal
          brdps={brdps}
          projectConfig={projectConfig}
          onClose={() => setShowBREXdocModal(false)}
        />
      )}
      {showAIExtractModal && (
        <AIExtractModal
          onClose={() => setShowAIExtractModal(false)}
          existingBRDPs={brdps}
          onImport={handleImportBRDPs}
        />
      )}
      <ToastContainer toasts={toasts} />
    </div>
  );
}

function App() {
  return (
    <BRDPProvider>
      <AppContent />
    </BRDPProvider>
  );
}

export default App;
