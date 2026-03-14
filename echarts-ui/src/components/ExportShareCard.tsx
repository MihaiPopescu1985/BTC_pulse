export interface ExportStatusMessage {
  tone: 'success' | 'error' | 'info';
  text: string;
}

interface ExportShareCardProps {
  status: ExportStatusMessage | null;
  onExportPng: () => void;
  onExportSvg: () => void;
  onCopyOptionJson: () => void;
  onDownloadOptionJson: () => void;
  onCopyShareLink: () => void;
}

export const ExportShareCard = ({
  status,
  onExportPng,
  onExportSvg,
  onCopyOptionJson,
  onDownloadOptionJson,
  onCopyShareLink,
}: ExportShareCardProps) => {
  return (
    <section className="section-card export-share-card">
      <h3>Export & Share</h3>
      <div className="export-grid">
        <button type="button" onClick={onExportPng}>
          Export PNG
        </button>
        <button type="button" onClick={onExportSvg}>
          Export SVG
        </button>
        <button type="button" onClick={onCopyOptionJson}>
          Copy option JSON
        </button>
        <button type="button" onClick={onDownloadOptionJson}>
          Download option.json
        </button>
        <button type="button" onClick={onCopyShareLink} className="export-span-two">
          Copy share link
        </button>
      </div>

      <p className={`export-status ${status?.tone ?? 'info'}`}>
        {status?.text ?? 'Ready to export or share.'}
      </p>
    </section>
  );
};
