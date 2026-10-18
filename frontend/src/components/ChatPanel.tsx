"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { sceneApi } from "../lib/api";
import { useViewer } from "../lib/store/viewerStore";
import { focus } from "./viewer/camera";

export function ChatPanel({ sceneId }: { sceneId: string }) {
  const t = useTranslations();
  const [question, setQuestion] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [answer, setAnswer] = useState("");
  const [tool, setTool] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [sceneId],
  );
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [answer, tool]);

  async function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy || !question.trim()) return;
    const c = new AbortController();
    controller.current = c;
    const version = useViewer.getState().beginResult();
    const text = question.trim();
    setBusy(true);
    setError("");
    setAnswer("");
    setTool("");
    setSubmitted(text);
    setQuestion("");
    try {
      await sceneApi.askQuestion(
        sceneId,
        {
          question: text,
          camera: { ...useViewer.getState().camera, up: [0, 0, 1] },
        },
        (event) => {
          if (c.signal.aborted || controller.current !== c) return;
          if (event.type === "tool") setTool(event.tool || "");
          if (event.type === "delta")
            setAnswer((current) => current + (event.delta || ""));
          if (event.type === "final") {
            setAnswer(event.answer || "");
            setTool("");
            const ids = event.object_ids || [];
            if (useViewer.getState().showResult(version, "qa", ids)) focus(ids);
          }
        },
        c.signal,
      );
    } catch (e) {
      if (!c.signal.aborted) setError(String(e));
    } finally {
      if (controller.current === c) {
        setBusy(false);
        setTool("");
      }
    }
  }
  return (
    <section className="chat" aria-label={t("ask")}>
      <p className="caption muted">{t("englishInput")}</p>
      <div
        className="messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {submitted && (
          <article className="message user">
            <p>{submitted}</p>
          </article>
        )}
        {answer && (
          <article className="message assistant">
            <p>{answer}</p>
          </article>
        )}
        {busy && (
          <p className="stream-status" role="status">
            {tool && t.has(`ui.tools.${tool}`)
              ? t(`ui.tools.${tool}`)
              : t("ui.answering")}
          </p>
        )}
        <div ref={end} />
      </div>
      <form className="chat-composer" onSubmit={send}>
        <textarea
          aria-label={t("question")}
          placeholder={t("question")}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <button className="full-width" disabled={busy || !question.trim()}>
          {t("send")}
        </button>
        {busy && (
          <button
            className="secondary full-width"
            type="button"
            onClick={() => controller.current?.abort()}
          >
            {t("stop")}
          </button>
        )}
        <small className="muted">{t("ui.chatKeyboard")}</small>
        {error && <p role="alert">{error}</p>}
      </form>
    </section>
  );
}
