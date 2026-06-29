export default function AlertModal({ isOpen, message, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-ink/40 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6 border border-line">
        <h3 className="text-lg font-display font-semibold text-ink mb-3 flex items-center gap-2">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-stamp">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          Aviso
        </h3>
        <p className="text-sm text-ink/70 font-body mb-6">
          {message}
        </p>
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium bg-ledger text-paper rounded hover:bg-ink transition-colors"
          >
            Aceptar
          </button>
        </div>
      </div>
    </div>
  )
}
