export type SaveStatus = 'saved' | 'unsaved' | 'restore_failed';

interface SessionCardProps {
  saveStatus: SaveStatus;
  lastPreset: string;
  onSaveNow: () => void;
  onResetSession: () => void;
}

const statusCopy: Record<SaveStatus, string> = {
  saved: 'Saved',
  unsaved: 'Unsaved changes',
  restore_failed: 'Restore failed',
};

export const SessionCard = ({ saveStatus, lastPreset, onSaveNow, onResetSession }: SessionCardProps) => {
  return (
    <section className="section-card session-card">
      <h3>Session</h3>
      <p className={`session-status ${saveStatus}`}>Status: {statusCopy[saveStatus]}</p>
      <p className="session-meta">Last starter: {lastPreset}</p>
      <div className="session-actions">
        <button type="button" onClick={onSaveNow}>
          Save now
        </button>
        <button type="button" onClick={onResetSession}>
          Reset session
        </button>
      </div>
    </section>
  );
};
