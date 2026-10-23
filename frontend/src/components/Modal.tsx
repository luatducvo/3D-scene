import { useEffect, useRef, type ReactNode } from "react";
import { useTranslations } from "use-intl";

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const t = useTranslations();
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="modal-title"
      onCancel={onClose}
    >
      <div className="panel-heading">
        <h2 id="modal-title">{title}</h2>
        <button className="quiet" onClick={onClose}>
          {t("ui.close")}
        </button>
      </div>
      {children}
    </dialog>
  );
}
