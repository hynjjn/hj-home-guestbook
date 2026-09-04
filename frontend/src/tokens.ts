/** 서버가 작성 응답에서만 내려주는 영구 edit_token을 기기에 보관한다. */

const KEY = "guestbook.edit_tokens";

type Store = Record<string, string>;

function read(): Store {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function write(store: Store) {
  try {
    localStorage.setItem(KEY, JSON.stringify(store));
  } catch {
    // 사파리 프라이빗 모드 등에서 실패할 수 있다. 이 경우 PIN 경로로 떨어진다.
  }
}

export function remember(id: number, token: string) {
  write({ ...read(), [String(id)]: token });
}

export function forget(id: number) {
  const store = read();
  delete store[String(id)];
  write(store);
}

export function tokenFor(id: number): string | undefined {
  return read()[String(id)];
}

export function allTokens(): string[] {
  return Object.values(read());
}
