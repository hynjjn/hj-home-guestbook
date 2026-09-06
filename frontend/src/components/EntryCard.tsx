import { useState } from "react";

import { ApiError, deleteEntry, patchEntry, verifyPin } from "../api";
import { formatDate } from "../format";
import { forget, tokenFor } from "../tokens";
import type { Entry } from "../types";
import { Avatar } from "./Avatar";

type Mode = null | "menu" | "pin" | "edit";
type Pending = "edit" | "delete";

export function EntryCard({
  entry,
  onChanged,
}: {
  entry: Entry;
  onChanged: () => void;
}) {
  const [mode, setMode] = useState<Mode>(null);
  const [pending, setPending] = useState<Pending>("edit");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function close() {
    setMode(null);
    setPin("");
    setError("");
    setToken(null);
  }

  async function act(next: Pending, useToken: string, content: string) {
    if (next === "edit") {
      setToken(useToken);
      setDraft(content);
      setMode("edit");
      return;
    }
    // 비밀글은 content가 응답에 없다. 그때는 그냥 "이 글"로 부른다.
    const head = (entry.content ?? "").trim();
    const label = head ? `"${head.length > 16 ? head.slice(0, 16) + "…" : head}"` : "이";
    if (!confirm(`${label} 글을 지울까요?\n되돌릴 수 없습니다.`)) {
      close();
      return;
    }
    setBusy(true);
    try {
      await deleteEntry(entry.id, useToken);
      forget(entry.id);
      onChanged();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "지우지 못했어요");
    } finally {
      setBusy(false);
      close();
    }
  }

  function ask(next: Pending) {
    setPending(next);
    setError("");
    const mine = tokenFor(entry.id);
    if (mine) {
      // 이 기기에서 쓴 글이면 PIN을 묻지 않는다
      void act(next, mine, entry.content ?? "");
      return;
    }
    setPin("");
    setMode("pin");
  }

  async function submitPin() {
    setBusy(true);
    try {
      const { edit_token, content } = await verifyPin(entry.id, pin);
      await act(pending, edit_token, content);
    } catch (e) {
      if (e instanceof ApiError && e.status === 423) {
        setError("여러 번 틀려서 한 시간 동안 잠겼어요");
      } else {
        setError("숫자가 맞지 않아요");
      }
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    const content = draft.trim();
    if (!content) return;
    if (!token) return;

    setBusy(true);
    try {
      await patchEntry(entry.id, token, content);
      onChanged();
      close();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "저장하지 못했어요");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="entry">
      <div className="entry-head">
        <Avatar seed={entry.name + entry.id} label={entry.name} />
        <span className="who">{entry.name}</span>
        <span className="when">
          {formatDate(entry.created_at)}
          {entry.updated_at ? " (수정됨)" : ""}
        </span>
        <button
          type="button"
          className="menu-btn"
          aria-expanded={mode !== null}
          aria-label="이 글 관리"
          onClick={() => (mode ? close() : setMode("menu"))}
        >
          ⋮
        </button>
      </div>

      {mode === "edit" ? (
        <>
          <div className="edit-area">
            <textarea
              value={draft}
              maxLength={1000}
              autoFocus
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
          <div className="card-foot">
            <button type="button" className="ghost" onClick={close}>
              취소
            </button>
            <button type="button" disabled={busy} onClick={() => void save()}>
              저장
            </button>
          </div>
        </>
      ) : (
        <div className="body">
          {entry.is_secret ? "주인장만 볼 수 있는 글이에요" : entry.content}
        </div>
      )}

      {entry.photo && (
        <img
          className="photo"
          src={entry.photo}
          alt={`${entry.name}님이 올린 사진`}
          loading="lazy"
        />
      )}

      {entry.reply && (
        <div className="reply">
          <div className="reply-head">
            <span>주인장</span>
            <span>{formatDate(entry.reply.at)}</span>
          </div>
          <div className="reply-body">{entry.reply.content}</div>
        </div>
      )}

      {mode === "menu" && (
        <div className="card-foot">
          <button
            type="button"
            className="ghost danger"
            disabled={busy}
            onClick={() => ask("delete")}
          >
            삭제
          </button>
          <button type="button" className="ghost" disabled={busy} onClick={() => ask("edit")}>
            수정
          </button>
          <button type="button" className="ghost" onClick={close}>
            닫기
          </button>
        </div>
      )}

      {mode === "pin" && (
        <div className="card-foot">
          <div className="pin-row">
            <input
              type="text"
              inputMode="numeric"
              maxLength={4}
              autoComplete="off"
              placeholder="숫자 4자리"
              value={pin}
              autoFocus
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              onKeyDown={(e) => {
                if (e.key === "Enter" && pin.length === 4) void submitPin();
              }}
            />
          </div>
          <button type="button" className="ghost" onClick={close}>
            취소
          </button>
          <button
            type="button"
            disabled={busy || pin.length !== 4}
            onClick={() => void submitPin()}
          >
            확인
          </button>
          {error && <p className="pin-msg">{error}</p>}
        </div>
      )}
    </article>
  );
}
