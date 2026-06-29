import React from 'react'

export default function ConfirmModal({ isOpen, message, title = "¿Confirmar acción?", onConfirm, onCancel, isProcessing = false, confirmText = "Confirmar", cancelText = "Cancelar" }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-ink/40 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-xl max-w-sm w-full p-6 border border-line">
        <h3 className="text-lg font-display font-semibold text-ink mb-2">
          {title}
        </h3>
        <p className="text-sm text-ink/70 font-body mb-6">
          {message}
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={isProcessing}
            className="px-4 py-2 text-sm font-medium text-ink/60 hover:text-ink transition-colors disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={isProcessing}
            className="px-4 py-2 text-sm font-medium bg-ledger text-paper rounded hover:bg-ink transition-colors disabled:opacity-50"
          >
            {isProcessing ? 'Procesando...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
