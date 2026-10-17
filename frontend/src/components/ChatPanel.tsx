"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { sceneApi } from "../lib/api";
import type { Schemas } from "../lib/api/types";
import { useViewer } from "../lib/store/viewerStore";
import { focus } from "./viewer/camera";

export function ChatPanel({ sceneId }: { sceneId: string }) {
  const t = useTranslations(),
    client = useQueryClient();
  const history = useQuery({
    queryKey: ["messages", sceneId],
    queryFn: () => sceneApi.getMessages(sceneId),
  });
  const [question, setQuestion] = useState(""),
    [submitted, setSubmitted] = useState(""),
    [answer, setAnswer] = useState(""),
    [tool, setTool] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null),
    end = useRef<HTMLDivElement>(null);
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [answer, history.data, tool]);
  async function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy || !question.trim()) return;
    const c = new AbortController();
    controller.current = c;
    const text = question.trim();
    setBusy(true);
    setError("");
    setAnswer("");
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
          if (c.signal.aborted) return;
          if (event.type === "tool") setTool(event.tool || "");
          if (event.type === "delta") setAnswer((a) => a + (event.delta || ""));
          if (event.type === "final") {
            setAnswer(event.answer || "");
            focus(event.object_ids || []);
            setTool("");
          }
        },
        c.signal,
      );
      await client.invalidateQueries(
        { queryKey: ["messages", sceneId] },
        { throwOnError: true },
      );
      setAnswer("");
      setSubmitted("");
    } catch (e) {
      if (!c.signal.aborted) setError(String(e));
    } finally {
      setBusy(false);
      setTool("");
    }
  }
  function focusMessage(content: Schemas["Message"]["content"]) {
    const ids = content.object_ids;
    if (Array.isArray(ids))
      focus(ids.filter((id): id is string => typeof id === "string"));
  }
  return (
    <section className="chat" aria-label={t("ask")}>
      <div
        className="messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {history.isLoading && <p className="muted">{t("loading")}</p>}
        {history.error && <p role="alert">{String(history.error)}</p>}
        {history.data?.map((m) => (
          <article key={m.id} className={`message ${m.role}`}>
            <p>{String(m.content.answer || m.content.question || "")}</p>
            {m.role === "assistant" &&
              Array.isArray(m.content.object_ids) &&
              m.content.object_ids.length > 0 && (
                <button
                  className="secondary full-width"
                  onClick={() => focusMessage(m.content)}
                >
                  {t("ui.showInScene")}
                </button>
              )}
          </article>
        ))}
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
