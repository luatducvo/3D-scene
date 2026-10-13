"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { sceneApi } from "../lib/api";
import type { Schemas } from "../lib/api/port";
import { useViewer } from "../lib/store/viewerStore";
export function ChatPanel({
  sceneId,
  suggestion,
}: {
  sceneId: string;
  suggestion: string;
}) {
  const t = useTranslations(),
    client = useQueryClient();
  const history = useQuery({
    queryKey: ["messages", sceneId],
    queryFn: () => sceneApi.getMessages(sceneId),
  });
  const [question, setQuestion] = useState(suggestion),
    [answer, setAnswer] = useState(""),
    [tool, setTool] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [evidence, setEvidence] = useState<Schemas["Evidence"][]>([]);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => setQuestion(suggestion), [suggestion]);
  useEffect(() => () => controller.current?.abort(), []);
  return (
    <section className="chat">
      <div className="messages">
        {history.data?.map((m) => (
          <p key={m.id} className={m.role}>
            {String(m.content.answer || m.content.question || "")}
          </p>
        ))}
        {answer && <p className="assistant">{answer}</p>}
        {tool && <small role="status">{t("tool", { tool })}</small>}
        <div className="evidence">
          {evidence.map((e, i) => (
            <img key={i} src={e.image_url} alt={t("evidence")} />
          ))}
        </div>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy || !question.trim()) return;
          const c = new AbortController();
          controller.current = c;
          setBusy(true);
          setError("");
          setAnswer("");
          setEvidence([]);
          try {
            await sceneApi.askQuestion(
              sceneId,
              {
                question,
                camera: { ...useViewer.getState().camera, up: [0, 0, 1] },
              },
              (event) => {
                if (event.type === "tool") setTool(event.tool || "");
                if (event.type === "delta")
                  setAnswer((a) => a + (event.delta || ""));
                if (event.type === "final") {
                  setAnswer(event.answer || "");
                  setEvidence(event.evidence || []);
                  useViewer.getState().highlight(event.object_ids || []);
                  setTool("");
                }
              },
              c.signal,
            );
            setQuestion("");
            await client.invalidateQueries({ queryKey: ["messages", sceneId] });
            setAnswer("");
          } catch (e) {
            if (!c.signal.aborted) setError(String(e));
          } finally {
            setBusy(false);
            setTool("");
          }
        }}
      >
        <textarea
          aria-label={t("question")}
          placeholder={t("question")}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button disabled={busy || !question.trim()}>{t("send")}</button>
        {busy && (
          <button type="button" onClick={() => controller.current?.abort()}>
            {t("stop")}
          </button>
        )}
      </form>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
