import { useCallback, useEffect, useRef, useState } from "react";

import { fetchEntries } from "./api";
import { EntryCard } from "./components/EntryCard";
import { WriteForm } from "./components/WriteForm";
import type { Entry } from "./types";

const PAGE = 20;

export default function App() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [fabHidden, setFabHidden] = useState(false);

  const writeRef = useRef<HTMLElement | null>(null);
  const listRef = useRef<HTMLElement | null>(null);

  const reload = useCallback(async () => {
    try {
      const feed = await fetchEntries({ limit: PAGE });
      setEntries(feed.entries);
      setTotal(feed.total);
      setHasMore(feed.has_more);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // 첫 로딩. reload는 await로 시작하므로 동기 setState가 일어나지 않는다
    // eslint-disable-next-line react/set-state-in-effect
    void reload();
  }, [reload]);

  /* 작성 폼이 화면에 들어오면 플로팅 버튼을 감춘다 */
  useEffect(() => {
    const target = writeRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => setFabHidden(entry.isIntersecting),
      { threshold: 0.25 },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  async function loadMore() {
    const last = entries.at(-1);
    if (!last) return;

    // 늘어난 뒤에도 보던 위치를 유지한다
    const anchor = listRef.current?.lastElementChild;
    const before = anchor?.getBoundingClientRect().top ?? 0;

    const feed = await fetchEntries({ limit: PAGE, before: last.id });
    setEntries((prev) => [...prev, ...feed.entries]);
    setTotal(feed.total);
    setHasMore(feed.has_more);

    requestAnimationFrame(() => {
      const after = anchor?.getBoundingClientRect().top ?? before;
      window.scrollBy(0, after - before);
    });
  }

  async function afterCreate(id: number) {
    await reload();
    // 남긴 게 보여야 남긴 맛이 난다
    requestAnimationFrame(() => {
      document
        .getElementById(`entry-${id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  const left = total - entries.length;

  return (
    <>
      <div className="wrap">
        <header className="head">
          <h1>Hyeonjin's Home</h1>
          <p>{total}명이 다녀갔어요</p>
        </header>

        <main id="list" ref={listRef as React.RefObject<HTMLElement>}>
          {entries.map((entry) => (
            <div key={entry.id} id={`entry-${entry.id}`}>
              <EntryCard entry={entry} onChanged={() => void reload()} />
            </div>
          ))}
        </main>

        {failed && <p className="list-end">글을 불러오지 못했어요</p>}
        {loading && entries.length === 0 && <p className="list-end">불러오는 중</p>}

        {hasMore && (
          <div className="more-wrap">
            <button type="button" className="more-button" onClick={() => void loadMore()}>
              더 보기{left > 0 ? ` (${left}개 남음)` : ""}
            </button>
          </div>
        )}
        {!hasMore && entries.length > 0 && <p className="list-end">여기까지가 처음이에요</p>}

        <WriteForm formRef={writeRef} onCreated={(id) => void afterCreate(id)} />
      </div>

      <button
        type="button"
        className="fab"
        hidden={fabHidden}
        onClick={() => {
          writeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
          setTimeout(() => document.getElementById("name")?.focus(), 400);
        }}
      >
        <svg viewBox="0 0 16 16" aria-hidden="true" shapeRendering="crispEdges" fill="currentColor">
          <rect x="9" y="1" width="4" height="2" /><rect x="11" y="3" width="2" height="2" />
          <rect x="7" y="3" width="2" height="2" /><rect x="9" y="5" width="2" height="2" />
          <rect x="5" y="5" width="2" height="2" /><rect x="7" y="7" width="2" height="2" />
          <rect x="3" y="7" width="2" height="2" /><rect x="5" y="9" width="2" height="2" />
          <rect x="2" y="9" width="2" height="2" /><rect x="3" y="11" width="2" height="2" />
          <rect x="2" y="11" width="1" height="3" /><rect x="2" y="13" width="3" height="1" />
        </svg>
        남기기
      </button>
    </>
  );
}
