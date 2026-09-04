import { useEffect, useRef, useState } from "react";

import { ApiError, createEntry } from "../api";
import { shrink } from "../shrink";
import { remember } from "../tokens";

const MAX_MB = 8;

export function WriteForm({
  formRef,
  onCreated,
}: {
  formRef: React.RefObject<HTMLElement | null>;
  onCreated: (id: number) => void;
}) {
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [content, setContent] = useState("");
  // 미리보기 URL은 파일과 같이 들고 있어야 교체, 해제 시점이 어긋나지 않는다
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // 남은 URL은 언마운트할 때 정리한다
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);

  function replacePhoto(next: { file: File; url: string } | null) {
    setPhoto((prev) => {
      if (prev) URL.revokeObjectURL(prev.url);
      return next;
    });
  }

  function pick(file: File | undefined) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("사진만 올릴 수 있어요.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      alert(`사진은 ${MAX_MB}MB까지예요.`);
      return;
    }
    replacePhoto({ file, url: URL.createObjectURL(file) });
  }

  async function submit() {
    const trimmedName = name.trim();
    const trimmedContent = content.trim();

    if (!trimmedName || !trimmedContent) {
      alert("이름과 내용을 채워 주세요.");
      return;
    }
    if (pin.length !== 4) {
      alert("숫자 4자리를 넣어 주세요.");
      return;
    }

    setBusy(true);
    try {
      const sized = photo ? await shrink(photo.file) : null;
      const { id, edit_token } = await createEntry({
        name: trimmedName,
        content: trimmedContent,
        pin,
        photo: sized,
      });
      remember(id, edit_token);

      setName("");
      setPin("");
      setContent("");
      replacePhoto(null);
      onCreated(id);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "남기지 못했어요");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="write" id="write" ref={formRef as React.RefObject<HTMLElement>}>
      <h2>한마디 남기기</h2>

      <div className="row">
        <input
          id="name"
          placeholder="이름"
          maxLength={12}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          id="pin"
          type="password"
          placeholder="숫자 4자리 (필수)"
          inputMode="numeric"
          maxLength={4}
          autoComplete="off"
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
        />
      </div>
      <textarea
        id="content"
        placeholder="다녀간 흔적을 남겨 주세요"
        maxLength={1000}
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />

      {photo && (
        <div className="preview">
          <img src={photo.url} alt="" />
          <span>{photo.file.name}</span>
          <button type="button" aria-label="사진 빼기" onClick={() => replacePhoto(null)}>
            ✕
          </button>
        </div>
      )}

      <div className="foot">
        <div className="foot-tools">
          <button
            type="button"
            className="photo-button"
            aria-label="사진 첨부"
            title="사진 첨부"
            onClick={() => fileRef.current?.click()}
          >
            <svg viewBox="0 0 20 20" aria-hidden="true" shapeRendering="crispEdges">
              <rect x="2" y="3" width="16" height="14" fill="none" stroke="currentColor" strokeWidth="2" />
              <rect x="5" y="6" width="3" height="3" fill="currentColor" />
              <path d="M3 15L7 11L10 14L13 10L17 15" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>
          {/* 비밀글 체크박스가 있던 자리. DB에 is_secret 컬럼과 직렬화 필터는 남아 있다. */}
          <input
            type="file"
            accept="image/*"
            hidden
            ref={fileRef}
            onChange={(e) => {
              pick(e.target.files?.[0]);
              e.target.value = ""; // 같은 파일을 다시 골라도 change가 뜨도록
            }}
          />
        </div>
        <button disabled={busy} onClick={() => void submit()}>
          {busy ? "남기는 중" : "남기기"}
        </button>
      </div>
    </section>
  );
}
